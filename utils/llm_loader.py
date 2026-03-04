import json, time, pathlib
import requests
from crewai import LLM

# Primary OpenAI-compatible router endpoint (hf-inference = HuggingFace's own free tier)
HF_ROUTER_BASE = "https://router.huggingface.co/hf-inference/v1"

# Fallback: the bare /v1 gateway on the same router
HF_ROUTER_BARE_BASE = "https://router.huggingface.co/v1"

# Models tried in order when the requested model is unavailable.
# All are instruction-tuned, chat-capable, and confirmed available on the
# hf-inference provider's free tier.
FALLBACK_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    "HuggingFaceH4/zephyr-7b-beta",
    "mistralai/Mistral-7B-Instruct-v0.2",
    "microsoft/Phi-3-mini-4k-instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "tiiuae/falcon-7b-instruct",
]

_LOG = pathlib.Path(__file__).parent.parent / "debug-005439.log"


def _log(msg, data=None, hypothesis_id=""):
    entry = {
        "sessionId": "005439",
        "timestamp": int(time.time() * 1000),
        "location": "llm_loader.py",
        "message": msg,
        "data": data or {},
        "hypothesisId": hypothesis_id,
    }
    with open(_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _probe_one(url: str, model: str, hf_api_key: str) -> dict:
    """POST a minimal chat-completions request and return status + body snippet."""
    headers = {
        "Authorization": f"Bearer {hf_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        return {
            "url": url,
            "model": model,
            "status": resp.status_code,
            "body": resp.text[:400],
            "ok": resp.status_code == 200,
        }
    except Exception as exc:
        return {"url": url, "model": model, "status": -1, "body": str(exc), "ok": False}


def probe_hf_endpoint(hf_api_key: str, requested_model: str) -> dict:
    """Probe the requested model, then fallbacks, across both base URLs.

    Returns:
        working_base   – first base URL that returned HTTP 200 (or None)
        working_model  – first model name that returned HTTP 200 (or None)
        results        – full list of probe dicts
    """
    # Build a deduplicated candidate list: requested model first, then fallbacks
    models_to_try = [requested_model] + [
        m for m in FALLBACK_MODELS if m != requested_model
    ]
    bases_to_try = [HF_ROUTER_BASE, HF_ROUTER_BARE_BASE]

    results = []
    working_base = None
    working_model = None

    for model in models_to_try:
        for base in bases_to_try:
            url = f"{base}/chat/completions"
            r = _probe_one(url, model, hf_api_key)
            results.append(r)
            _log(
                "probe",
                {"url": url, "model": model, "status": r["status"], "body": r["body"]},
                "H-PROBE",
            )
            if r["ok"] and working_base is None:
                working_base = base
                working_model = model
                # Don't short-circuit — log all results for diagnostics
                break   # skip second base for this model once we have a winner
        if working_base is not None:
            break   # we have a working combo; stop trying more models

    _log(
        "probe summary",
        {
            "requested_model": requested_model,
            "working_base": working_base,
            "working_model": working_model,
            "total_probes": len(results),
        },
        "H-PROBE-SUMMARY",
    )
    return {
        "working_base": working_base,
        "working_model": working_model,
        "results": results,
    }


def _build_probe_report(results: list) -> str:
    lines = []
    for r in results:
        tag = "OK " if r["ok"] else "   "
        lines.append(f"  {tag} [{r['status']}] {r['model']}  @  {r['url']}\n       {r['body'][:120]}")
    return "\n".join(lines)


def load_llm(hf_api_key, model_name="mistralai/Mistral-7B-Instruct-v0.2"):
    _log(
        "load_llm called – probing endpoint",
        {
            "requested_model": model_name,
            "primary_base": HF_ROUTER_BASE,
            "key_prefix": hf_api_key[:8] if hf_api_key else "EMPTY",
        },
        "H-A",
    )

    probe = probe_hf_endpoint(hf_api_key, model_name)

    if probe["working_base"] is None:
        report = _build_probe_report(probe["results"])
        _log("no working model/endpoint found", {"report": report}, "H-FAIL")
        raise RuntimeError(
            f"No available HuggingFace model found for your API key.\n\n"
            f"Requested model: {model_name}\n\n"
            f"Probe results (tried {len(probe['results'])} combinations):\n{report}\n\n"
            "Possible fixes:\n"
            "  1. Go to huggingface.co/settings/tokens, regenerate your token and enable\n"
            "     the 'Make calls to serverless Inference API' permission.\n"
            "  2. Visit https://huggingface.co/models and check that the model you selected\n"
            "     shows a 'Serverless Inference API' badge.\n"
            "  3. Check https://status.huggingface.co for outages."
        )

    actual_model = probe["working_model"]
    actual_base = probe["working_base"]

    if actual_model != model_name:
        _log(
            "requested model unavailable – using fallback",
            {"requested": model_name, "fallback": actual_model, "base": actual_base},
            "H-FALLBACK",
        )

    _log(
        "load_llm resolved",
        {"model": actual_model, "api_base": actual_base},
        "H-OK",
    )

    return LLM(
        model=f"openai/{actual_model}",
        api_key=hf_api_key,
        api_base=actual_base,
        temperature=0.7,
        max_tokens=3000,
    ), actual_model   # return model name so crew.py can surface it in the UI
