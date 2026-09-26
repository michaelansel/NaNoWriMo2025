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
from nanoif.github.bible import render_bible_diff, render_bible_not_run
from nanoif.github.commands import parse_command, write_github_output
from nanoif.github.comments import MARKER_BIBLE, upsert_sticky
from nanoif.github.dismiss import (
    DismissalError,
    append_record,
    apply_dismissals,
    build_record,
    load_dismissals,
)
from nanoif.github.merge import HEAD_SHA_FILE, merge_passage_review
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


def _recorded_head(path: Path) -> str:
    """Return the head sha recorded beside a stored review, or ``""`` when unknown."""
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _stale_review(sha_file: Path, head_sha: str) -> str:
    """Return why a stored review must not be re-rendered on ``head_sha``, or ``""``.

    A missing or empty sidecar means the commit is unknown, never the same commit (ADR-022).
    """
    recorded = _recorded_head(sha_file)
    if not recorded:
        return "the stored AI review does not say which commit it reviewed"
    if recorded != head_sha:
        return f"the stored AI review is for commit {recorded[:7]}, not {head_sha[:7]}"
    return ""


def _report(args: argparse.Namespace) -> int:
    if args.review_head_sha_file is not None and (args.pr is None or not args.head_sha):
        return _usage("--review-head-sha-file needs --pr and --head-sha (the current PR head)")
    try:
        review = load_artifact(args.review, "ai_review")
        if args.dismissals is not None:
            review = apply_dismissals(review, load_dismissals(args.dismissals))
    except (BuildError, ArtifactValidationError, DismissalError) as exc:
        return _usage(str(exc))
    stale = ""
    if args.review_head_sha_file is not None:
        stale = _stale_review(args.review_head_sha_file, args.head_sha)
    if args.github_output:
        write_github_output(args.github_output, {"rendered": "false" if stale else "true"})
    if stale:
        # Re-rendering an older commit's review would post its results as the current
        # head's; the next review of this head will pick up any recorded dismissal.
        print(f"{stale}; comments and check runs not re-rendered")
        _step_summary(f"AI comments not re-rendered: {stale}.")
        return EXIT_OK
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


def _bible_report(args: argparse.Namespace) -> int:
    run = RunInfo.from_env()
    if args.diff is not None:
        try:
            diff = load_artifact(args.diff, "bible_diff")
        except (BuildError, ArtifactValidationError) as exc:
            return _usage(str(exc))
        body = render_bible_diff(diff, run)
    else:
        body = render_bible_not_run(args.reason, run)
    _step_summary(body.removeprefix(MARKER_BIBLE))
    if args.pr is None:
        return EXIT_OK
    result = upsert_sticky(api_factory(), args.pr, MARKER_BIBLE, body)
    print(f"Story Bible: comment {result.action} ({result.comment_id})")
    return EXIT_OK


def _earlier_review(folder: Path | None, head_sha: str | None) -> tuple[dict | None, str]:
    """Return the earlier review to merge into, or ``None`` and why it is not usable."""
    review_path = folder / "ai-review.json" if folder is not None else None
    if review_path is None or not review_path.is_file():
        return None, "no earlier AI review of this pull request is available"
    recorded = _recorded_head(folder / HEAD_SHA_FILE)
    if not recorded or not head_sha:
        return None, "the earlier AI review does not say which commit it reviewed"
    if recorded != head_sha:
        return None, (
            f"the earlier AI review is for commit {recorded[:7]}, not {head_sha[:7]}"
        )
    try:
        return load_artifact(review_path, "ai_review"), ""
    except (BuildError, ArtifactValidationError) as exc:
        print(f"warning: cannot read the earlier AI review: {exc}", file=sys.stderr)
        return None, "the earlier AI review could not be read"


def _merge_review(args: argparse.Namespace) -> int:
    try:
        update = load_artifact(args.review, "ai_review")
    except (BuildError, ArtifactValidationError) as exc:
        return _usage(str(exc))
    if update["mode"] != "passage":
        return _usage(f"{args.review} is a mode {update['mode']!r} review, not mode 'passage'")
    previous, why = _earlier_review(args.previous_dir, args.head_sha)
    if previous is None:
        result = update
        print(f"{why}; publishing the re-check of {args.passage!r} as partial")
    else:
        try:
            result = merge_passage_review(previous, update, args.passage)
        except ArtifactValidationError as exc:
            return _usage(f"merged review is invalid: {exc}")
        print(f"merged the re-check of {args.passage!r} into the earlier AI review")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
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
    report.add_argument(
        "--review-head-sha-file",
        type=Path,
        help=f"the review's {HEAD_SHA_FILE}; publish only if it equals --head-sha",
    )
    report.add_argument(
        "--github-output", type=Path, help="append rendered=true|false to this file"
    )
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

    bible = commands.add_parser(
        "bible-report", help="the /extract-story-bible dry-run comment (<!-- nano:bible -->)"
    )
    bible.add_argument("--pr", type=int, help="pull request (omit: step summary only)")
    source = bible.add_mutually_exclusive_group(required=True)
    source.add_argument("--diff", type=Path, help="bible-diff.json of the dry run")
    source.add_argument("--reason", help="why the dry run did not run")
    bible.set_defaults(handler=_bible_report)

    merge = commands.add_parser(
        "merge-review", help="merge a passage re-check into the PR's last AI review"
    )
    merge.add_argument("--review", type=Path, required=True, help="the mode passage review")
    merge.add_argument("--passage", required=True, help="the re-checked passage")
    merge.add_argument(
        "--previous-dir",
        type=Path,
        help=f"the last ai-review artifact (ai-review.json and {HEAD_SHA_FILE})",
    )
    merge.add_argument("--head-sha", help="the pull request head the re-check reviewed")
    merge.add_argument("--out", type=Path, required=True, help="where to write the result")
    merge.set_defaults(handler=_merge_review)

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
