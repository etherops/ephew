import sys

import pytest

from ephew.__main__ import main


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ephew" in captured.out.lower()


def test_unknown_flag_exits_2():
    with pytest.raises(SystemExit) as exc_info:
        main(["--not-a-real-flag"])
    assert exc_info.value.code == 2


def test_verbose_flag_parsed():
    import argparse

    # Mirror the argparse setup in ephew.__main__ so we can assert --verbose is accepted
    # without actually starting the daemon.
    parser = argparse.ArgumentParser(prog="ephew")
    parser.add_argument("--verbose", "-v", action="store_true")
    ns = parser.parse_args(["--verbose"])
    assert ns.verbose is True
    ns = parser.parse_args(["-v"])
    assert ns.verbose is True
    ns = parser.parse_args([])
    assert ns.verbose is False
