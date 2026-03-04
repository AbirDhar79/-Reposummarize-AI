import json, time, pathlib, traceback
from crewai import Task, Crew
from agents import create_agents
from utils.llm_loader import load_llm

_LOG = pathlib.Path(__file__).parent / "debug-005439.log"

def _log(msg, data=None, hypothesis_id=""):
    entry = {"sessionId":"005439","timestamp":int(time.time()*1000),"location":"crew.py","message":msg,"data":data or {},"hypothesisId":hypothesis_id}
    with open(_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

def run_crew(repo_content, hf_api_key, model_name="mistralai/Mistral-7B-Instruct-v0.2"):

    llm, resolved_model = load_llm(hf_api_key, model_name=model_name)

    analyzer, writer = create_agents(llm)

    analyze_task = Task(
        description=f"""
        Analyze the following GitHub repository content and summarize:
        - Project objective
        - Tech stack
        - Architecture
        - Key features
        - Models used
        - Business impact

        Repository Content:
        {repo_content}
        """,
        expected_output="Structured project summary.",
        agent=analyzer
    )

    write_task = Task(
        description="""
        Using the project summary, write a complete, professional,
        long-form blog article in plain readable text.

        IMPORTANT:
        - Do NOT use markdown
        - Do NOT use # headings
        - Do NOT include YAML
        - Do NOT use bullet markdown symbols
        - Write in natural paragraph format
        - Minimum 1200 words

        Include:
        - Introduction
        - Problem Statement
        - Dataset Overview
        - Model Explanation
        - Performance Metrics
        - Business Insights
        - Conclusion
        """,
        expected_output="Complete readable blog article.",
        agent=writer,
        context=[analyze_task]
    )

    crew = Crew(
        agents=[analyzer, writer],
        tasks=[analyze_task, write_task],
        verbose=False
    )

    _log("crew.kickoff starting", {"requested_model": model_name, "resolved_model": resolved_model}, "H-A")
    try:
        result = crew.kickoff()
    except Exception as exc:
        full_trace = traceback.format_exc()
        _log(
            "crew.kickoff EXCEPTION",
            {
                "type": type(exc).__name__,
                "msg": str(exc),
                "trace_tail": full_trace[-2000:],
                "hint": (
                    "404 NotFoundError usually means the model is unavailable on "
                    "this HuggingFace endpoint. Check debug-005439.log for probe results."
                ) if "NotFoundError" in type(exc).__name__ or "404" in str(exc) else "",
            },
            "H-B",
        )
        raise

    if not result.raw or not result.raw.strip():
        raise ValueError(
            "The AI crew returned an empty result. "
            "The model may have timed out or failed to generate a response. "
            "Please try again."
        )

    return result.raw, resolved_model
