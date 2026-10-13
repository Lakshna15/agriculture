"""Shared machinery for tests that run actions at the same moment on separate connections."""

import threading
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

SessionFactory = sessionmaker[Session]

# An action receives a function to call once it is connected and ready. That
# call blocks until every other action is ready too.
WaitForStart = Callable[[], None]
Action = Callable[[WaitForStart], str]


def run_together(actions: list[Action]) -> list[str]:
    """Run each action on its own thread and release them all at the same instant.

    Returns the outcomes the actions reported, sorted so that assertions do not
    depend on which thread happened to win.
    """
    barrier = threading.Barrier(len(actions))
    outcomes: list[str] = []

    def run(action: Action) -> None:
        outcomes.append(action(lambda: barrier.wait(timeout=10)))

    threads = [threading.Thread(target=run, args=(action,)) for action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads), "an action is deadlocked"
    assert len(outcomes) == len(actions), "a thread ended without reporting an outcome"
    return sorted(outcomes)
