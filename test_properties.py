"""Property-based tests for session-cookie deduplication (Task 4)."""
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import hypothesis
from hypothesis import given, settings
import hypothesis.strategies as st

# Patch boto3 at the module level so lambda_handler can be imported without
# real AWS credentials or a configured region.
with patch('boto3.resource', return_value=MagicMock()):
    from lambda_handler import lambda_handler

# sha256("test-key") — used to patch EXPECTED_HASH so API key auth passes
TEST_API_KEY = "test-key"
TEST_API_KEY_HASH = "62af8704764faf8ea82fc61ce9c4c3908b6cb97d463a634e9e587d7c885db0ef"


def make_event(cookie=None, api_key=TEST_API_KEY):
    """Build a minimal Lambda proxy event."""
    headers = {"X-API-Key": api_key}
    if cookie is not None:
        headers["Cookie"] = cookie
    return {"headers": headers}


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Simple cookie name=value token (no semicolons, no visitor_session=1)
_safe_cookie_token = st.from_regex(r'[a-zA-Z][a-zA-Z0-9_]{0,10}=[a-zA-Z0-9]{1,10}', fullmatch=True).filter(
    lambda s: s != "visitor_session=1"
)

# Cookie strings that CONTAIN visitor_session=1 (possibly with surrounding cookies)
@st.composite
def cookie_with_session(draw):
    prefix_parts = draw(st.lists(_safe_cookie_token, min_size=0, max_size=3))
    suffix_parts = draw(st.lists(_safe_cookie_token, min_size=0, max_size=3))
    parts = prefix_parts + ["visitor_session=1"] + suffix_parts
    sep = draw(st.sampled_from(["; ", ";", " ; "]))
    return sep.join(parts)


# Cookie strings that do NOT contain visitor_session=1
@st.composite
def cookie_without_session(draw):
    strategy = draw(st.sampled_from(["empty", "tokens", "malformed"]))
    if strategy == "empty":
        return ""
    elif strategy == "tokens":
        parts = draw(st.lists(_safe_cookie_token, min_size=1, max_size=5))
        return "; ".join(parts)
    else:
        # malformed: random text that doesn't contain visitor_session=1
        return draw(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=50).filter(
            lambda s: "visitor_session=1" not in s
        ))


# ---------------------------------------------------------------------------
# Property 1: Returning visitor — no increment, no Set-Cookie
# ---------------------------------------------------------------------------

# Feature: session-cookie-deduplication, Property 1: Returning visitor — no increment, no Set-Cookie
@settings(max_examples=100)
@given(cookie=cookie_with_session())
def test_returning_visitor_no_increment_no_set_cookie(cookie):
    """
    Validates: Requirements 1.1, 2.2

    For any request containing visitor_session=1 in the Cookie header,
    update_item must NOT be called and the response must have no Set-Cookie header.
    """
    mock_table = MagicMock()
    mock_table.get_item.return_value = {"Item": {"visitors_count": Decimal("42")}}

    with patch("lambda_handler.EXPECTED_HASH", TEST_API_KEY_HASH), \
         patch("lambda_handler.table", mock_table):
        response = lambda_handler(make_event(cookie=cookie), None)

    mock_table.update_item.assert_not_called()
    assert response["statusCode"] == 200
    assert "Set-Cookie" not in response.get("headers", {})


# ---------------------------------------------------------------------------
# Property 2: New visitor — increment and Set-Cookie
# ---------------------------------------------------------------------------

# Feature: session-cookie-deduplication, Property 2: New visitor — increment and Set-Cookie
@settings(max_examples=100)
@given(cookie=st.one_of(st.none(), cookie_without_session()))
def test_new_visitor_increment_and_set_cookie(cookie):
    """
    Validates: Requirements 1.2, 1.3, 1.4, 2.1, 2.3, 2.4, 2.5

    For any request where the Cookie header is absent or does not contain
    visitor_session=1, update_item must be called once and the response must
    include the exact Set-Cookie header with no Max-Age or Expires attribute.
    """
    mock_table = MagicMock()
    mock_table.update_item.return_value = {"Attributes": {"visitors_count": Decimal("5")}}

    with patch("lambda_handler.EXPECTED_HASH", TEST_API_KEY_HASH), \
         patch("lambda_handler.table", mock_table):
        response = lambda_handler(make_event(cookie=cookie), None)

    mock_table.update_item.assert_called_once()
    assert response["statusCode"] == 200

    set_cookie = response.get("headers", {}).get("Set-Cookie", "")
    assert set_cookie == "visitor_session=1; Path=/; SameSite=Strict; HttpOnly"

    # No Max-Age or Expires attributes
    assert "Max-Age" not in set_cookie
    assert "Expires" not in set_cookie


# ---------------------------------------------------------------------------
# Property 3: Response structure is always consistent
# ---------------------------------------------------------------------------

# Feature: session-cookie-deduplication, Property 3: Response structure is always consistent
@settings(max_examples=100)
@given(
    is_returning=st.booleans(),
    count=st.integers(min_value=0, max_value=10_000_000),
)
def test_response_structure_always_consistent(is_returning, count):
    """
    Validates: Requirements 5.1, 5.2, 5.3

    For any valid request (new or returning visitor), the response must have
    statusCode 200, a parseable JSON body, and a non-negative integer visitors_count.
    """
    mock_table = MagicMock()

    if is_returning:
        mock_table.get_item.return_value = {"Item": {"visitors_count": Decimal(str(count))}}
        cookie = "visitor_session=1"
    else:
        mock_table.update_item.return_value = {"Attributes": {"visitors_count": Decimal(str(count))}}
        cookie = None

    with patch("lambda_handler.EXPECTED_HASH", TEST_API_KEY_HASH), \
         patch("lambda_handler.table", mock_table):
        response = lambda_handler(make_event(cookie=cookie), None)

    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert "visitors_count" in body
    assert isinstance(body["visitors_count"], int)
    assert body["visitors_count"] >= 0
