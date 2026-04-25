import logging
import threading

from ephew.modes import MODES
from ephew.state import CurrentMode


def test_get_returns_initial():
    state = CurrentMode(initial=MODES[0])
    assert state.get() is MODES[0]


def test_set_changes_mode_and_notifies():
    state = CurrentMode(initial=MODES[0])
    calls: list = []
    state.subscribe(lambda m: calls.append(m))
    state.set(MODES[1])
    assert state.get() is MODES[1]
    assert calls == [MODES[1]]


def test_set_same_mode_no_notify():
    state = CurrentMode(initial=MODES[0])
    calls: list = []
    state.subscribe(lambda m: calls.append(m))
    state.set(MODES[0])
    assert calls == []


def test_cycle_advances_and_returns_new():
    state = CurrentMode(initial=MODES[0])
    for i in range(1, len(MODES)):
        new = state.cycle()
        assert new is MODES[i]
        assert state.get() is MODES[i]
    # Wraps
    assert state.cycle() is MODES[0]


def test_subscribers_run_in_registration_order():
    state = CurrentMode(initial=MODES[0])
    log: list = []
    state.subscribe(lambda m: log.append("a"))
    state.subscribe(lambda m: log.append("b"))
    state.subscribe(lambda m: log.append("c"))
    state.set(MODES[1])
    assert log == ["a", "b", "c"]


def test_subscriber_exception_does_not_block_others():
    state = CurrentMode(initial=MODES[0])
    log: list = []

    def bad(_m):
        raise RuntimeError("boom")

    state.subscribe(bad)
    state.subscribe(lambda m: log.append("ok"))
    # set must not raise despite bad subscriber
    state.set(MODES[1])
    assert log == ["ok"]


def test_subscriber_can_call_get_without_deadlock():
    state = CurrentMode(initial=MODES[0])
    seen: list = []
    state.subscribe(lambda m: seen.append(state.get()))
    state.set(MODES[1])
    assert seen == [MODES[1]]


def test_mode_change_emits_log(caplog):
    state = CurrentMode(initial=MODES[0])
    with caplog.at_level(logging.INFO, logger="ephew.state"):
        state.set(MODES[1])
    messages = [rec.getMessage() for rec in caplog.records]
    assert any("mode changed" in m and MODES[1].name in m for m in messages), (
        f"expected mode-change log; got: {messages}"
    )


def test_setting_same_mode_emits_no_log(caplog):
    state = CurrentMode(initial=MODES[0])
    with caplog.at_level(logging.INFO, logger="ephew.state"):
        state.set(MODES[0])
    messages = [rec.getMessage() for rec in caplog.records]
    assert not any("mode changed" in m for m in messages)


def test_cycle_emits_log(caplog):
    state = CurrentMode(initial=MODES[0])
    with caplog.at_level(logging.INFO, logger="ephew.state"):
        state.cycle()
    messages = [rec.getMessage() for rec in caplog.records]
    assert any("mode changed" in m and MODES[1].name in m for m in messages)


def test_concurrent_cycle_no_lost_updates():
    state = CurrentMode(initial=MODES[0])
    steps_per_thread = 200
    threads = 4

    def worker():
        for _ in range(steps_per_thread):
            state.cycle()

    ts = [threading.Thread(target=worker) for _ in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    total = steps_per_thread * threads
    expected_index = total % len(MODES)
    assert state.get() is MODES[expected_index]
