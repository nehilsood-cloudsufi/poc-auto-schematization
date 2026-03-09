"""
02_sources_and_chat.py — Source management and multi-turn chat via ADK.

Uses ResearchAgent with multi-turn conversation to add diverse sources
and ask follow-up questions.
"""

import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from notebooklm.agents import create_research_agent
from notebooklm.tools import shutdown_client

SAMPLE_TEXT = """\
Data Commons is an open knowledge graph that aggregates data from many
public datasets. It provides a unified schema based on Schema.org to
represent statistical observations. Each observation has a variable
(StatisticalVariable), a place (observationAbout), a date
(observationDate), and a value. The schema uses properties like
measuredProperty, populationType, and constraintProperties to define
what each statistical variable measures."""


async def main():
    agent = create_research_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="notebooklm_chat", session_service=session_service)

    session = await session_service.create_session(
        app_name="notebooklm_chat",
        user_id="user",
    )

    # Turn 1: Create notebook and add sources
    turn1 = (
        "Create a notebook called 'Sources & Chat Demo'. Then add these sources:\n"
        "1. URL: https://docs.datacommons.org/api/\n"
        "2. YouTube: https://www.youtube.com/watch?v=ByT27rl1gzU\n"
        f"3. Text: {SAMPLE_TEXT}"
    )

    # Turn 2: Ask a question
    turn2 = "What is Data Commons and what problem does it solve?"

    # Turn 3: Follow-up
    turn3 = "How does its schema represent statistical observations?"

    # Turn 4: Cleanup
    turn4 = "Great, now delete the notebook to clean up."

    turns = [turn1, turn2, turn3, turn4]

    print("Starting multi-turn chat demo via ADK ResearchAgent...\n")

    for i, message in enumerate(turns, 1):
        print(f"--- Turn {i} ---")
        print(f"User: {message[:100]}{'...' if len(message) > 100 else ''}\n")

        async for event in runner.run_async(
            user_id="user",
            session_id=session.id,
            new_message=message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"[{event.author}] {part.text}\n")

    await shutdown_client()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
