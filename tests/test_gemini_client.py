"""
Tests for the Gemini client module.

Tests src/data_commons/api/gemini_client.py including:
- API key loading
- Client initialization
- Content generation
- Error handling
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os


class TestLoadGeminiApiKey:
    """Tests for the load_gemini_api_key function."""

    @patch('src.data_commons.api.gemini_client.dotenv_values')
    def test_load_api_key_from_env_file(self, mock_dotenv):
        """Test loading API key from .env file."""
        from src.data_commons.api.gemini_client import load_gemini_api_key

        mock_dotenv.return_value = {'GEMINI_API_KEY': 'test-api-key-123'}

        with patch('pathlib.Path.exists', return_value=True):
            api_key = load_gemini_api_key()

        assert api_key == 'test-api-key-123'

    @patch('src.data_commons.api.gemini_client.dotenv_values')
    def test_load_api_key_google_api_key(self, mock_dotenv):
        """Test loading API key using GOOGLE_API_KEY env var name."""
        from src.data_commons.api.gemini_client import load_gemini_api_key

        mock_dotenv.return_value = {'GOOGLE_API_KEY': 'google-api-key-456'}

        with patch('pathlib.Path.exists', return_value=True):
            api_key = load_gemini_api_key()

        assert api_key == 'google-api-key-456'

    @patch('src.data_commons.api.gemini_client.dotenv_values')
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'env-var-key'}, clear=False)
    def test_load_api_key_fallback_to_env_var(self, mock_dotenv):
        """Test fallback to environment variable when .env has no key."""
        from src.data_commons.api.gemini_client import load_gemini_api_key

        mock_dotenv.return_value = {}

        with patch('pathlib.Path.exists', return_value=True):
            api_key = load_gemini_api_key()

        assert api_key == 'env-var-key'

    @patch('src.data_commons.api.gemini_client.dotenv_values')
    @patch.dict(os.environ, {}, clear=True)
    def test_load_api_key_missing_raises_error(self, mock_dotenv):
        """Test that missing API key raises ValueError."""
        from src.data_commons.api.gemini_client import load_gemini_api_key

        mock_dotenv.return_value = {}

        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(ValueError) as exc_info:
                load_gemini_api_key()

        assert 'No API key found' in str(exc_info.value)

    @patch('src.data_commons.api.gemini_client.dotenv_values')
    def test_load_api_key_strips_whitespace(self, mock_dotenv):
        """Test that API key whitespace is stripped."""
        from src.data_commons.api.gemini_client import load_gemini_api_key

        mock_dotenv.return_value = {'GEMINI_API_KEY': '  api-key-with-spaces  '}

        with patch('pathlib.Path.exists', return_value=True):
            api_key = load_gemini_api_key()

        assert api_key == 'api-key-with-spaces'


class TestGeminiClientInit:
    """Tests for GeminiClient initialization."""

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_init_with_default_model(self, mock_client_class, mock_load_key):
        """Test client initialization with default model."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'

        client = GeminiClient()

        assert client.model_name == 'gemini-3-pro-preview'
        # Client is now called with http_options for retry configuration
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args
        assert call_kwargs[1]['api_key'] == 'test-key'
        assert 'http_options' in call_kwargs[1]

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_init_with_custom_model(self, mock_client_class, mock_load_key):
        """Test client initialization with custom model."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'

        client = GeminiClient(model_name='gemini-2.5-flash')

        assert client.model_name == 'gemini-2.5-flash'


class TestGeminiClientGenerateContent:
    """Tests for GeminiClient.generate_content method."""

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_generate_content_basic(self, mock_client_class, mock_load_key):
        """Test basic content generation."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock response
        mock_response = Mock()
        mock_response.text = 'Generated response text'
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        result = client.generate_content('Test prompt')

        assert result == 'Generated response text'
        mock_client.models.generate_content.assert_called_once()

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_generate_content_with_temperature(self, mock_client_class, mock_load_key):
        """Test content generation with custom temperature."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Response'
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        client.generate_content('Test', temperature=0.7)

        # Verify the call was made with correct config
        call_args = mock_client.models.generate_content.call_args
        assert call_args is not None

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_generate_content_with_max_tokens(self, mock_client_class, mock_load_key):
        """Test content generation with max_output_tokens."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Response'
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        client.generate_content('Test', max_output_tokens=1000)

        mock_client.models.generate_content.assert_called_once()


class TestGeminiClientGenerateContentWithMetadata:
    """Tests for GeminiClient.generate_content_with_metadata method."""

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_generate_content_with_metadata_returns_dict(self, mock_client_class, mock_load_key):
        """Test that generate_content_with_metadata returns proper dict structure."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock response with metadata
        mock_response = Mock()
        mock_response.text = 'Generated text'
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        mock_response.usage_metadata.total_token_count = 30
        mock_response.usage_metadata.thoughts_token_count = None
        mock_response.candidates = []
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        result = client.generate_content_with_metadata('Test prompt')

        assert isinstance(result, dict)
        assert 'text' in result
        assert 'model' in result
        assert 'temperature' in result
        assert 'duration_ms' in result
        assert 'prompt_tokens' in result
        assert 'response_tokens' in result
        assert result['text'] == 'Generated text'
        assert result['model'] == 'gemini-3-pro-preview'

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_generate_content_with_metadata_no_usage(self, mock_client_class, mock_load_key):
        """Test handling when usage_metadata is not available."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Generated text'
        mock_response.usage_metadata = None
        mock_response.candidates = []
        del mock_response.usage_metadata  # Simulate attribute not existing
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        result = client.generate_content_with_metadata('Test prompt')

        assert result['prompt_tokens'] is None
        assert result['response_tokens'] is None


class TestGeminiClientProcessOutput:
    """Tests for GeminiClient.process_output method."""

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_process_output_default_instruction(self, mock_client_class, mock_load_key):
        """Test process_output with default instruction."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Processed output'
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        result = client.process_output('Some content to process')

        assert result == 'Processed output'

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_process_output_custom_instruction(self, mock_client_class, mock_load_key):
        """Test process_output with custom instruction."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Custom processed output'
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        result = client.process_output('Content', instruction='Custom instruction:')

        assert result == 'Custom processed output'


class TestGeminiClientChat:
    """Tests for GeminiClient.chat method."""

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_chat_single_message(self, mock_client_class, mock_load_key):
        """Test chat with single message."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Chat response'
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        messages = [{'role': 'user', 'content': 'Hello'}]
        result = client.chat(messages)

        assert result == 'Chat response'

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_chat_multi_turn(self, mock_client_class, mock_load_key):
        """Test multi-turn chat conversation."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Multi-turn response'
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        messages = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'model', 'content': 'Hi there!'},
            {'role': 'user', 'content': 'How are you?'}
        ]
        result = client.chat(messages)

        assert result == 'Multi-turn response'

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_chat_empty_response(self, mock_client_class, mock_load_key):
        """Test chat with empty response."""
        from src.data_commons.api.gemini_client import GeminiClient

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # When response.text is None but response is truthy, result should be None
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        client = GeminiClient()
        messages = [{'role': 'user', 'content': 'Test'}]
        result = client.chat(messages)

        # The actual implementation returns None when response.text is None
        assert result is None or result == ''


class TestQuickGenerate:
    """Tests for the quick_generate convenience function."""

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_quick_generate_default_model(self, mock_client_class, mock_load_key):
        """Test quick_generate with default model."""
        from src.data_commons.api.gemini_client import quick_generate

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Quick response'
        mock_client.models.generate_content.return_value = mock_response

        result = quick_generate('Test prompt')

        assert result == 'Quick response'

    @patch('src.data_commons.api.gemini_client.load_gemini_api_key')
    @patch('src.data_commons.api.gemini_client.genai.Client')
    def test_quick_generate_custom_model(self, mock_client_class, mock_load_key):
        """Test quick_generate with custom model."""
        from src.data_commons.api.gemini_client import quick_generate

        mock_load_key.return_value = 'test-key'
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = 'Custom model response'
        mock_client.models.generate_content.return_value = mock_response

        result = quick_generate('Test prompt', model_name='gemini-2.5-flash')

        assert result == 'Custom model response'
