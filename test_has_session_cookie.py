"""Unit tests for _has_session_cookie (Task 1.1)."""
import pytest
from unittest.mock import MagicMock, patch

# Patch boto3 at the module level so lambda_handler can be imported without
# real AWS credentials or a configured region.
with patch('boto3.resource', return_value=MagicMock()):
    from lambda_handler import _has_session_cookie


def make_event(cookie=None):
    headers = {}
    if cookie is not None:
        headers['Cookie'] = cookie
    return {'headers': headers}


def test_no_cookie_header_returns_false():
    assert _has_session_cookie(make_event()) is False


def test_visitor_session_1_returns_true():
    assert _has_session_cookie(make_event('visitor_session=1')) is True


def test_visitor_session_1_among_multiple_cookies_returns_true():
    assert _has_session_cookie(make_event('foo=bar; visitor_session=1; baz=qux')) is True


def test_visitor_session_wrong_value_returns_false():
    assert _has_session_cookie(make_event('visitor_session=2')) is False


def test_malformed_cookie_string_returns_false():
    # ";;;" splits into empty/whitespace tokens — none equal 'visitor_session=1'
    assert _has_session_cookie(make_event(';;;')) is False


def test_empty_cookie_header_returns_false():
    assert _has_session_cookie(make_event('')) is False


def test_exception_during_parsing_returns_false():
    # headers is not a dict — accessing .get will raise AttributeError
    assert _has_session_cookie({'headers': None}) is False
