"""Tests for dc_api_wrapper.py — V2-only API, tenacity retry, validation."""

import urllib
from unittest.mock import MagicMock, patch

import pytest
import requests
from datacommons_client.utils.error_handling import (
    DCConnectionError,
    DCStatusError,
    APIError,
)

from src.data_commons.api.dc_api_wrapper import (
    _add_namespace,
    _get_exception_status_code,
    _should_retry_exception,
    _strip_namespace,
    _validate_v2_config,
    dc_api_merge_results,
    dc_api_wrapper,
    get_dc_api_key,
)


# --- _validate_v2_config ---


class TestValidateV2Config:
    def test_none_config_passes(self):
        _validate_v2_config(None)

    def test_empty_config_passes(self):
        _validate_v2_config({})

    def test_v2_config_passes(self):
        _validate_v2_config({'dc_api_version': 'V2'})

    def test_v1_config_raises(self):
        with pytest.raises(ValueError, match='Only V2 API is supported'):
            _validate_v2_config({'dc_api_version': 'V1'})

    def test_unknown_version_raises(self):
        with pytest.raises(ValueError):
            _validate_v2_config({'dc_api_version': 'V3'})


# --- get_dc_api_key ---


class TestGetDcApiKey:
    def test_key_from_config(self):
        assert get_dc_api_key({'dc_api_key': 'my-key'}) == 'my-key'

    @patch.dict('os.environ', {'DC_API_KEY': 'env-key'})
    def test_key_from_env(self):
        assert get_dc_api_key({}) == 'env-key'

    @patch.dict('os.environ', {}, clear=True)
    def test_fallback_to_default(self):
        key = get_dc_api_key({})
        # Should return the default key (non-empty)
        assert key and len(key) > 10


# --- _should_retry_exception ---


class TestShouldRetryException:
    def test_key_error_no_retry(self):
        assert _should_retry_exception(KeyError('missing')) is False

    def test_connection_error_retry(self):
        assert _should_retry_exception(DCConnectionError('timeout')) is True

    def test_timeout_retry(self):
        assert _should_retry_exception(
            requests.exceptions.Timeout('timeout')) is True

    def test_chunked_encoding_retry(self):
        assert _should_retry_exception(
            requests.exceptions.ChunkedEncodingError('err')) is True

    def test_http_500_retry(self):
        e = urllib.error.HTTPError(
            url='http://test', code=500, msg='error', hdrs={}, fp=None)
        assert _should_retry_exception(e) is True

    def test_http_429_retry(self):
        e = urllib.error.HTTPError(
            url='http://test', code=429, msg='rate limited', hdrs={}, fp=None)
        assert _should_retry_exception(e) is True

    def test_http_401_no_retry(self):
        e = urllib.error.HTTPError(
            url='http://test', code=401, msg='unauthorized', hdrs={}, fp=None)
        assert _should_retry_exception(e) is False

    def test_http_404_no_retry(self):
        e = urllib.error.HTTPError(
            url='http://test', code=404, msg='not found', hdrs={}, fp=None)
        assert _should_retry_exception(e) is False

    def test_dc_status_error_500_retry(self):
        e = DCStatusError('server error')
        e.status_code = 503
        assert _should_retry_exception(e) is True

    def test_dc_status_error_400_no_retry(self):
        e = DCStatusError('bad request')
        e.status_code = 400
        assert _should_retry_exception(e) is False


# --- _get_exception_status_code ---


class TestGetExceptionStatusCode:
    def test_http_error_code(self):
        e = urllib.error.HTTPError(
            url='http://test', code=503, msg='error', hdrs={}, fp=None)
        assert _get_exception_status_code(e) == 503

    def test_status_code_attr(self):
        e = DCStatusError('error')
        e.status_code = 429
        assert _get_exception_status_code(e) == 429

    def test_no_status_code(self):
        e = ValueError('no status')
        assert _get_exception_status_code(e) is None


# --- dc_api_wrapper retry behavior ---


class TestDcApiWrapperRetry:
    @patch('src.data_commons.api.dc_api_wrapper.requests_cache')
    def test_successful_call(self, mock_cache):
        mock_cache.is_installed.return_value = True
        mock_cache.disabled.return_value = MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        )
        fn = MagicMock(return_value={'result': 'ok'})
        result = dc_api_wrapper(fn, {})
        assert result == {'result': 'ok'}
        fn.assert_called_once()

    @patch('src.data_commons.api.dc_api_wrapper.requests_cache')
    def test_retry_on_connection_error_then_success(self, mock_cache):
        mock_cache.is_installed.return_value = True
        mock_cache.disabled.return_value = MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        )
        fn = MagicMock(side_effect=[
            DCConnectionError('fail'),
            {'result': 'ok'},
        ])
        result = dc_api_wrapper(fn, {}, retries=3, retry_secs=0)
        assert result == {'result': 'ok'}
        assert fn.call_count == 2

    @patch('src.data_commons.api.dc_api_wrapper.requests_cache')
    def test_raises_after_all_retries_exhausted(self, mock_cache):
        mock_cache.is_installed.return_value = True
        mock_cache.disabled.return_value = MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        )
        fn = MagicMock(side_effect=DCConnectionError('always fail'))
        with pytest.raises(DCConnectionError):
            dc_api_wrapper(fn, {}, retries=2, retry_secs=0)
        assert fn.call_count == 2

    @patch('src.data_commons.api.dc_api_wrapper.requests_cache')
    def test_key_error_returns_none_no_retry(self, mock_cache):
        mock_cache.is_installed.return_value = True
        mock_cache.disabled.return_value = MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        )
        fn = MagicMock(side_effect=KeyError('missing'))
        result = dc_api_wrapper(fn, {}, retries=3, retry_secs=0)
        assert result is None
        fn.assert_called_once()

    @patch('src.data_commons.api.dc_api_wrapper.requests_cache')
    def test_http_401_no_retry(self, mock_cache):
        mock_cache.is_installed.return_value = True
        mock_cache.disabled.return_value = MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        )
        e = urllib.error.HTTPError(
            url='http://test', code=401, msg='unauth', hdrs={}, fp=None)
        fn = MagicMock(side_effect=e)
        with pytest.raises(urllib.error.HTTPError):
            dc_api_wrapper(fn, {}, retries=3, retry_secs=0)
        fn.assert_called_once()


# --- dc_api_merge_results ---


class TestMergeResults:
    def test_merge_new_keys(self):
        result = {}
        dc_api_merge_results(result, {'a': 1, 'b': 2})
        assert result == {'a': 1, 'b': 2}

    def test_merge_nested_dicts(self):
        result = {'a': {'x': 1}}
        dc_api_merge_results(result, {'a': {'y': 2}})
        assert result == {'a': {'x': 1, 'y': 2}}

    def test_merge_lists(self):
        result = {'a': [1, 2]}
        dc_api_merge_results(result, {'a': [3, 4]})
        assert result == {'a': [1, 2, 3, 4]}

    def test_merge_none_results(self):
        result = dc_api_merge_results(None, {'a': 1})
        assert result == {'a': 1}


# --- namespace helpers ---


class TestNamespaceHelpers:
    def test_add_namespace(self):
        assert _add_namespace('Count_Person') == 'dcid:Count_Person'

    def test_add_namespace_already_has(self):
        assert _add_namespace('dcid:Count_Person') == 'dcid:Count_Person'

    def test_add_namespace_quoted(self):
        assert _add_namespace('"some value"') == '"some value"'

    def test_strip_namespace(self):
        assert _strip_namespace('dcid:Count_Person') == 'Count_Person'

    def test_strip_namespace_no_prefix(self):
        assert _strip_namespace('Count_Person') == 'Count_Person'

    def test_strip_namespace_quoted(self):
        assert _strip_namespace('"some value"') == '"some value"'
