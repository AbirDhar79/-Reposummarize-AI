import os
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

import streamlit as st
from tools.github_tool import fetch_repo_content
from crew import run_crew

st.set_page_config(page_title="RepoScribe AI", layout="wide")

st.title("🚀 RepoScribe AI")
st.write("Generate a professional readable blog from any GitHub repository.")

# Sidebar for keys
st.sidebar.header("🔐 API Configuration")

hf_api_key = st.sidebar.text_input(
    "HuggingFace API Key",
    type="password"
)

github_token = st.sidebar.text_input(
    "GitHub API Token",
    type="password"
)

repo_url = st.text_input("🔗 Enter GitHub Repository URL")

if st.button("✨ Generate Blog"):

    if not hf_api_key or not github_token or not repo_url:
        st.error("Please provide HuggingFace key, GitHub token, and repository URL.")
    else:
        try:
            with st.spinner("📂 Fetching repository..."):
                repo_content = fetch_repo_content(repo_url, github_token)

            if not repo_content:
                st.error("No readable content found in repository.")
                st.stop()

            with st.spinner("🤖 Generating blog using AI Agents..."):
                blog = run_crew(repo_content, hf_api_key)

            st.success("✅ Blog Generated Successfully!")

            st.markdown(
                f"""
                <div style="
                    background-color:#f9f9f9;
                    padding:30px;
                    border-radius:10px;
                    line-height:1.8;
                    font-size:18px;
                    color:#111;
                ">
                {blog}
                </div>
                """,
                unsafe_allow_html=True
            )

            st.download_button(
                label="⬇ Download Blog",
                data=blog,
                file_name="generated_blog.txt",
                mime="text/plain"
            )

        except Exception as e:
            st.error(f"Error: {str(e)}")
