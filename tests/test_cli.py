"""Smoke tests for the ``nanoif`` CLI entry point."""

from nanoif import __version__
from nanoif.cli import main


def test_version_flag_prints_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help_and_succeeds(capsys):
    assert main([]) == 0
    assert "usage: nanoif" in capsys.readouterr().out
