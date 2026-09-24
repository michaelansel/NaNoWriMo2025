"""``nanoif github``: publish workflow results to a pull request.

Exit codes: 0 ok, 1 GitHub API error (message on stderr), 2 usage or unreadable input.
``authorize`` also exits 1 when the user lacks write access. Without ``--pr``, the
report commands write only the workflow step summary (for maintenance runs).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

from nanoif.errors import ArtifactValidationError, BuildError
from nanoif.github.api import GitHubAPI
from nanoif.github.commands import parse_command, write_github_output
from nanoif.github.comments import upsert_sticky
from nanoif.github.dismiss import (
    DismissalError,
    append_record,
    apply_dismissals,
    build_record,
    load_dismissals,
)
from nanoif.github.report import (
    EDITORS,
    Rendered,
    RunInfo,
    collect_build_stats,
    render_build,
    render_editor,
    render_not_run,
    render_pending,
    render_unavailable,
)
from nanoif.schemas.artifacts import load_artifact, validate_artifact

EXIT_OK = 0
EXIT_API = 1
EXIT_USAGE = 2
WRITE_ROLES = frozenset({"admin", "maintain", "write"})
OUTCOMES = ("success", "failure", "cancelled", "skipped")
REACTIONS = ("+1", "-1", "laugh", "confused", "heart", "hooray", "rocket", "eyes")

# Tests replace this factory to inject a fake transport.
api_factory: Callable[[], GitHubAPI] = GitHubAPI.from_env


def _usage(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return EXIT_USAGE


def _step_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(markdown.rstrip() + "\n\n")


def _head_sha(api: GitHubAPI, pr: int, given: str | None) -> str:
    return given or api.get_pull(pr)["head"]["sha"]


def _publish(rendered: list[Rendered], pr: int | None, head_sha: str | None) -> None:
    for item in rendered:
        _step_summary(item.body.removeprefix(item.marker))
    if pr is None:
        return
    api = api_factory()
    sha = _head_sha(api, pr, head_sha)
    for item in rendered:
        result = upsert_sticky(api, pr, item.marker, item.body)
        check = item.check
        api.create_check_run(
            check.name,
            sha,
            check.conclusion,
            check.title,
            check.summary,
            check.text,
            check.annotations,
        )
        print(
            f"{check.name}: comment {result.action} ({result.comment_id}), check {check.conclusion}"
        )


def _report(args: argparse.Namespace) -> int:
    try:
        review = load_artifact(args.review, "ai_review")
        if args.dismissals is not None:
            review = apply_dismissals(review, load_dismissals(args.dismissals))
    except (BuildError, ArtifactValidationError, DismissalError) as exc:
        return _usage(str(exc))
    run = RunInfo.from_env()
    rendered = [render_editor(review, editor["name"], run) for editor in review["editors"]]
    _publish(rendered, args.pr, args.head_sha)
    failed = [e["name"] for e in review["editors"] if e["status"] != "ok"]
    if failed:
        print(f"editors not ok: {', '.join(failed)} (reported as failed checks)")
    return EXIT_OK


def _editor_names(value: str) -> list[str]:
    names = [name.strip() for name in value.split(",") if name.strip()]
    unknown = [name for name in names if name not in EDITORS]
    if unknown or not names:
        raise argparse.ArgumentTypeError(f"editors must be from {sorted(EDITORS)}")
    return names


def _unavailable(args: argparse.Namespace) -> int:
    run = RunInfo.from_env()
    rendered = [render_unavailable(name, args.reason, run) for name in args.editors]
    _publish(rendered, args.pr, args.head_sha)
    return EXIT_OK


def _not_run(args: argparse.Namespace) -> int:
    run = RunInfo.from_env()
    rendered = [render_not_run(name, args.reason, args.head_sha, run) for name in args.editors]
    _publish(rendered, args.pr, args.head_sha)
    return EXIT_OK


def _pending(args: argparse.Namespace) -> int:
    run = RunInfo.from_env()
    api = api_factory()
    for name in args.editors:
        spec = EDITORS[name]
        upsert_sticky(api, args.pr, spec.marker, render_pending(name, run))
    return EXIT_OK


def _build_report(args: argparse.Namespace) -> int:
    # Without a structure result the comment and check say the check did not run: a
    # missing or failed structure step must never render as "0 errors" (AC-structure-check-18).
    build_ok = args.build_outcome == "success"
    findings = None
    problem = None
    if args.structure_outcome == "success":
        try:
            findings = json.loads(args.structure.read_text(encoding="utf-8"))
            validate_artifact(findings, "structure_findings")
        except (OSError, json.JSONDecodeError, ArtifactValidationError) as exc:
            findings = None
            problem = f"cannot read the structure result: {exc}"
    try:
        # A failed build's dist/ holds no uploaded preview; its sizes would be stale.
        stats = collect_build_stats(args.dist) if build_ok and args.dist.is_dir() else None
    except (ArtifactValidationError, BuildError) as exc:
        return _usage(f"cannot read build inputs: {exc}")
    crashed = args.structure_outcome == "failure" or problem is not None
    rendered = render_build(
        findings, stats, RunInfo.from_env(), build_ok, structure_crashed=crashed
    )
    _publish([rendered], args.pr, args.head_sha)
    if problem is not None:
        return _usage(problem)
    return EXIT_OK


def _authorize(args: argparse.Namespace) -> int:
    role = api_factory().get_collaborator_permission(args.user)
    allowed = role in WRITE_ROLES
    print(f"{args.user}: {role} ({'allowed' if allowed else 'not allowed'})")
    return EXIT_OK if allowed else EXIT_API


def _react(args: argparse.Namespace) -> int:
    api_factory().add_reaction(args.comment_id, args.content)
    return EXIT_OK


def _parse_command(args: argparse.Namespace) -> int:
    command = parse_command(sys.stdin.read())
    values = command.outputs() if command else {"command": "none"}
    if args.github_output:
        write_github_output(args.github_output, values)
    print(
        f"command: {values['command']}" + (f" ({values['error']})" if values.get("error") else "")
    )
    return EXIT_OK


def _dismiss(args: argparse.Namespace) -> int:
    # No review result means no passage hashes: refuse rather than write a key-only line.
    if args.review is None or not args.review.is_file():
        print(f"error: no AI review result for PR #{args.pr}; nothing recorded", file=sys.stderr)
        return EXIT_API
    try:
        review = load_artifact(args.review, "ai_review")
    except (BuildError, ArtifactValidationError) as exc:
        return _usage(str(exc))
    try:
        record = build_record(args.key, args.by, args.pr, args.reason, review)
    except DismissalError as exc:
        print(f"error: {exc}; nothing recorded", file=sys.stderr)
        return EXIT_API
    append_record(args.out, record)
    print(f"recorded {args.key} for PR #{args.pr}")
    return EXIT_OK


def register(subparsers: argparse._SubParsersAction) -> None:
    """Add the ``github`` command group to the top-level parser.

    Args:
        subparsers: The top-level ``add_subparsers()`` object.
    """
    group = subparsers.add_parser("github", help="publish workflow results to GitHub")
    commands = group.add_subparsers(dest="github_command")
    group.set_defaults(handler=lambda _args: (group.print_help(), EXIT_USAGE)[1])

    report = commands.add_parser("report", help="AI review comments and check runs")
    report.add_argument("--pr", type=int, help="pull request (omit: step summary only)")
    report.add_argument("--review", type=Path, required=True, help="ai-review.json")
    report.add_argument("--dismissals", type=Path, help="ai/dismissals.jsonl to re-apply")
    report.add_argument("--head-sha", help="commit for the check runs (default: PR head)")
    report.set_defaults(handler=_report)

    unavailable = commands.add_parser("unavailable", help="AI review could not run")
    unavailable.add_argument("--pr", type=int)
    unavailable.add_argument("--reason", required=True)
    unavailable.add_argument(
        "--editors", type=_editor_names, default=list(EDITORS), help="comma-separated"
    )
    unavailable.add_argument("--head-sha")
    unavailable.set_defaults(handler=_unavailable)

    not_run = commands.add_parser(
        "not-run", help="AI review never started for this commit (build or probe failed)"
    )
    not_run.add_argument("--pr", type=int, required=True)
    not_run.add_argument("--reason", required=True)
    not_run.add_argument("--head-sha", required=True, help="the commit it did not run for")
    not_run.add_argument(
        "--editors", type=_editor_names, default=list(EDITORS), help="comma-separated"
    )
    not_run.set_defaults(handler=_not_run)

    pending = commands.add_parser("pending", help="mark AI comments as running")
    pending.add_argument("--pr", type=int, required=True)
    pending.add_argument("--editors", type=_editor_names, default=list(EDITORS))
    pending.set_defaults(handler=_pending)

    build = commands.add_parser("build-report", help="Build & Structure comment and check")
    build.add_argument("--pr", type=int)
    build.add_argument("--structure", type=Path, required=True, help="structure JSON")
    build.add_argument("--dist", type=Path, required=True, help="build output directory")
    build.add_argument(
        "--build-outcome",
        choices=OUTCOMES,
        default="success",
    )
    build.add_argument(
        "--structure-outcome",
        choices=OUTCOMES,
        default="success",
        help="outcome of the structure step; anything but success means no structure result",
    )
    build.add_argument("--head-sha")
    build.set_defaults(handler=_build_report)

    authorize = commands.add_parser("authorize", help="exit 0 if the user has write access")
    authorize.add_argument("--user", required=True)
    authorize.set_defaults(handler=_authorize)

    react = commands.add_parser("react", help="react to an issue comment")
    react.add_argument("--comment-id", type=int, required=True)
    react.add_argument("--content", choices=REACTIONS, default="eyes")
    react.set_defaults(handler=_react)

    parse = commands.add_parser("parse-command", help="parse a slash command from stdin")
    parse.add_argument("--github-output", type=Path, help="append outputs to this file")
    parse.set_defaults(handler=_parse_command)

    dismiss = commands.add_parser("dismiss", help="append a dismissal record")
    dismiss.add_argument("--key", required=True)
    dismiss.add_argument("--by", required=True)
    dismiss.add_argument("--pr", type=int, required=True)
    dismiss.add_argument("--reason", default="")
    dismiss.add_argument("--review", type=Path, help="the PR's last ai-review.json")
    dismiss.add_argument("--out", type=Path, required=True, help="ai/dismissals.jsonl")
    dismiss.set_defaults(handler=_dismiss)
