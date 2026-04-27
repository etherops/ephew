import logging
import threading

from ephew.activity import ActivityNotifier


def test_subscribe_and_pulse_calls_listener():
    a = ActivityNotifier()
    calls = []
    a.subscribe(lambda: calls.append(1))
    a.pulse()
    assert calls == [1]


def test_pulse_with_no_subscribers_is_noop():
    a = ActivityNotifier()
    a.pulse()  # must not raise


def test_subscribers_run_in_registration_order():
    a = ActivityNotifier()
    log = []
    a.subscribe(lambda: log.append("a"))
    a.subscribe(lambda: log.append("b"))
    a.subscribe(lambda: log.append("c"))
    a.pulse()
    assert log == ["a", "b", "c"]


def test_listener_exception_does_not_block_others(caplog):
    a = ActivityNotifier()
    log = []

    def bad():
        raise RuntimeError("boom")

    a.subscribe(bad)
    a.subscribe(lambda: log.append("ok"))
    with caplog.at_level(logging.WARNING, logger="ephew.activity"):
        a.pulse()
    assert log == ["ok"]
    assert any("activity subscriber raised" in rec.getMessage() for rec in caplog.records)


def test_concurrent_pulses_no_lost_calls():
    a = ActivityNotifier()
    counter = [0]
    lock = threading.Lock()

    def inc():
        with lock:
            counter[0] += 1

    a.subscribe(inc)

    pulses_per_thread = 100
    threads = 4

    def worker():
        for _ in range(pulses_per_thread):
            a.pulse()

    ts = [threading.Thread(target=worker) for _ in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    assert counter[0] == pulses_per_thread * threads
