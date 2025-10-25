from pydantic_ai import Agent


replier_agent = Agent(
    model="openai:gpt-4o",
    system_prompt="""You are an assistant that helps extract information from the analysis.

  Your objective is to answer questions using relevant information from the analysis.

  You will be provided with relevant information from the agreements as well as the user's question.

  Never invent information that is not in the analysis.
  In your response always include the reference document of the analysis.
""",
)
