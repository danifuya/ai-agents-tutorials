import os
import asyncio
from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from graph_builder import build_graph

# Load environment variables before any other imports
load_dotenv()


async def run_local_chat(graph, user_message: str, from_number: str):
    """
    Example CLI loop for local development and debugging.
    """
    thread_id = from_number

    # Get the current state from the graph using the thread_id
    config = {"configurable": {"thread_id": thread_id}}

    # We call graph.stream w/ the same thread_id to preserve context
    result = await graph.ainvoke(
        {
            "latest_user_message": user_message,
        },
        config,
        stream_mode="custom",
    )
    # Process the chunks from the agent
    return result[-1]


async def run_agent(user_message: str, from_number: str) -> str:
    async with AsyncConnectionPool(
        conninfo=f"postgres://{os.getenv('SUPABASE_DB_USER')}:{os.getenv('SUPABASE_DB_PASSWORD')}"
        f"@{os.getenv('SUPABASE_DB_HOST')}:{os.getenv('SUPABASE_DB_PORT')}/{os.getenv('SUPABASE_DB_NAME')}"
        f"?sslmode=require",
        max_size=20,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,  # Disable automatic prepared statements
            "row_factory": dict_row,
        },
    ) as pool:
        async with pool.connection() as conn:
            memory = AsyncPostgresSaver(conn)
            await memory.setup()

            # Build and run the graph
            graph = build_graph(checkpointer=memory)

            # Properly consume the async generator
            response = await run_local_chat(graph, user_message, from_number)
            print(f"Agent response: {response}")
            return response


if __name__ == "__main__":
    from_number = "12222"  # Use a fixed number for the conversation

    async def main_loop():
        while True:
            try:
                user_input = input("User: ")
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                await run_agent(user_input, from_number)
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
                import traceback

                traceback.print_exc()

    # Run the async main loop
    asyncio.run(main_loop())
