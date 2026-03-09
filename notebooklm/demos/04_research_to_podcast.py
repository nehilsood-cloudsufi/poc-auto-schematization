"""
04_research_to_podcast.py — Research-to-podcast pipeline via ADK.

Uses PodcastPipelineAgent (BaseAgent) for a deterministic workflow:
create notebook -> deep research -> ask questions -> generate podcast -> download.

Usage:
    python 04_research_to_podcast.py "quantum computing advances 2025"
    python 04_research_to_podcast.py "impact of AI on healthcare"
"""

import asyncio
import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from notebooklm.agents import PodcastPipelineAgent
from notebooklm.tools import shutdown_client


async def main():
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "advances in fusion energy 2025"
    print(f"Topic: {topic}\n")

    agent = PodcastPipelineAgent(name="PodcastPipeline")
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="notebooklm_podcast", session_service=session_service)

    session = await session_service.create_session(
        app_name="notebooklm_podcast",
        user_id="user",
        state={"topic": topic, "output_dir": "podcast_output"},
    )

    print("Starting podcast pipeline via ADK PodcastPipelineAgent...\n")

    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=f"Generate a research podcast about: {topic}",
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{event.author}] {part.text}\n")

    await shutdown_client()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
