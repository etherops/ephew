import pytest

from ephew.__main__ import main


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ephew" in captured.out.lower()


def test_help_lists_modes(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    # Epilog must include every non-normal mode and its directive.
    from ephew.modes import MODES

    for mode in MODES:
        assert mode.display in captured.out
    # And at least one full directive text appears.
    assert "One sentence." in captured.out


def test_version_prints_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    from ephew import __version__

    assert __version__ in captured.out


def test_unknown_flag_exits_2():
    with pytest.raises(SystemExit) as exc_info:
        main(["--not-a-real-flag"])
    assert exc_info.value.code == 2


def test_port_flag_parsed():
    import argparse

    parser = argparse.ArgumentParser(prog="ephew")
    parser.add_argument("--port", type=int, default=None)
    ns = parser.parse_args(["--port", "12345"])
    assert ns.port == 12345


def test_verbose_flag_parsed():
    import argparse

    parser = argparse.ArgumentParser(prog="ephew")
    parser.add_argument("--verbose", "-v", action="store_true")
    ns = parser.parse_args(["--verbose"])
    assert ns.verbose is True
    ns = parser.parse_args(["-v"])
    assert ns.verbose is True
    ns = parser.parse_args([])
    assert ns.verbose is False


def test_verbose_does_not_enable_third_party_debug():
    """--verbose must not unleash httpcore / httpx / uvicorn DEBUG noise."""
    import logging as _logging

    from ephew.__main__ import _configure_logging

    # Snapshot and restore root state so this test doesn't poison others.
    root = _logging.getLogger()
    saved_level = root.level
    saved_handlers = list(root.handlers)
    saved_namespaced = {
        name: _logging.getLogger(name).level for name in ("ephew", "httpx", "httpcore", "uvicorn")
    }
    try:
        _configure_logging(verbose=True)
        assert _logging.getLogger("ephew").getEffectiveLevel() == _logging.DEBUG
        for noisy in ("httpx", "httpcore", "uvicorn"):
            level = _logging.getLogger(noisy).getEffectiveLevel()
            assert level >= _logging.WARNING, (
                f"{noisy!r} effective level is {level} (expected >= WARNING)"
            )
    finally:
        for handler in list(root.handlers):
            if handler not in saved_handlers:
                root.removeHandler(handler)
        root.setLevel(saved_level)
        for name, lvl in saved_namespaced.items():
            _logging.getLogger(name).setLevel(lvl)
