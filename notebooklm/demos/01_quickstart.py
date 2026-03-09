"""
01_quickstart.py — End-to-end NotebookLM basics via ADK.

Uses ResearchAgent with a single-turn instruction to:
create notebook -> add URL source -> ask question -> generate audio -> cleanup.
"""

import asyncio

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from notebooklm.agents import create_research_agent
from notebooklm.tools import shutdown_client


async def main():
    agent = create_research_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="notebooklm_quickstart", session_service=session_service)

    session = await session_service.create_session(
        app_name="notebooklm_quickstart",
        user_id="user",
    )

    user_message = (
        "Create a notebook called 'Quickstart Demo', add this URL as a source: "
        "https://en.wikipedia.org/wiki/Large_language_model, "
        "then ask 'What are the key limitations of large language models?'. "
        "After that, generate a short audio overview and download it to 'quickstart_audio.mp3'. "
        "Finally, delete the notebook to clean up."
    )

    print("Starting quickstart demo via ADK ResearchAgent...\n")

    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=user_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{event.author}] {part.text}\n")

    await shutdown_client()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
