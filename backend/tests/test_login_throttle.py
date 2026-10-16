"""The throttle on its own, with a clock the tests move by hand."""

import pytest

from app.services.login_throttle import LoginThrottle

WINDOW_SECONDS = 900


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def throttle(clock: FakeClock) -> LoginThrottle:
    return LoginThrottle(
        max_failures_per_email=3,
        max_failures_per_client=5,
        window_seconds=WINDOW_SECONDS,
        clock=clock,
    )


def fail(throttle: LoginThrottle, times: int, email: str = "ana@example.com", client: str = "10.0.0.1") -> None:
    for _ in range(times):
        throttle.record_failure(email, client)


def test_attempts_are_allowed_until_the_limit_is_reached(throttle: LoginThrottle) -> None:
    fail(throttle, 2)
    assert throttle.seconds_until_allowed("ana@example.com", "10.0.0.1") == 0

    fail(throttle, 1)
    assert throttle.seconds_until_allowed("ana@example.com", "10.0.0.1") == WINDOW_SECONDS


def test_the_wait_counts_down_from_the_oldest_failure(
    throttle: LoginThrottle, clock: FakeClock
) -> None:
    throttle.record_failure("ana@example.com", "10.0.0.1")
    clock.advance(100)
    fail(throttle, 2)

    clock.advance(50)

    # The first failure was 150 seconds ago; it leaves the window 750 seconds from now.
    assert throttle.seconds_until_allowed("ana@example.com", "10.0.0.1") == WINDOW_SECONDS - 150


def test_failures_older_than_the_window_stop_counting(
    throttle: LoginThrottle, clock: FakeClock
) -> None:
    fail(throttle, 3)

    clock.advance(WINDOW_SECONDS)

    assert throttle.seconds_until_allowed("ana@example.com", "10.0.0.1") == 0


def test_one_client_guessing_at_many_accounts_is_limited(throttle: LoginThrottle) -> None:
    for number in range(5):
        throttle.record_failure(f"person-{number}@example.com", "10.0.0.1")

    assert throttle.seconds_until_allowed("someone-new@example.com", "10.0.0.1") > 0
    assert throttle.seconds_until_allowed("someone-new@example.com", "10.0.0.2") == 0


def test_success_clears_the_account_but_not_the_client(throttle: LoginThrottle) -> None:
    fail(throttle, 3, email="ana@example.com")
    for number in range(2):
        throttle.record_failure(f"other-{number}@example.com", "10.0.0.1")

    throttle.record_success("ana@example.com")

    # Three of Ana's failures plus two others leave the client at its limit of five.
    assert throttle.seconds_until_allowed("ana@example.com", "10.0.0.2") == 0
    assert throttle.seconds_until_allowed("ana@example.com", "10.0.0.1") > 0


def test_an_unknown_client_address_is_limited_by_email_alone(throttle: LoginThrottle) -> None:
    for _ in range(3):
        throttle.record_failure("ana@example.com", None)

    assert throttle.seconds_until_allowed("ana@example.com", None) > 0
    assert throttle.seconds_until_allowed("ben@example.com", None) == 0


def test_stale_entries_are_swept_once_many_keys_are_tracked(
    throttle: LoginThrottle, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.login_throttle._SWEEP_THRESHOLD", 4)
    for number in range(5):
        throttle.record_failure(f"made-up-{number}@example.com", None)
    clock.advance(WINDOW_SECONDS)

    throttle.record_failure("ana@example.com", None)

    assert set(throttle._failures) == {"email:ana@example.com"}


def test_clear_forgets_everything(throttle: LoginThrottle) -> None:
    fail(throttle, 3)

    throttle.clear()

    assert throttle.seconds_until_allowed("ana@example.com", "10.0.0.1") == 0
