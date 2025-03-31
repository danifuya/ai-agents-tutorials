# Add the parent directory to Python path
import sys
import os

# Update the system path to include the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Import necessary modules and classes
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver
from pydantic_ai.messages import ModelMessage

# Import agents and related classes
from agents.search_agent import search_agent, Tool
from agents.listing_filtering_agent import listing_filtering_agent, potential_ai_agent
from agents.listing_summarizer_agent import listing_summarizer_agent
from agents.listing_classifier_agent import AIAgentListing, listing_classifier_agent
from agents.db_inserter_agent import db_inserter_agent
from agents.feedback_router import feedback_router
from agents.listing_rectifier_agent import listing_rectifier_agent


# Define state schema
class AgentState(TypedDict):
    latest_user_message: str
    tools: List[Tool]
    potential_agents: List[potential_ai_agent]
    summarized_agents: List[AIAgentListing]
    ai_agents: List[
        AIAgentListing
    ]  # Final classified agents ready for database insertion


# 1st node
async def search_tools(state: AgentState, writer):
    writer(
        "Searching for tools that can be published as new listings in the directory ...\n"
    )
    result = await search_agent.run(state["latest_user_message"])

    writer("I have found the following tools: \n")
    writer("### Potential Listings Identified:  \n")
    for tool in result.data:
        writer(f"**{tool.name}**  \n*{tool.description}*  \n{tool.url}  \n \n")
    return {"tools": result.data}


# 2nd node
async def filter_ai_agents(state: AgentState, writer):
    # Get the latest message and deserialize it
    prompt = f"""
    The list of tools is: {state["tools"]}
    """
    print("filter ai agents prompt", prompt)
    writer("I will now proceed to filter the tools to only include the AI agents.\n\n")
    writer("Evaluating each agent...\n\n")

    result = await listing_filtering_agent.run(prompt)

    # Add summary message showing how many tools were detected as AI agents
    total_tools = len(state["tools"])
    total_ai_agents = len(result.data)
    writer(f"Found {total_ai_agents} AI agents out of {total_tools} tools. \n\n")

    # Format and display the potential AI agents
    writer("### AI Agents identified:  \n")
    for agent in result.data:
        confidence_percentage = agent.confidence * 100
        writer(f"**{agent.name}**  \n")
        writer(f"*Confidence Score: {confidence_percentage:.1f}%*  \n")
        writer(f"URL: {agent.url}  \n\n")

    print("The agents are: ", result.data)
    return {"potential_agents": result.data}


# 3rd node
async def summarize_ai_agents(state: AgentState, writer):
    writer(f"Summarizing the AI agents...\n\n")

    summarized_agents: List[AIAgentListing] = []

    for agent in state["potential_agents"]:
        prompt = f"""
        The agent to summarize is: {agent}
        """
        print(f"Summarizing agent: {agent}")
        result = await listing_summarizer_agent.run(prompt)

        if result.data:
            # Add the summarized agent(s) to our list - handling both single and list results
            summarized_agents.extend(
                result.data if isinstance(result.data, list) else [result.data]
            )
            print(f"Summarization result: {result.data}")

    # Add summary information
    total_potential_agents = len(state["potential_agents"])
    total_summarized = len(summarized_agents)
    writer(
        f"**Successfully summarized {total_summarized} AI agents out of {total_potential_agents} potential agents.**  \n"
    )

    # Format and display the summarized agents
    writer("## Summarized AI Agents:  \n")
    for agent in summarized_agents:
        writer(f"### {agent.name}  \n")
        writer(f"**{agent.short_description}**  \n")
        writer(f"{agent.long_description}  \n")

        writer("**Features:**  \n")
        for feature in agent.features:
            writer(f"- {feature}  \n")
        writer("\n")
        writer("**Use Cases:**  \n")
        for use_case in agent.use_cases:
            writer(f"- {use_case}  \n")
        writer("\n")

        # Display pricing tiers
        writer("**Pricing Tiers:**  \n")
        for price in agent.pricing_tiers:
            if price == 0.0:
                writer(f"- Free tier  \n")
            else:
                writer(f"- ${price:.2f}  \n")
        writer("\n")

        # Display source type information
        open_source_status = (
            "Open Source" if agent.source_type.is_open_source else "Closed Source"
        )
        confidence = agent.source_type.confidence_score * 100
        writer(f"**Source:** {open_source_status} (Confidence: {confidence:.1f}%)  \n")
        writer("\n")

        # Display URLs
        writer(f"**Website:** {agent.website_url}  \n")
        if hasattr(agent, "github_url") and agent.github_url:
            writer(f"**GitHub:** {agent.github_url}  \n")

            writer(f"**Logo URL:** {agent.logo_url}  \n")
        if hasattr(agent, "video_url") and agent.video_url:
            writer(f"**Demo Video:** {agent.video_url}  \n")

        writer("\n")  # Extra line break between agents

    return {
        "summarized_agents": summarized_agents,
    }


# 4th node
async def classify_ai_agents(state: AgentState, writer):
    writer(f"Classifying AI agents...\n\n")

    classified_agents: List[AIAgentListing] = []

    for agent in state["summarized_agents"]:
        prompt = f"""
        The agent to classify is: {agent}
        """
        print(f"Classifying agent: {agent}")
        result = await listing_classifier_agent.run(prompt)
        if result.data:
            # Ensure we're only adding AIAgentListing objects
            if isinstance(result.data, list):
                for item in result.data:
                    if isinstance(item, AIAgentListing):
                        classified_agents.append(item)
            elif isinstance(result.data, AIAgentListing):
                classified_agents.append(result.data)

    total_summarized = len(state["summarized_agents"])
    total_classified = len(classified_agents)
    writer(
        f"**Successfully classified {total_classified} AI agents out of {total_summarized} summarized agents.**\n\n"
    )

    # Format and display only the agent name and categorization
    writer("## Classified AI Agents:\n")
    for agent in classified_agents:
        writer(f"### {agent.name}\n")

        # Display only category information
        writer(
            f"**Category:** {agent.category_score.category_name} (Confidence: {agent.category_score.score * 100:.1f}%)\n\n"
        )

        # Display only tag information
        if hasattr(agent, "tag_scores") and agent.tag_scores:
            writer("**Tags:**\n")
            for tag in agent.tag_scores:
                confidence_percentage = tag.score * 100
                writer(f"- {tag.tag_name} (Confidence: {confidence_percentage:.1f}%)\n")
            writer("\n \n")

    print("All agents classified:", classified_agents)
    writer("What do you think about the AI agents? \n \n")
    writer(
        "Provide feedback so that I modify them or that i proceed them to publish them in the directory. \n \n"
    )
    return {"ai_agents": classified_agents}


# 5th node - Interrupt the graph to get the user's feedback on the classified agents
def get_user_feedback(state: AgentState, writer):
    # Get the user feedback using interrupt
    user_input = interrupt("Provide feedback.")

    # Return a dictionary with all required state fields, updating only the user message
    return {
        "latest_user_message": user_input,
    }


# 6th node - Determine if user feedback requires rectification or if we can proceed to database insertion
async def route_user_feedback(state: AgentState, writer):
    prompt = f"""
    The user has sent a message: 
    
    {state["latest_user_message"]}

    If the user wants to end the conversation, respond with just the text "finish_conversation".
    If the user wants to continue coding the AI agent, respond with just the text "coder_agent".
    """

    result = await feedback_router.run(prompt)
    next_action = result.data

    if next_action == "rectify_listing":
        writer("I will now proceed to rectify the listings. \n \n")
        return "rectify_listing"
    else:
        writer("I will now proceed to publish the listings. \n \n")
        return "insert_listing"


# 7th node - Modify listings based on user feedback
async def listing_rectifier(state: AgentState, writer):
    prompt = f"""
    The user feedback is: 
    
    {state["latest_user_message"]}
    
    The current state of the listings to be published before correction: 
    {state["ai_agents"]}
    
    """

    result = await listing_rectifier_agent.run(prompt)
    rectified_agents = result.data

    writer("Based on your feedback, I've made the following changes:\n\n")

    for agent in rectified_agents:
        writer(f"### {agent.name}\n")
        writer(f"**Description:** {agent.short_description}\n")
        writer(f"{agent.long_description}\n\n")

        writer("**Features:**\n")
        for feature in agent.features:
            writer(f"- {feature}\n")
        writer("\n")

        writer("**Use Cases:**\n")
        for use_case in agent.use_cases:
            writer(f"- {use_case}\n")
        writer("\n")

        # Display pricing tiers
        writer("**Pricing Tiers:**\n")
        for price in agent.pricing_tiers:
            if price == 0.0:
                writer(f"- Free tier\n")
            else:
                writer(f"- ${price:.2f}\n")
        writer("\n")

        # Display category
        writer(
            f"**Category:** {agent.category_score.category_name} (Confidence: {agent.category_score.score * 100:.1f}%)\n\n"
        )

        # Display tags
        if hasattr(agent, "tag_scores") and agent.tag_scores:
            writer("**Tags:**\n")
            for tag in agent.tag_scores:
                confidence_percentage = tag.score * 100
                writer(f"- {tag.tag_name} (Confidence: {confidence_percentage:.1f}%)\n")
            writer("\n")

        # Display URLs
        writer(f"**Website:** {agent.website_url}\n")
        if hasattr(agent, "github_url") and agent.github_url:
            writer(f"**GitHub:** {agent.github_url}\n")

        if hasattr(agent, "video_url") and agent.video_url:
            writer(f"**Demo Video:** {agent.video_url}\n")
        writer("\n")

    writer("I've rectified the listings based on your feedback.\n\n")
    writer(
        "Is there anything else you would like to change about the listings? Or should I proceed to insert them into the database?\n\n"
    )

    return {"ai_agents": rectified_agents}


# 8th node
async def insert_listing(state: AgentState, writer):
    insertion_results = []

    writer("Publishing the listings...\n\n")

    for agent in state["ai_agents"]:
        prompt = f"""
        The agent to insert is: {agent}
        """
        print(f"Inserting agent: {agent.name}")
        result = await db_inserter_agent.run(prompt)

        # Get the success and name directly from the result
        # InsertionResult will have success and name fields
        success = result.data.success
        name = result.data.name

        # Add to our results tracking
        insertion_results.append({"name": name, "success": success})

        # Write information about each insertion
        writer(f"#### Publishing: {name}...\n")
        if success:
            writer(f"✅ **Success!** Agent has been published.\n\n")
        else:
            writer(f"❌ **Failed!** Agent could not be added to the database.\n\n")

        print(f"Insertion result for agent {name}: success={success}")

    writer("## Summary\n\n")
    successful_insertions = sum(1 for result in insertion_results if result["success"])
    total_insertions = len(insertion_results)

    writer(
        f"Successfully published {successful_insertions} out of {total_insertions} listings.\n\n"
    )

    if successful_insertions == total_insertions:
        writer(
            "🎉 All agents were successfully added to the directory! They will now be visible in [BestAIAgents](http://localhost:3000/)\n\n"
        )
    else:
        writer(
            "⚠️ Some agents could not be added. Please review the errors above and try again.\n\n"
        )

    print("All agents inserted. Results:", insertion_results)
    return {}


# Build workflow
builder = StateGraph(AgentState)

builder.add_node("Search Agent", search_tools)
builder.add_node("Listing Filtering Agent", filter_ai_agents)
builder.add_node("Summarizer Agent", summarize_ai_agents)
builder.add_node("Listing Classifier Agent", classify_ai_agents)
builder.add_node("Feedback Collector", get_user_feedback)
builder.add_node("Publisher Agent", insert_listing)
builder.add_node("Listing Rectifier Agent", listing_rectifier)

builder.add_edge(START, "Search Agent")
builder.add_edge("Search Agent", "Listing Filtering Agent")
builder.add_edge("Listing Filtering Agent", "Summarizer Agent")
builder.add_edge("Summarizer Agent", "Listing Classifier Agent")
builder.add_edge("Listing Classifier Agent", "Feedback Collector")
builder.add_conditional_edges(
    "Feedback Collector",
    route_user_feedback,
    {
        "rectify_listing": "Listing Rectifier Agent",
        "insert_listing": "Publisher Agent",
    },
)
builder.add_edge("Listing Rectifier Agent", "Feedback Collector")
builder.add_edge("Publisher Agent", END)


# Configure persistence
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
