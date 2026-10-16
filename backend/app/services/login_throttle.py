import math
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable

# Failed logins allowed within the window, counted separately for each email
# address and for each client address. Five guesses at one account is plenty
# for a person who mistyped; the per-address limit is higher because several
# people can share one address, and it slows guessing across many accounts.
MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_CLIENT = 50
FAILURE_WINDOW_SECONDS = 15 * 60

# Old entries are swept out once this many keys are tracked, so a stream of
# attempts against made-up addresses cannot grow memory without bound.
_SWEEP_THRESHOLD = 10_000


class LoginThrottle:
    """Counts recent failed logins and says when to stop accepting more.

    State is kept in this process's memory. It is reset when the server
    restarts and is not shared between processes, which suits a single
    backend process. Several processes would need a shared store such as Redis.
    """

    def __init__(
        self,
        max_failures_per_email: int = MAX_FAILURES_PER_EMAIL,
        max_failures_per_client: int = MAX_FAILURES_PER_CLIENT,
        window_seconds: float = FAILURE_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = {"email": max_failures_per_email, "client": max_failures_per_client}
        self._window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _keys(email: str, client: str | None) -> list[tuple[str, str]]:
        keys = [("email", f"email:{email}")]
        if client is not None:
            keys.append(("client", f"client:{client}"))
        return keys

    def _recent(self, key: str, now: float) -> deque[float]:
        """The failures for a key that are still inside the window, oldest first."""
        failures = self._failures.get(key, deque())
        while failures and now - failures[0] >= self._window_seconds:
            failures.popleft()
        return failures

    def seconds_until_allowed(self, email: str, client: str | None) -> int:
        """Zero if a login may be attempted now, otherwise how long to wait."""
        with self._lock:
            now = self._clock()
            wait = 0.0
            for kind, key in self._keys(email, client):
                failures = self._recent(key, now)
                if len(failures) >= self._limits[kind]:
                    # Allowed again once the oldest counted failure leaves the window.
                    wait = max(wait, failures[0] + self._window_seconds - now)
            return math.ceil(wait)

    def record_failure(self, email: str, client: str | None) -> None:
        with self._lock:
            now = self._clock()
            if len(self._failures) > _SWEEP_THRESHOLD:
                self._sweep(now)
            for _kind, key in self._keys(email, client):
                failures = self._recent(key, now)
                failures.append(now)
                self._failures[key] = failures

    def record_success(self, email: str) -> None:
        """A correct password clears that account's count, but not the client's."""
        with self._lock:
            self._failures.pop(f"email:{email}", None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()

    def _sweep(self, now: float) -> None:
        stale_keys: Iterable[str] = [
            key
            for key, failures in self._failures.items()
            if not failures or now - failures[-1] >= self._window_seconds
        ]
        for key in stale_keys:
            del self._failures[key]


login_throttle = LoginThrottle()
