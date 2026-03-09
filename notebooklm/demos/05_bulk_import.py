"""
05_bulk_import.py — Bulk source import via ADK.

Uses BulkImportAgent (BaseAgent) to concurrently import multiple sources
into a single notebook with error handling and status reporting.
"""

import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from notebooklm.agents import BulkImportAgent
from notebooklm.tools import shutdown_client, ask_question, delete_notebook

# Sources to import
SOURCES = [
    {"type": "url", "content": "https://en.wikipedia.org/wiki/Statistical_variable", "label": "StatVar Wikipedia"},
    {"type": "url", "content": "https://en.wikipedia.org/wiki/Schema.org", "label": "Schema.org Wikipedia"},
    {"type": "url", "content": "https://docs.datacommons.org/api/rest/v2", "label": "Data Commons REST API"},
    {"type": "youtube", "content": "https://www.youtube.com/watch?v=ByT27rl1gzU", "label": "Data Commons intro video"},
    {
        "type": "text",
        "content": (
            "A PVMAP (Property-Value Map) defines how to transform source data columns "
            "into Data Commons StatVarObservations. Each row maps a data key to property-value pairs. "
            "Special placeholders like [DATA] pass through values and [NUMBER] passes numeric values."
        ),
        "label": "PVMAP explanation",
    },
    {
        "type": "text",
        "content": (
            "Schema.org provides a shared vocabulary for structured data on the internet. "
            "Data Commons extends Schema.org with statistical types like StatisticalVariable, "
            "StatVarObservation, and properties like measuredProperty, populationType."
        ),
        "label": "Schema.org + DC explanation",
    },
]


async def main():
    agent = BulkImportAgent(name="BulkImporter")
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="notebooklm_bulk", session_service=session_service)

    session = await session_service.create_session(
        app_name="notebooklm_bulk",
        user_id="user",
        state={
            "notebook_name": "Bulk Import Demo",
            "sources": SOURCES,
        },
    )

    print(f"Starting bulk import of {len(SOURCES)} sources via ADK BulkImportAgent...\n")

    notebook_id = None
    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message="Import all the sources.",
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{event.author}] {part.text}\n")

    # Read back state for follow-up
    updated_session = await session_service.get_session(
        app_name="notebooklm_bulk", user_id="user", session_id=session.id
    )
    notebook_id = updated_session.state.get("notebook_id") if updated_session else None

    # Quick verification: ask a summary question
    if notebook_id:
        print("--- Verification ---")
        result = await ask_question(
            notebook_id, "Briefly summarize what topics these sources cover."
        )
        if result["success"]:
            print(f"Summary: {result['data']['answer'][:500]}\n")

        # Cleanup
        await delete_notebook(notebook_id)
        print(f"Cleaned up notebook {notebook_id}")

    await shutdown_client()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
