"""Login to NotebookLM using system Chrome (for Cloudtop/CRD security key support).

Chrome Remote Desktop forwards security key challenges to the system Chrome,
but NOT to Playwright's bundled Chromium. This script uses Playwright with
channel="chrome" to launch the system Chrome instead.

Usage:
    python3 cloudtop_login.py
"""

import asyncio
import os
from pathlib import Path


STORAGE_DIR = Path.home() / ".notebooklm"
STORAGE_STATE = STORAGE_DIR / "storage_state.json"
NOTEBOOKLM_URL = "https://notebooklm.google.com/"


async def login():
    from playwright.async_api import async_playwright

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    print("Opening system Chrome for Google sign-in...")
    print("Sign in with your @google.com account and tap your security key.")
    print("After sign-in completes, close the browser or press Ctrl+C.\n")

    async with async_playwright() as p:
        # Use system Chrome (channel="chrome") instead of bundled Chromium.
        # This is critical: CRD security key forwarding only works with system Chrome.
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
        )
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(NOTEBOOKLM_URL)

        # Wait for the user to complete sign-in.
        # NotebookLM redirects to the main page after successful auth.
        print("Waiting for sign-in to complete...")
        try:
            await page.wait_for_url("**/notebook/**", timeout=300_000)
            print("Sign-in detected (notebook page loaded).")
        except Exception:
            # If they don't navigate to a notebook, just wait for the main page
            try:
                await page.wait_for_url("https://notebooklm.google.com/**", timeout=10_000)
            except Exception:
                pass

        # Give a moment for cookies to settle
        await asyncio.sleep(2)

        # Save the browser state (cookies + localStorage)
        await context.storage_state(path=str(STORAGE_STATE))
        print(f"\nAuth saved to {STORAGE_STATE}")

        await browser.close()


def main():
    try:
        asyncio.run(login())
        if STORAGE_STATE.exists():
            print(f"\nSuccess! Storage state saved to {STORAGE_STATE}")
            print(f"File size: {STORAGE_STATE.stat().st_size} bytes")
        else:
            print("\nWarning: storage_state.json was not created.")
    except KeyboardInterrupt:
        print("\nLogin cancelled.")


if __name__ == "__main__":
    main()
