"""Every ``nanoif`` call in ``.github/`` parses against the real CLI.

A workflow step that passes a missing or unknown option fails only when the
step runs, which for manual and exe-runner jobs can be days later. This reads
each call out of the workflow and action files (joining continuation lines and
bash argument arrays) and parses it with :func:`nanoif.cli.build_parser`.
"""

from __future__ import annotations

import argparse
import re
import shlex
from pathlib import Path

import pytest

from nanoif.cli import build_parser

REPO = Path(__file__).resolve().parents[1]
FILES = sorted((REPO / ".github").rglob("*.yml"))
STOP = {"|", "||", "&&", ";", ">", ">>", "<<<", "2>", "&>"}
ARRAY_USE = re.compile(r'"\$\{(\w+)\[@\]\}"')


def _calls(path: Path) -> list[tuple[int, str]]:
    """Return ``(line number, command text)`` for each ``nanoif`` call in a file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    calls = []
    for i, raw in enumerate(lines):
        text = raw.strip()
        text = re.sub(r"^(?:- )?run:\s*(?:>-?\s*)?", "", text)
        text = text.rsplit("| ", 1)[-1] if "| nanoif " in text else text
        if not text.startswith("nanoif "):
            continue
        j = i
        while text.endswith("\\") or (
            j + 1 < len(lines) and lines[j + 1].strip().startswith("--")
        ):
            j += 1
            text = text.rstrip("\\") + " " + lines[j].strip()
        calls.append((i + 1, _expand_arrays(text, lines[:i])))
    return calls


def _expand_arrays(text: str, before: list[str]) -> str:
    """Replace ``"${name[@]}"`` with every element the preceding lines give it."""

    def elements(match: re.Match[str]) -> str:
        name = match.group(1)
        joined = "\n".join(before)
        starts = [m.start() for m in re.finditer(rf"\b{name}=\(", joined)]
        if not starts:
            return ""
        tail = joined[starts[-1]:]
        parts = re.findall(rf"\b{name}\+?=\(([^)]*)\)", tail, flags=re.S)
        return " ".join(" ".join(p.split()) for p in parts)

    return ARRAY_USE.sub(elements, text)


def _argv(text: str) -> list[str]:
    tokens = shlex.split(text)[1:]
    for n, token in enumerate(tokens):
        if token in STOP or token.startswith((">", "2>")):
            return tokens[:n]
    return tokens


def _leaf(parser: argparse.ArgumentParser, argv: list[str]) -> argparse.ArgumentParser:
    for token in argv:
        if token.startswith("-"):
            break
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs or token not in subs[0].choices:
            break
        parser = subs[0].choices[token]
    return parser


def _concrete(argv: list[str]) -> list[str]:
    """Swap shell and Actions expressions for values their option accepts."""
    leaf = _leaf(build_parser(), argv)
    out = []
    for n, token in enumerate(argv):
        if "$" not in token:
            out.append(token)
            continue
        action = leaf._option_string_actions.get(argv[n - 1]) if n else None
        if action is not None and action.choices:
            out.append(sorted(action.choices)[0])
        elif action is not None and action.type is int:
            out.append("1")
        else:
            out.append("x")
    return out


def parse_error(text: str) -> str | None:
    """Return argparse's complaint about a ``nanoif`` command line, or ``None``."""
    parser = build_parser()
    messages: list[str] = []

    def fail(message: str) -> None:
        messages.append(message)
        raise SystemExit(2)

    for p in [parser, *_all_subparsers(parser)]:
        p.error = fail  # type: ignore[method-assign]
    try:
        parser.parse_args(_concrete(_argv(text)))
    except SystemExit:
        return messages[0] if messages else "exited while parsing"
    return None


def _all_subparsers(parser: argparse.ArgumentParser) -> list[argparse.ArgumentParser]:
    found = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                found += [sub, *_all_subparsers(sub)]
    return found


CALLS = [(path, line, text) for path in FILES for line, text in _calls(path)]


def test_workflows_call_nanoif():
    assert len(CALLS) >= 15


@pytest.mark.parametrize(
    ("path", "line", "text"),
    CALLS,
    ids=[f"{p.relative_to(REPO)}:{line}" for p, line, _ in CALLS],
)
def test_workflow_call_parses(path, line, text):
    assert parse_error(text) is None, f"{path.relative_to(REPO)}:{line}: {text}"


@pytest.mark.parametrize(
    "text",
    [
        "nanoif ai eval --out dist/eval-results.json --markdown dist/eval-results.md",
        'nanoif github not-run --pr "$PR_NUMBER" --reason "$reason"',
        'nanoif ai review --repo . --mode "$MODE" --bogus',
    ],
)
def test_checker_rejects_bad_calls(text):
    assert parse_error(text) is not None


@pytest.mark.parametrize(
    "name", ["build-and-deploy.yml", "ai-command.yml", "ai-maintenance.yml"]
)
def test_ai_workflows_pass_the_monthly_cap_from_a_repository_variable(name):
    text = (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")
    top_env = text.split("\njobs:", 1)[0]
    assert "NANOIF_LLM_MONTHLY_USD: ${{ vars.LLM_MONTHLY_USD }}" in top_env
