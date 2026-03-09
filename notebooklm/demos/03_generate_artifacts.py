"""
03_generate_artifacts.py — Content generation via ADK.

Uses ResearchAgent to create a notebook with sources, then generate
multiple artifact types: audio, video, report, quiz.
"""

import asyncio
import os

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from notebooklm.agents import create_research_agent
from notebooklm.tools import shutdown_client

OUTPUT_DIR = "artifacts_output"


async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    agent = create_research_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="notebooklm_artifacts", session_service=session_service)

    session = await session_service.create_session(
        app_name="notebooklm_artifacts",
        user_id="user",
    )

    message = (
        f"Create a notebook called 'Artifacts Demo'. "
        f"Add these two URL sources (wait for each to finish):\n"
        f"1. https://en.wikipedia.org/wiki/Climate_change\n"
        f"2. https://en.wikipedia.org/wiki/Renewable_energy\n\n"
        f"Then generate the following artifacts:\n"
        f"1. A deep-dive medium-length audio podcast focused on the intersection "
        f"of climate change and renewable energy. Download it to '{OUTPUT_DIR}/podcast.mp3'.\n"
        f"2. A report/briefing about the key findings. Download it to '{OUTPUT_DIR}/briefing.md'.\n"
        f"3. A medium-difficulty quiz. Download it to '{OUTPUT_DIR}/quiz.json'.\n\n"
        f"Finally, delete the notebook."
    )

    print("Starting artifact generation demo via ADK ResearchAgent...\n")

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
    print(f"\nArtifacts saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
