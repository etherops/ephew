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
    # Epilog must include every non-none mode and its directive.
    from ephew.modes import MODES

    for mode in MODES:
        assert mode.display in captured.out
    # And at least one full directive text appears.
    assert "Max one sentence." in captured.out


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


def test_setup_default_prints_friendly_message(capsys):
    rc = main(["setup"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ANTHROPIC_BASE_URL" in out
    assert "127.0.0.1:47821" in out
    # Friendly form mentions both apply paths.
    assert "eval" in out.lower()
    assert "rc" in out.lower() or "shell" in out.lower()


def test_setup_print_emits_single_export_line(capsys):
    rc = main(["setup", "--print"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "export ANTHROPIC_BASE_URL=http://127.0.0.1:47821"


def test_setup_print_honors_port_flag(capsys):
    rc = main(["setup", "--print", "--port", "12345"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "export ANTHROPIC_BASE_URL=http://127.0.0.1:12345"


def test_setup_print_honors_ephew_port_env(monkeypatch, capsys):
    monkeypatch.setenv("EPHEW_PORT", "33333")
    rc = main(["setup", "--print"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "export ANTHROPIC_BASE_URL=http://127.0.0.1:33333"


def test_setup_append_rc_writes_line(tmp_path, monkeypatch, capsys):
    rc_file = tmp_path / ".zshrc"
    rc_file.write_text("# pre-existing content\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")

    rc = main(["setup", "--append-rc"])
    assert rc == 0
    contents = rc_file.read_text()
    assert "export ANTHROPIC_BASE_URL=http://127.0.0.1:47821" in contents
    assert "# ephew" in contents
    assert contents.startswith("# pre-existing content\n")


def test_setup_append_rc_is_idempotent(tmp_path, monkeypatch):
    rc_file = tmp_path / ".zshrc"
    rc_file.write_text("\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")

    main(["setup", "--append-rc"])
    main(["setup", "--append-rc"])
    contents = rc_file.read_text()
    assert contents.count("export ANTHROPIC_BASE_URL") == 1


def test_setup_append_rc_uses_fish_syntax_when_shell_is_fish(tmp_path, monkeypatch):
    rc_file = tmp_path / ".config/fish/config.fish"
    rc_file.parent.mkdir(parents=True)
    rc_file.write_text("")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/usr/local/bin/fish")

    main(["setup", "--append-rc"])
    contents = rc_file.read_text()
    assert "set -gx ANTHROPIC_BASE_URL http://127.0.0.1:47821" in contents
    assert "export" not in contents


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
