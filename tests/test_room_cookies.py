"""Cookie names and the same-origin rule that every API write depends on.

The API sets and reads the cookies (tests/test_api_session.py). The old
`/_room-access/{slug}` endpoint of the NiceGUI pages is gone; its token rules
live in tests/test_room_token_validation.py and its request checks are the
API's (tests/test_api_basics.py).
"""

import pytest
from starlette.requests import Request

from room_cookies import (
    HOST_PREFIX,
    LAST_ROOM_COOKIE,
    is_same_origin_request,
    plain_token_cookie_name,
    token_cookie_name,
)


def request(headers: dict[str, str], scheme: str = "https") -> Request:
    return Request(
        {
            "type": "http",
            "scheme": scheme,
            "server": ("testserver", 443 if scheme == "https" else 80),
            "path": "/",
            "headers": [
                (b"host", b"testserver"),
                *((k.lower().encode(), v.encode()) for k, v in headers.items()),
            ],
        }
    )


def test_token_cookie_names_hide_the_slug_and_differ_per_room():
    first, second = token_cookie_name("home-ab12cd"), token_cookie_name("other")
    assert first != second
    assert first.startswith(HOST_PREFIX)
    assert "home-ab12cd" not in first
    assert first == HOST_PREFIX + plain_token_cookie_name("home-ab12cd")
    assert LAST_ROOM_COOKIE.startswith(HOST_PREFIX)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Origin": "https://testserver"}, True),
        ({"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"}, True),
        ({}, False),
        ({"Origin": "https://evil.example"}, False),
        ({"Origin": "http://testserver"}, False),
        ({"Origin": "https://testserver", "Sec-Fetch-Site": "cross-site"}, False),
        ({"Origin": "https://testserver", "Sec-Fetch-Site": "same-site"}, False),
        ({"Sec-Fetch-Site": "same-origin"}, False),
    ],
)
def test_only_the_exact_origin_counts_as_same_origin(headers, expected):
    assert is_same_origin_request(request(headers)) is expected
