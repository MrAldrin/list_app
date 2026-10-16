"""Sign-in rate limit on the API: room and admin sign-in, with a fake clock."""

import pytest
from api_helpers import APP_PASSWORD, HTTPS, browser, home, sign_in
from starlette.testclient import TestClient

import main
from api import sign_in_limit
from database_crud import create_room
from sign_in_limiter import SignInLimiter

LIMITED = {
    "error": {
        "code": "too_many_attempts",
        "message": "Too many attempts. Try again in a minute.",
    }
}


class FakeClock:
    def __init__(self) -> None:
        self.now = 5000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(sign_in_limit, "sign_in_limiter", SignInLimiter(clock=fake))
    return fake


def app_client(address: str = "testclient") -> TestClient:
    """A client with no sign-in, from one client address."""
    return TestClient(
        main.app,
        base_url=HTTPS,
        headers={"Origin": HTTPS},
        raise_server_exceptions=False,
        client=(address, 50000),
    )


def try_room(client: TestClient, slug: str, password: str):
    return client.post(f"/api/v1/rooms/{slug}/session", json={"password": password})


def exhaust_room(client: TestClient, slug: str, count: int = 10) -> None:
    for _ in range(count):
        assert try_room(client, slug, "wrong-one").status_code == 401


def test_eleventh_wrong_password_is_refused_with_retry_after(clock):
    _, slug = home()
    client = app_client()
    exhaust_room(client, slug)

    response = try_room(client, slug, "wrong-one")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == LIMITED


def test_the_right_password_is_refused_while_limited(clock):
    _, slug = home()
    client = app_client()
    exhaust_room(client, slug)

    response = try_room(client, slug, "pw")

    assert response.status_code == 429
    assert "set-cookie" not in response.headers


def test_the_room_opens_again_after_a_minute(clock):
    _, slug = home()
    client = app_client()
    exhaust_room(client, slug)

    clock.now += 60
    assert try_room(client, slug, "pw").status_code == 200


def test_a_successful_sign_in_does_not_use_up_the_limit(clock):
    _, slug = home()
    client = app_client()
    exhaust_room(client, slug, count=9)
    assert try_room(client, slug, "pw").status_code == 200

    # Nine failures plus one success: one more failure is still allowed.
    assert try_room(client, slug, "wrong-one").status_code == 401
    assert try_room(client, slug, "wrong-one").status_code == 429


def test_unknown_room_is_limited_the_same_way(clock):
    _, slug = home()
    client = app_client()
    unknown = "no-such-room"

    known_answers = [try_room(client, slug, "wrong-one") for _ in range(10)]
    unknown_answers = [try_room(client, unknown, "wrong-one") for _ in range(10)]

    assert [r.status_code for r in known_answers] == [401] * 10
    assert [r.status_code for r in unknown_answers] == [401] * 10
    assert [r.json() for r in known_answers] == [r.json() for r in unknown_answers]
    assert try_room(client, unknown, "wrong-one").status_code == 429
    assert try_room(client, slug, "wrong-one").status_code == 429


def test_each_room_has_its_own_limit(clock):
    _, slug = home()
    _, other_slug = create_room("Other", "pass")
    client = app_client()
    exhaust_room(client, slug)

    assert try_room(client, other_slug, "pass").status_code == 200


def test_one_client_is_limited_across_rooms(clock):
    _, first = home()
    _, second = create_room("Second", "pass")
    _, third = create_room("Third", "pass")
    client = app_client()
    exhaust_room(client, first)
    exhaust_room(client, second)

    assert try_room(client, third, "pass").status_code == 429


def test_another_client_is_not_limited_by_one_client(clock):
    _, first = home()
    _, second = create_room("Second", "pass")
    _, third = create_room("Third", "pass")
    attacker = app_client("10.0.0.1")
    exhaust_room(attacker, first)
    exhaust_room(attacker, second)

    other = app_client("10.0.0.2")
    assert try_room(other, third, "pass").status_code == 200


def test_a_bad_body_does_not_use_a_slot(clock):
    _, slug = home()
    client = app_client()
    for _ in range(12):
        assert client.post(f"/api/v1/rooms/{slug}/session", json={}).status_code == 422

    assert try_room(client, slug, "wrong-one").status_code == 401


def test_admin_sign_in_is_limited(clock, admin_app):
    client = browser(admin_app)
    for _ in range(10):
        assert sign_in(client, "wrong").status_code == 401

    response = sign_in(client, APP_PASSWORD)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == LIMITED
    assert client.get("/api/v1/admin/session").status_code == 401

    clock.now += 60
    assert sign_in(client, APP_PASSWORD).status_code == 200


def test_admin_limit_is_shared_by_all_clients(clock, admin_app):
    for address in ["10.0.1.1", "10.0.1.2"]:
        client = TestClient(
            admin_app,
            base_url=HTTPS,
            headers={"Origin": HTTPS},
            client=(address, 50000),
        )
        for _ in range(5):
            assert sign_in(client, "wrong").status_code == 401

    other = TestClient(
        admin_app,
        base_url=HTTPS,
        headers={"Origin": HTTPS},
        client=("10.0.1.3", 50000),
    )
    assert sign_in(other, "wrong").status_code == 429
    assert sign_in(other, APP_PASSWORD).status_code == 429
