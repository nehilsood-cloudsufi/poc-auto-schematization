"""
Test script for the Gemini client utility.

Run this script to verify the Gemini API integration is working correctly.
Usage: python -m test.test_gemini_client
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from util.gemini_client import GeminiClient, quick_generate, load_gemini_api_key


def test_api_key_loading():
    """Test that the API key loads correctly from .env file."""
    print("=" * 50)
    print("Test 1: Loading API key from .env")
    print("=" * 50)

    try:
        api_key = load_gemini_api_key()
        # Only show first/last few characters for security
        masked_key = f"{api_key[:8]}...{api_key[-4:]}"
        print(f"API key loaded successfully: {masked_key}")
        print("PASSED\n")
        return True
    except Exception as e:
        print(f"FAILED: {e}\n")
        return False


def test_client_initialization():
    """Test that the GeminiClient initializes correctly."""
    print("=" * 50)
    print("Test 2: Client initialization")
    print("=" * 50)

    try:
        client = GeminiClient()
        print(f"Client initialized with model: {client.model_name}")
        print("PASSED\n")
        return True
    except Exception as e:
        print(f"FAILED: {e}\n")
        return False


def test_simple_generation():
    """Test a simple content generation request."""
    print("=" * 50)
    print("Test 3: Simple content generation")
    print("=" * 50)

    try:
        client = GeminiClient()
        prompt = "What is 2 + 2? Reply with just the number."
        print(f"Prompt: {prompt}")

        response = client.generate_content(prompt, temperature=0.0)
        print(f"Response: {response.strip()}")
        print("PASSED\n")
        return True
    except Exception as e:
        print(f"FAILED: {e}\n")
        return False


def test_process_output():
    """Test the process_output method for analyzing content."""
    print("=" * 50)
    print("Test 4: Process output functionality")
    print("=" * 50)

    try:
        client = GeminiClient()
        content = """
        Sales data for Q4 2025:
        - Product A: $50,000
        - Product B: $75,000
        - Product C: $25,000
        """
        instruction = "Summarize this data in one sentence."

        print(f"Content: {content.strip()}")
        print(f"Instruction: {instruction}")

        response = client.process_output(content, instruction)
        print(f"Response: {response.strip()}")
        print("PASSED\n")
        return True
    except Exception as e:
        print(f"FAILED: {e}\n")
        return False


def test_quick_generate():
    """Test the convenience quick_generate function."""
    print("=" * 50)
    print("Test 5: Quick generate function")
    print("=" * 50)

    try:
        prompt = "Say 'Hello, World!' and nothing else."
        print(f"Prompt: {prompt}")

        response = quick_generate(prompt)
        print(f"Response: {response.strip()}")
        print("PASSED\n")
        return True
    except Exception as e:
        print(f"FAILED: {e}\n")
        return False


def test_custom_model():
    """Test using a different model (gemini-3-pro-preview)."""
    print("=" * 50)
    print("Test 6: Custom model (gemini-3-pro-preview)")
    print("=" * 50)

    try:
        client = GeminiClient(model_name="gemini-3-pro-preview")
        print(f"Client initialized with model: {client.model_name}")

        prompt = "What is the capital of France? Reply with just the city name."
        response = client.generate_content(prompt, temperature=0.0)
        print(f"Prompt: {prompt}")
        print(f"Response: {response.strip()}")
        print("PASSED\n")
        return True
    except Exception as e:
        print(f"FAILED: {e}\n")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("GEMINI CLIENT TEST SUITE")
    print("=" * 50 + "\n")

    tests = [
        ("API Key Loading", test_api_key_loading),
        ("Client Initialization", test_client_initialization),
        ("Simple Generation", test_simple_generation),
        ("Process Output", test_process_output),
        ("Quick Generate", test_quick_generate),
        ("Custom Model", test_custom_model),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"Unexpected error in {name}: {e}")
            results.append((name, False))

    # Summary
    print("=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\nAll tests passed!")
        return 0
    else:
        print("\nSome tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
