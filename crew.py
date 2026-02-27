from crewai import Task, Crew
from agents import create_agents
from utils.llm_loader import load_llm

def run_crew(repo_content, hf_api_key):

    llm = load_llm(hf_api_key)

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
        agent=writer
    )

    crew = Crew(
        agents=[analyzer, writer],
        tasks=[analyze_task, write_task],
        verbose=False
    )

    result = crew.kickoff()

    return result.raw
