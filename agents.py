from crewai import Agent

def create_agents(llm):

    analyzer = Agent(
        role="Senior Software Architect",
        goal="Understand and summarize GitHub repository clearly",
        backstory="Expert at analyzing AI and data science projects",
        llm=llm,
        verbose=False
    )

    writer = Agent(
        role="Professional Blog Writer",
        goal="Write complete long-form readable blog",
        backstory="Writes clear technical blogs in plain text format",
        llm=llm,
        verbose=False
    )

    return analyzer, writer
