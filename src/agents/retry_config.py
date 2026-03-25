"""Shared retry configuration for Gemini API calls.

Provides aggressive exponential backoff for transient API errors (429, 500, etc.)
that go beyond the google-genai built-in retry defaults (2 retries, 0.5s initial).

Used by:
- All ADK LlmAgent creation sites (via create_resilient_model)
- GeminiClient direct API calls (via DEFAULT_RETRY_OPTIONS)
"""

from google.adk.models import Gemini
from google.genai import types

DEFAULT_RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=7,           # Up to 7 total attempts
    initial_delay=5.0,    # Start with 5s
    max_delay=60.0,       # Cap at 60s
    exp_base=2.0,         # Double each time: 5→10→20→40→60→60
    jitter=1.0,           # Add randomization
    http_status_codes=[408, 429, 500, 502, 503, 504],
)


def create_resilient_model(model: str) -> Gemini:
    """Wrap a model name string into a Gemini instance with retry options.

    ADK LlmAgent accepts either a plain model string or a Gemini instance.
    This function converts the string form into a Gemini instance configured
    with aggressive retry/backoff so agents survive transient API errors.

    Args:
        model: Gemini model name (e.g., "gemini-2.5-flash")

    Returns:
        Gemini instance with retry_options configured
    """
    return Gemini(model=model, retry_options=DEFAULT_RETRY_OPTIONS)
