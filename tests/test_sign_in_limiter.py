"""The in-memory sign-in limiter, with a fake clock."""

import pytest

from sign_in_limiter import Reservation, SignInLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def limiter(clock: FakeClock) -> SignInLimiter:
    return SignInLimiter(clock=clock, window=60.0, max_buckets=100)


def take(limiter: SignInLimiter, *limits: tuple[object, int]) -> Reservation | int:
    return limiter.reserve(list(limits))


def test_attempts_up_to_the_limit_are_allowed(limiter):
    for _ in range(3):
        assert isinstance(take(limiter, ("room", 3)), Reservation)
    assert take(limiter, ("room", 3)) == 60


def test_wait_is_the_seconds_until_a_slot_frees(limiter, clock):
    for _ in range(2):
        take(limiter, ("room", 2))
    clock.now += 10
    assert take(limiter, ("room", 2)) == 50


def test_slots_free_after_the_window(limiter, clock):
    take(limiter, ("room", 1))
    clock.now += 59.9
    assert take(limiter, ("room", 1)) == 1
    clock.now += 0.2  # The first attempt is now a full window old.
    assert isinstance(take(limiter, ("room", 1)), Reservation)


def test_only_the_expired_part_of_a_full_bucket_frees(limiter, clock):
    # Two attempts at t=0 and t=30 fill a limit of 2.
    take(limiter, ("room", 2))
    clock.now += 30
    take(limiter, ("room", 2))
    clock.now += 5
    assert take(limiter, ("room", 2)) == 25  # Waits for the t=0 attempt.
    clock.now += 25
    assert isinstance(take(limiter, ("room", 2)), Reservation)


def test_release_gives_the_slot_back(limiter):
    first = take(limiter, ("room", 2))
    take(limiter, ("room", 2))
    assert take(limiter, ("room", 2)) == 60
    limiter.release(first)
    assert isinstance(take(limiter, ("room", 2)), Reservation)


def test_a_refused_attempt_takes_no_slot_in_any_bucket(limiter, clock):
    take(limiter, ("room", 1))
    # "client" has room to spare, but "room" is full: nothing is taken.
    assert take(limiter, ("client", 5), ("room", 1)) == 60
    for _ in range(5):  # Five slots: the refused attempt took none of them.
        assert isinstance(take(limiter, ("client", 5)), Reservation)
    assert take(limiter, ("client", 5)) == 60


def test_buckets_are_separate(limiter):
    take(limiter, (("room", "a"), 1))
    assert isinstance(take(limiter, (("room", "b"), 1)), Reservation)
    assert take(limiter, (("room", "a"), 1)) == 60


def test_memory_is_bounded_and_the_oldest_bucket_goes_first(clock):
    limiter = SignInLimiter(clock=clock, window=60.0, max_buckets=3)
    for name in ["a", "b", "c", "d"]:
        take(limiter, (("room", name), 1))
    assert len(limiter._buckets) == 3
    assert ("room", "a") not in limiter._buckets


def test_expired_buckets_are_dropped_before_live_ones(clock):
    limiter = SignInLimiter(clock=clock, window=60.0, max_buckets=2)
    take(limiter, (("room", "old"), 1))
    clock.now += 61
    take(limiter, (("room", "new1"), 1))
    take(limiter, (("room", "new2"), 1))
    assert set(limiter._buckets) == {("room", "new1"), ("room", "new2")}


def test_an_empty_bucket_is_removed_on_release(limiter):
    reservation = take(limiter, (("room", "a"), 1))
    limiter.release(reservation)
    assert limiter._buckets == {}
