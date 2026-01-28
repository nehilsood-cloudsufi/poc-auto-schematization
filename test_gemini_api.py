#!/usr/bin/env python3
"""Simple script to test Gemini API connectivity with different models."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# Get API key
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY")
    exit(1)

print(f"API Key found: {api_key[:10]}...")

# Test with google-genai library
from google import genai

client = genai.Client(api_key=api_key)

models_to_test = [
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

for model in models_to_test:
    print(f"\nTesting {model}...")
    try:
        response = client.models.generate_content(
            model=model,
            contents="Say hello in one word."
        )
        print(f"  SUCCESS: {response.text.strip()}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__} - {str(e)[:100]}")
