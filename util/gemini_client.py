"""
Gemini API client utility for processing generated output.

This module provides a client for interacting with Google's Gemini API
using the API key from the .env file.

Usage:
    python -m util.gemini_client --model gemini-3-pro-preview "Your prompt here"
"""

import argparse
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError(
        "google-genai package is required. "
        "Install it with: pip install google-genai"
    )


def load_gemini_api_key() -> str:
    """Load the Gemini API key from the .env file.

    Returns:
        str: The Gemini API key.

    Raises:
        ValueError: If GEMINI_API_KEY is not found in environment.
    """
    # Find the .env file (look in project root)
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"

    # Read directly from .env file (ignores shell environment)
    env_vars = dotenv_values(env_path)
    api_key = env_vars.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found in environment. "
            "Please add it to your .env file."
        )

    return api_key.strip()


class GeminiClient:
    """Client for interacting with Google's Gemini 3 Pro API."""

    DEFAULT_MODEL = "gemini-3-pro-preview"

    def __init__(self, model_name: Optional[str] = None):
        """Initialize the Gemini client.

        Args:
            model_name: The Gemini model to use. Defaults to gemini-3-pro-preview.
        """
        self.api_key = load_gemini_api_key()
        self.model_name = model_name or self.DEFAULT_MODEL

        # Initialize the client
        self.client = genai.Client(api_key=self.api_key)

    def generate_content(
        self,
        prompt: str,
        temperature: float = 0,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """Generate content using the Gemini model.

        Args:
            prompt: The input prompt to send to the model.
            temperature: Controls randomness (0.0-1.0). Lower = more deterministic.
            max_output_tokens: Maximum number of tokens in the response.

        Returns:
            str: The generated text response.
        """
        config_params = {"temperature": temperature}
        if max_output_tokens:
            config_params["max_output_tokens"] = max_output_tokens

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_params),
        )

        return response.text

    def generate_content_with_metadata(
        self,
        prompt: str,
        temperature: float = 0,
        max_output_tokens: Optional[int] = None,
    ) -> dict:
        """Generate content and return full metadata.

        Args:
            prompt: The input prompt to send to the model.
            temperature: Controls randomness (0.0-1.0). Lower = more deterministic.
            max_output_tokens: Maximum number of tokens in the response.

        Returns:
            dict with keys:
             - text: Generated text
             - model: Model name
             - temperature: Temperature used
             - max_tokens: Max tokens setting
             - start_time: ISO timestamp
             - end_time: ISO timestamp
             - duration_ms: Duration in milliseconds
             - prompt_tokens: Prompt token count (if available)
             - response_tokens: Response token count (if available)
             - total_tokens: Total token count (if available)
        """
        from datetime import datetime
        import time

        start_time = datetime.now()
        start_ms = time.time() * 1000

        config_params = {"temperature": temperature}
        if max_output_tokens:
            config_params["max_output_tokens"] = max_output_tokens

        # Enable thinking output
        config_params["thinking_config"] = types.ThinkingConfig(
            include_thoughts=True
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_params),
        )

        end_time = datetime.now()
        end_ms = time.time() * 1000
        duration_ms = int(end_ms - start_ms)

        # Extract token usage if available
        prompt_tokens = None
        response_tokens = None
        total_tokens = None
        thoughts_tokens = None

        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            prompt_tokens = getattr(usage, 'prompt_token_count', None)
            response_tokens = getattr(usage, 'candidates_token_count', None)
            total_tokens = getattr(usage, 'total_token_count', None)
            thoughts_tokens = getattr(usage, 'thoughts_token_count', None)

        # Extract thinking/reasoning content from response parts
        thinking_content = []
        output_content = []

        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                    for part in candidate.content.parts:
                        # Check if this is a thinking part
                        is_thought = getattr(part, 'thought', False)
                        part_text = getattr(part, 'text', None)

                        if part_text:
                            if is_thought:
                                thinking_content.append(part_text)
                            else:
                                output_content.append(part_text)

        return {
            'text': response.text if response.text else None,
            'model': self.model_name,
            'temperature': temperature,
            'max_tokens': max_output_tokens,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_ms': duration_ms,
            'prompt_tokens': prompt_tokens,
            'response_tokens': response_tokens,
            'total_tokens': total_tokens,
            'thoughts_tokens': thoughts_tokens,
            'thinking_content': thinking_content,  # List of thinking/reasoning parts
            'output_content': output_content,      # List of output parts
        }

    def process_output(
        self,
        content: str,
        instruction: str = "Analyze and summarize the following content:",
    ) -> str:
        """Process generated output with a specific instruction.

        Args:
            content: The content to process.
            instruction: The instruction for how to process the content.

        Returns:
            str: The processed output from Gemini.
        """
        prompt = f"{instruction}\n\n{content}"
        return self.generate_content(prompt)

    def chat(self, messages: list[dict]) -> str:
        """Have a multi-turn conversation with the model.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                     Roles can be 'user' or 'model'.

        Returns:
            str: The model's response to the conversation.
        """
        # Convert messages to the new format
        contents = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            contents.append(types.Content(role=role, parts=[types.Part(text=content)]))

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
        )

        return response.text if response else ""


def quick_generate(prompt: str, model_name: Optional[str] = None) -> str:
    """Convenience function for one-off generation.

    Args:
        prompt: The input prompt.
        model_name: Optional model name override.

    Returns:
        str: The generated response.
    """
    client = GeminiClient(model_name=model_name)
    return client.generate_content(prompt)


def main():
    """Command-line interface for the Gemini client."""
    parser = argparse.ArgumentParser(
        description="Generate content using Google's Gemini API"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to send to the model",
    )
    parser.add_argument(
        "--model", "-m",
        default=GeminiClient.DEFAULT_MODEL,
        help=f"The Gemini model to use (default: {GeminiClient.DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.0,
        help="Temperature for generation (0.0-1.0, default: 0.0)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum output tokens (default: no limit)",
    )

    args = parser.parse_args()

    if not args.prompt:
        parser.print_help()
        return

    client = GeminiClient(model_name=args.model)
    response = client.generate_content(
        args.prompt,
        temperature=args.temperature,
        max_output_tokens=args.max_tokens,
    )
    print(response)


if __name__ == "__main__":
    main()
