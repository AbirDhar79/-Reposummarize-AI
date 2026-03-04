import os
import sys
from pathlib import Path

# ── Startup permission fix ────────────────────────────────────────────────────
# Streamlit writes a telemetry file to ~/.streamlit/machine_id_v4 on every
# session start. If that folder is owned by Administrators (common on Windows
# when Streamlit was previously run with elevated rights), the write fails with
# PermissionError and the app session never loads.
#
# Fix: probe whether ~/.streamlit is writable; if not, redirect USERPROFILE
# to the project directory, which already contains a writable .streamlit/ folder.
def _ensure_streamlit_writable() -> None:
    streamlit_home = Path.home() / ".streamlit"
    probe = streamlit_home / ".write_probe"
    try:
        streamlit_home.mkdir(parents=True, exist_ok=True)
        probe.touch()
        probe.unlink()
    except (PermissionError, OSError):
        project_root = Path(__file__).parent
        writable_streamlit = project_root / ".streamlit"
        writable_streamlit.mkdir(exist_ok=True)
        os.environ["USERPROFILE"] = str(project_root)
        os.environ["HOME"] = str(project_root)
        print(
            f"[RepoScribe] ~/.streamlit is not writable — redirected to "
            f"{writable_streamlit} (permission fix applied automatically).",
            file=sys.stderr,
        )

_ensure_streamlit_writable()
# ─────────────────────────────────────────────────────────────────────────────

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"   # suppress interactive tracing prompt

import html
import re
import streamlit as st
from tools.github_tool import fetch_repo_content
from crew import run_crew

SUPPORTED_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.2",
    "Qwen/Qwen2.5-7B-Instruct",
    "HuggingFaceH4/zephyr-7b-beta",
    "microsoft/Phi-3-mini-4k-instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]

GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[\w\-\.]+/[\w\-\.]+(/.*)?$"
)


def extract_repo_name(url: str) -> str:
    parts = url.rstrip("/").rstrip(".git").split("/")
    return parts[-1] if parts else "repo"


def validate_github_url(url: str) -> str | None:
    """Return an error string if invalid, else None."""
    url = url.strip()
    if not url:
        return "Repository URL is required."
    if not url.startswith("https://github.com/"):
        return "URL must start with https://github.com/"
    if not GITHUB_URL_PATTERN.match(url):
        return "URL must be in the format https://github.com/owner/repo"
    return None


def _blog_to_paragraphs(text: str) -> list[str]:
    """Split blog plain-text into paragraphs for nice rendering."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paras) <= 1:
        paras = [p.strip() for p in text.split("\n") if p.strip()]
    return paras


# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="RepoScribe AI", page_icon="🚀", layout="wide")

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Global ──────────────────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background: #f0f2f8;
}

/* ── Hero card ───────────────────────────────────────────── */
.hero-card {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    padding: 2.5rem 2rem 2rem;
    border-radius: 16px;
    text-align: center;
    margin-bottom: 1.8rem;
    box-shadow: 0 8px 32px rgba(79, 70, 229, 0.28);
}
.hero-card h1 {
    color: white;
    font-size: 2.6rem;
    font-weight: 800;
    margin: 0 0 0.4rem;
    letter-spacing: -0.5px;
    line-height: 1.1;
}
.hero-card p {
    color: rgba(255, 255, 255, 0.85);
    font-size: 1.05rem;
    margin: 0;
}
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.18);
    color: white;
    border-radius: 20px;
    padding: 0.2rem 0.8rem;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 0.8rem;
    text-transform: uppercase;
}

/* ── Sidebar branding ────────────────────────────────────── */
.sidebar-brand {
    text-align: center;
    padding: 0.5rem 0 1rem;
}
.sidebar-brand .brand-icon {
    font-size: 2.2rem;
    line-height: 1;
}
.sidebar-brand .brand-name {
    font-weight: 800;
    font-size: 1.1rem;
    color: #4f46e5;
    margin: 0.3rem 0 0.1rem;
}
.sidebar-brand .brand-tagline {
    font-size: 0.72rem;
    color: #888;
    letter-spacing: 0.3px;
}
.sidebar-divider {
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 0.5rem 0 1.2rem;
}

/* ── Generate button ─────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 0.65rem 1.5rem !important;
    transition: transform 0.18s, box-shadow 0.18s !important;
    box-shadow: 0 4px 14px rgba(79, 70, 229, 0.38) !important;
    width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.48) !important;
}

/* ── Metric cards ────────────────────────────────────────── */
.metrics-row {
    display: flex;
    gap: 1rem;
    margin: 1.2rem 0 1.6rem;
}
.metric-card {
    flex: 1;
    background: white;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    border-top: 3px solid #4f46e5;
}
.metric-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #9ca3af;
    margin-bottom: 4px;
    font-weight: 600;
}
.metric-value {
    font-size: 1.5rem;
    font-weight: 800;
    color: #4f46e5;
    line-height: 1.1;
}
.metric-sub {
    font-size: 0.7rem;
    color: #9ca3af;
    margin-top: 2px;
}

/* ── Blog output container ───────────────────────────────── */
.blog-wrapper {
    background: white;
    border-radius: 14px;
    padding: 2.5rem 3rem 2rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    max-width: 820px;
    margin: 0 auto 1.5rem;
}
.blog-title-bar {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 1.6rem;
    padding-bottom: 1rem;
    border-bottom: 2px solid #f3f4f6;
}
.blog-title-bar .dot {
    width: 12px; height: 12px; border-radius: 50%;
}
.blog-p {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 1.08rem;
    line-height: 1.95;
    color: #1f2937;
    margin-bottom: 1.3em;
    text-align: justify;
}
.blog-p.first-para::first-letter {
    font-size: 3.2rem;
    font-weight: 700;
    float: left;
    line-height: 0.85;
    margin: 0.1em 0.12em -0.05em 0;
    color: #4f46e5;
}

/* ── Download buttons ────────────────────────────────────── */
[data-testid="stDownloadButton"] button {
    background: #059669 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.2rem !important;
    transition: opacity 0.15s !important;
    width: 100% !important;
}
[data-testid="stDownloadButton"] button:hover {
    opacity: 0.88 !important;
}

/* ── Footer ──────────────────────────────────────────────── */
.rs-footer {
    text-align: center;
    color: #c0c4ce;
    font-size: 0.75rem;
    padding: 2rem 0 1rem;
}

/* ── Success banner ──────────────────────────────────────── */
.success-banner {
    background: linear-gradient(135deg, #d1fae5, #a7f3d0);
    border-left: 4px solid #059669;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    margin-bottom: 1rem;
    font-weight: 600;
    color: #065f46;
    font-size: 0.95rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ─── Hero Header ─────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="hero-card">
    <div class="hero-badge">✨ Powered by open-source AI</div>
    <h1>🚀 RepoScribe AI</h1>
    <p>Transform any GitHub repository into a professional, long-form blog article in minutes</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.expander("📖 Quick Start Guide", expanded=False):
    st.markdown(
        """
### How to use RepoScribe AI

| Step | What to do |
|---|---|
| **1** | Get a free **HuggingFace API key** (`hf_...`) → [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| **2** | Get a free **GitHub token** (`ghp_...`) → [github.com/settings/tokens](https://github.com/settings/tokens) |
| **3** | Paste both keys in the **sidebar on the left** |
| **4** | Paste any GitHub repo URL below (e.g. `https://github.com/owner/repo`) |
| **5** | Click **✨ Generate Blog** and wait 1–3 minutes |
| **6** | Read or download the generated blog article |

**Tips:**
- Works best on **Python / ML / data science** repos with `.py` and `.md` files
- C++ / Java / Go repos are supported but only `README.md` and `.txt` files are read
- If generation fails, switch the model in the sidebar and try again
- Keys are never stored — they only live in your browser session
        """
    )

# Persist password field values and error state across reruns via session_state.
for key in ("hf_api_key", "github_token"):
    if key not in st.session_state:
        st.session_state[key] = ""
if "error_msg" not in st.session_state:
    st.session_state["error_msg"] = ""

def _clear_error():
    """Clear the sticky error the moment the user edits any input field."""
    st.session_state["error_msg"] = ""

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.markdown(
    """
<div class="sidebar-brand">
    <div class="brand-icon">🚀</div>
    <div class="brand-name">RepoScribe AI</div>
    <div class="brand-tagline">GitHub → Blog in minutes</div>
</div>
<hr class="sidebar-divider">
""",
    unsafe_allow_html=True,
)

st.sidebar.header("🔐 API Configuration")

with st.sidebar.expander("❓ How to get a HuggingFace API Key", expanded=False):
    st.markdown(
        """
**HuggingFace** runs the AI model that writes the blog.

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click **"New token"**
3. Give it any name (e.g. `RepoScribe`)
4. Set **Type** to **Read**
5. Click **"Generate a token"**
6. Copy the key — it starts with **`hf_`**

> The free tier supports the models listed below. No credit card needed.
        """
    )

hf_api_key = st.sidebar.text_input(
    "HuggingFace API Key",
    type="password",
    key="hf_api_key",
    placeholder="hf_...",
    on_change=_clear_error,
)

with st.sidebar.expander("❓ How to get a GitHub API Token", expanded=False):
    st.markdown(
        """
**GitHub** token lets the app read repository files on your behalf.

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Give it any name (e.g. `RepoScribe`)
4. Set **Expiration** to 90 days (or No expiration)
5. Check the **`public_repo`** scope (for public repos)
   — check **`repo`** if you want to analyse private repos too
6. Scroll down → click **"Generate token"**
7. Copy the key — it starts with **`ghp_`**

> Without this token GitHub rate-limits to ~60 requests/hour, which can cause failures on large repos.
        """
    )

github_token = st.sidebar.text_input(
    "GitHub API Token",
    type="password",
    key="github_token",
    placeholder="ghp_...",
    on_change=_clear_error,
)

st.sidebar.header("🤖 Model Selection")
model_name = st.sidebar.selectbox(
    "HuggingFace Model",
    options=SUPPORTED_MODELS,
    index=0,
    help="Choose the instruction-tuned model to generate the blog.",
)

with st.sidebar.expander("ℹ️ Which model should I pick?", expanded=False):
    st.markdown(
        """
| Model | Notes |
|---|---|
| **Mistral-7B v0.2** | Recommended default — reliable on free tier |
| **Qwen 2.5-7B** | Strong reasoning, good fallback |
| **Zephyr-7B** | Clear, conversational writing style |
| **Phi-3-mini** | Fastest on free tier |
| **Llama 3.2-3B** | Lightweight, good for short repos |
| **Mistral-7B v0.3** | May be unavailable on the free tier |

If the model you pick is unavailable, the app will **automatically fall back**
to the next available model and tell you which one was used.
        """
    )

# ─── Main input area ─────────────────────────────────────────────────────────
_error_slot = st.empty()
if st.session_state["error_msg"]:
    _error_slot.error(st.session_state["error_msg"])

repo_url = st.text_input(
    "🔗 GitHub Repository URL",
    placeholder="https://github.com/owner/repository",
    on_change=_clear_error,
)

generate_clicked = st.button("✨ Generate Blog", type="primary")

# ─── Generation logic ─────────────────────────────────────────────────────────
if generate_clicked:
    hf_api_key = st.session_state.get("hf_api_key", "").strip()
    github_token = st.session_state.get("github_token", "").strip()

    if not hf_api_key or not github_token:
        st.session_state["error_msg"] = (
            "Please provide both your HuggingFace API key and GitHub token in the sidebar."
        )
        _error_slot.error(st.session_state["error_msg"])
        st.stop()

    url_error = validate_github_url(repo_url)
    if url_error:
        st.session_state["error_msg"] = f"Invalid repository URL — {url_error}"
        _error_slot.error(st.session_state["error_msg"])
        st.stop()

    clean_url = repo_url.strip().rstrip("/")
    repo_name = extract_repo_name(clean_url)

    try:
        with st.spinner("📂 Fetching repository content…"):
            repo_content = fetch_repo_content(clean_url, github_token)

        if not repo_content or not repo_content.strip():
            st.session_state["error_msg"] = (
                "No readable content was found in the repository. "
                "Make sure it has text files and is publicly accessible (or your token has access)."
            )
            _error_slot.error(st.session_state["error_msg"])
            st.stop()

        with st.spinner("🤖 Analyzing repo and writing blog — this may take 1–3 minutes…"):
            blog, resolved_model = run_crew(repo_content, hf_api_key, model_name=model_name)

        if not blog or not blog.strip():
            st.session_state["error_msg"] = (
                "The AI agents returned an empty result. "
                "This can happen when the model quota is exceeded or the output was filtered. "
                "Try again in a few minutes or switch to a different model."
            )
            _error_slot.error(st.session_state["error_msg"])
            st.stop()

        if resolved_model != model_name:
            st.info(
                f"ℹ️ The model you selected (`{model_name}`) was not available on the "
                f"HuggingFace free inference tier. The blog was generated using "
                f"**`{resolved_model}`** instead."
            )

        # ── Success banner ────────────────────────────────────────────────────
        st.markdown(
            '<div class="success-banner">✅ Blog generated successfully!</div>',
            unsafe_allow_html=True,
        )

        # ── Metrics row ───────────────────────────────────────────────────────
        word_count = len(blog.split())
        read_time = max(1, round(word_count / 200))
        model_short = resolved_model.split("/")[-1]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Words</div>
                    <div class="metric-value">{word_count:,}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Read time</div>
                    <div class="metric-value">{read_time} min</div>
                    <div class="metric-sub">at 200 wpm</div>
                </div>""",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">Model</div>
                    <div class="metric-value" style="font-size:0.82rem; padding-top:0.2rem">{model_short}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        # ── Blog display ──────────────────────────────────────────────────────
        paragraphs = _blog_to_paragraphs(blog)
        paras_html = ""
        for i, para in enumerate(paragraphs):
            css_class = "blog-p first-para" if i == 0 else "blog-p"
            paras_html += f'<p class="{css_class}">{html.escape(para)}</p>\n'

        st.markdown(
            f"""
<div class="blog-wrapper">
    <div class="blog-title-bar">
        <div class="dot" style="background:#ef4444;"></div>
        <div class="dot" style="background:#f59e0b;"></div>
        <div class="dot" style="background:#10b981;"></div>
        <span style="margin-left:0.4rem; font-size:0.8rem; color:#9ca3af; font-weight:500;">
            {repo_name} — generated blog
        </span>
    </div>
    {paras_html}
</div>
""",
            unsafe_allow_html=True,
        )

        # ── Download buttons ──────────────────────────────────────────────────
        st.markdown("**Download article:**")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇ Download as .txt",
                data=blog,
                file_name=f"blog_{repo_name}.txt",
                mime="text/plain",
            )
        with dl_col2:
            md_content = f"# {repo_name}\n\n" + "\n\n".join(paragraphs)
            st.download_button(
                label="⬇ Download as .md",
                data=md_content,
                file_name=f"blog_{repo_name}.md",
                mime="text/markdown",
            )

    except Exception as e:
        err_msg = str(e)
        err_lower = err_msg.lower()

        if "rate limit" in err_lower or ("403" in err_msg and "github" in err_lower):
            st.session_state["error_msg"] = (
                "GitHub API rate limit exceeded. "
                "Wait a few minutes and try again, or use a GitHub token with higher limits."
            )
        elif "repository" in err_lower and "not found" in err_lower and "github" in err_lower:
            st.session_state["error_msg"] = (
                "Repository not found (404). "
                "Check that the URL is correct and that your token has access to the repo."
            )
        elif (
            "NotFoundError" in err_msg
            or "OpenAIException" in err_msg
            or "endpoint not reachable" in err_lower
        ):
            st.session_state["error_msg"] = (
                "HuggingFace model endpoint returned 404 (Not Found).\n\n"
                "**Likely causes:**\n"
                "- The selected model is not available on the free HuggingFace inference tier.\n"
                "- Your API key may lack 'Make calls to serverless Inference API' permission.\n"
                "- The HuggingFace router may be temporarily unavailable.\n\n"
                "**What to try:**\n"
                "1. Switch to a different model in the sidebar (e.g. Mistral-7B v0.2 or Zephyr-7B).\n"
                "2. Re-generate your HuggingFace token at huggingface.co/settings/tokens "
                "with the **'Make calls to serverless Inference API'** permission enabled.\n"
                "3. Check https://status.huggingface.co for outages.\n\n"
                f"**Debug detail:** `{err_msg[:300]}`\n\n"
                "Full probe results are written to `debug-005439.log` in the project folder."
            )
        else:
            st.session_state["error_msg"] = f"An unexpected error occurred: {err_msg}"

        _error_slot.error(st.session_state["error_msg"])

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="rs-footer">RepoScribe AI · Open-source AI · Keys never stored</div>',
    unsafe_allow_html=True,
)
