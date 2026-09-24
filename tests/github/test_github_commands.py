"""Slash-command parsing for ai-command.yml."""

from __future__ import annotations

import pytest

from nanoif.github.commands import Command, parse_command, write_github_output


@pytest.mark.intent("AC-continuity-review-10")
@pytest.mark.parametrize(
    "body, expected",
    [
        ("/check-continuity", Command("check-continuity", mode="changed")),
        ("/check-continuity all", Command("check-continuity", mode="all")),
        ("/CHECK-CONTINUITY ALL", Command("check-continuity", mode="all")),
        ("  /check-continuity  \nthanks!", Command("check-continuity", mode="changed")),
        (
            "/check-continuity passage=The widow's door",
            Command("check-continuity", mode="passage", passage="The widow's door"),
        ),
        (
            '/check-continuity passage="Day 1 EV"',
            Command("check-continuity", mode="passage", passage="Day 1 EV"),
        ),
        ("/extract-story-bible", Command("extract-story-bible")),
        ("/extract-story-bible full", Command("extract-story-bible")),
        ("/dismiss f-1a2b3c4d", Command("dismiss", key="f-1a2b3c4d")),
        (
            "/dismiss F-1A2B3C4D Tamsin misremembers on purpose",
            Command("dismiss", key="f-1a2b3c4d", reason="Tamsin misremembers on purpose"),
        ),
    ],
)
def test_known_commands(body, expected):
    assert parse_command(body) == expected


@pytest.mark.intent("AC-continuity-review-10")
@pytest.mark.parametrize(
    "body",
    [
        None,
        "",
        "LGTM",
        "please run /check-continuity",
        "/status",
        "/check-continuityall",
        "/help me",
        "> /check-continuity",
    ],
)
def test_anything_else_is_not_a_command(body):
    assert parse_command(body) is None


@pytest.mark.intent("AC-continuity-review-10")
@pytest.mark.parametrize(
    "body, fragment",
    [
        ("/check-continuity modified", "unknown argument 'modified'"),
        ("/check-continuity new-only", "unknown argument"),
        ("/check-continuity passage=", "needs a passage name"),
        ("/check-continuity all passage=The weir", "not both"),
        ("/dismiss", "not a finding key"),
        ("/dismiss 1a2b3c4d", "not a finding key"),
        ("/dismiss f-xyz", "not a finding key"),
    ],
)
def test_known_command_with_bad_arguments_carries_an_error(body, fragment):
    command = parse_command(body)
    assert command is not None and command.error and fragment in command.error
    assert command.mode is None and command.key is None


def test_reason_is_capped():
    command = parse_command("/dismiss f-1a2b3c4d " + "x" * 900)
    assert command is not None and len(command.reason or "") == 500


def test_github_output_uses_random_delimiters_that_values_cannot_close(tmp_path):
    out = tmp_path / "output"
    hostile = "ok\nEOF\ncommand=dismiss"
    write_github_output(out, {"reason": hostile, "command": "check-continuity"})
    text = out.read_text()
    first_line = text.splitlines()[0]
    assert first_line.startswith("reason<<EOF_") and len(first_line) > len("reason<<EOF_")
    delimiter = first_line.split("<<", 1)[1]
    assert text.count(delimiter) == 2
    assert "command<<EOF_" in text


def test_outputs_are_all_strings():
    values = Command("check-continuity", mode="all").outputs()
    assert values == {
        "command": "check-continuity",
        "mode": "all",
        "passage": "",
        "key": "",
        "reason": "",
        "error": "",
    }
