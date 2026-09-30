"""Command-line entry point for ``nanoif``.

Build commands take ``--repo`` and derive every other path from it
(``src/``, ``lib/artifacts/``, ``dist/``, ``ai/story-bible-cache.json``); each
can be overridden. Nothing is resolved against the current directory.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from nanoif import __version__
from nanoif.build.paths import ProjectPaths
from nanoif.errors import NanoifError

if TYPE_CHECKING:
    from nanoif.llm.client import Completer

Handler = Callable[[argparse.Namespace], int]


def _paths(args: argparse.Namespace) -> ProjectPaths:
    return ProjectPaths.from_repo(
        args.repo,
        src=args.src,
        artifacts=args.artifacts,
        dist=args.out,
        cache=getattr(args, "cache", None),
    )


def _add_build(
    subparsers: argparse._SubParsersAction, name: str, help_text: str, handler: Handler
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("--repo", type=Path, required=True, help="repository root")
    parser.add_argument("--src", type=Path, help="story source (default: <repo>/src)")
    parser.add_argument("--artifacts", type=Path, help="default: <repo>/lib/artifacts")
    parser.add_argument("--out", type=Path, help="output directory (default: <repo>/dist)")
    parser.set_defaults(handler=handler)
    return parser


def _build_core(args: argparse.Namespace) -> int:
    from nanoif.build.core import build_core

    paths = _paths(args)
    result = build_core(
        html_path=args.html or paths.paperthin_html,
        src_dir=paths.src,
        out_dir=paths.artifacts,
        lookup_path=args.lookup or paths.lookup,
    )
    print(f"Parsed {result.passage_count} passages; start passage: {result.start_passage}")
    print(f"Wrote {result.story_graph_path}")
    print(f"Wrote {result.passages_path}")
    print(f"Wrote {result.lookup_path} ({result.path_count} routes)")
    return 0


def _build_allpaths(args: argparse.Namespace) -> int:
    from nanoif.formats.allpaths import AllPathsConfig, resolve_base_ref, run

    paths = _paths(args)
    base_ref = args.base_ref or resolve_base_ref(os.environ)
    result = run(
        AllPathsConfig(
            repo_root=paths.repo,
            src_dir=paths.src,
            story_graph_path=paths.story_graph,
            output_dir=paths.dist,
            base_ref=base_ref,
        )
    )
    print(f"Base ref: {base_ref} ({result.base_sha})")
    print(
        f"Paths: {len(result.paths)} "
        f"(new {result.counts['new']}, modified {result.counts['modified']}, "
        f"unchanged {result.counts['unchanged']})"
    )
    for source, target in result.broken_links:
        print(f"WARNING: broken link {source!r} -> {target!r} (not followed)")
    for cycle in result.cycles:
        print(f"WARNING: cycle cut at {' -> '.join(cycle)}")
    print(f"Wrote {result.html_path} and {len(result.paths)} path files under {paths.dist}")
    return 0


def _build_metrics(args: argparse.Namespace) -> int:
    from nanoif.formats.metrics import MetricsConfig, build_metrics

    paths = _paths(args)
    result = build_metrics(
        MetricsConfig(
            src_dir=paths.src,
            story_graph_path=paths.story_graph,
            output_dir=paths.dist,
            include=tuple(args.include or ()),
            exclude=tuple(args.exclude or ()),
            top_n=args.top,
        )
    )
    metrics = result.metrics
    print(
        f"Metrics: {metrics['total_words']:,} words in {metrics['passage_count']} passages "
        f"across {metrics['file_count']} files"
    )
    print(f"Wrote {result.html_path}")
    return 0


def _preview_inputs(
    args: argparse.Namespace,
) -> tuple[tuple[str, ...] | None, dict[str, str]]:
    """The pull request's passages and why any were not read, for a preview Story Bible.

    Raises:
        NanoifError: ``changes.json`` or the preview's ``bible-diff.json`` is missing or
            invalid.
    """
    from nanoif.schemas.artifacts import load_artifact

    changes_path = getattr(args, "preview_passages", None)
    if changes_path is None:
        return None, {}
    changes = load_artifact(changes_path, "changes")
    passages = tuple(sorted(set(changes["changed"]) | set(changes["new"])))
    reasons: dict[str, str] = {}
    diff_path = getattr(args, "preview_diff", None)
    if diff_path is not None:
        diff = load_artifact(diff_path, "bible_diff")
        reasons = {item["passage"]: item["reason"] for item in diff["passages_failed"]}
    reason = getattr(args, "preview_reason", None)
    if reason:
        reasons = {name: reasons.get(name, reason) for name in passages} | reasons
    return passages, reasons


def _build_story_bible(args: argparse.Namespace) -> int:
    from nanoif.formats.story_bible import StoryBibleConfig, build_story_bible

    if getattr(args, "preview_passages", None) is None and (
        getattr(args, "preview_diff", None) is not None or getattr(args, "preview_reason", None)
    ):
        print("error: --preview-diff and --preview-reason need --preview-passages",
              file=sys.stderr)
        return 2
    paths = _paths(args)
    preview_passages, reasons = _preview_inputs(args)
    result = build_story_bible(
        StoryBibleConfig(
            repo_root=paths.repo,
            cache_path=paths.cache,
            src_dir=paths.src,
            overrides_path=paths.overrides,
            story_graph_path=paths.story_graph,
            output_dir=paths.dist,
            extraction_result=getattr(args, "extraction_result", None) or "success",
            preview_passages=preview_passages,
            unread_reasons=reasons,
        )
    )
    bible = result.bible
    fresh = bible.freshness
    if result.placeholder:
        print(f"Story Bible cache not found at {paths.cache}; rendered the placeholder page")
    else:
        print(
            f"Story Bible: {len(bible.cast)} characters, {len(bible.places)} places, "
            f"{len(bible.items)} items, {len(bible.groups)} groups, "
            f"{len(bible.world_rules)} world rules, {len(bible.conflicts)} conflicts, "
            f"{len(bible.mysteries)} intentional mysteries"
        )
    print(
        f"Story Bible freshness: {len(fresh.unread)} passage(s) not yet read in their current "
        f"text, {len(fresh.deleted)} no longer in the story; latest extraction: "
        f"{fresh.extraction_result}"
    )
    for name, reason in fresh.reasons.items():
        print(f"not read in this pull request's preview: {name}: {reason}")
    for line, text in bible.unmatched:
        print(f"story-overrides.txt:{line}: unmatched: {text}")
    print(f"Wrote {result.html_path} and {result.json_path}")
    return 0


def _build_canon_pack(args: argparse.Namespace) -> int:
    from nanoif.bible.assemble import load_bible
    from nanoif.bible.canon import write_canon_pack

    paths = _paths(args)
    bible = load_bible(paths.repo, paths.cache, overrides_path=paths.overrides, src=paths.src)
    pack = write_canon_pack(bible, paths.canon_pack)
    facts = sum(len(entity["facts"]) for entity in pack["entities"])
    source = "from the saved extraction" if bible.cache_present else "with no saved extraction"
    print(f"Canon pack {source}: {len(pack['entities'])} entities, {facts} facts")
    print(f"Wrote {paths.canon_pack}")
    return 0


def _build_passages(args: argparse.Namespace) -> int:
    from nanoif.formats.passages import build_passages

    paths = _paths(args)
    result = build_passages(paths.src, paths.story_graph, paths.dist)
    print(f"Passage index: {result.passage_count} passages in {result.file_count} files")
    print(f"Wrote {result.html_path}")
    return 0


def _build_landing(args: argparse.Namespace) -> int:
    from nanoif.formats.landing import build_landing

    paths = _paths(args)
    out = build_landing(paths.repo / "landing" / "index.html", paths.story_graph, paths.dist)
    print(f"Wrote {out}")
    return 0


def _build_all(args: argparse.Namespace) -> int:
    steps = (
        _build_core,
        _build_allpaths,
        _build_metrics,
        _build_story_bible,
        _build_canon_pack,
        _build_passages,
        _build_landing,
    )
    for step in steps:
        status = step(args)
        if status != 0:
            return status
    return 0


def _lint(args: argparse.Namespace) -> int:
    from nanoif.twee.lint import lint_path

    violations = lint_path(args.path)
    for violation in violations:
        print(violation.github() if args.format == "github" else str(violation))
    files = len({violation.file for violation in violations})
    print(f"{len(violations)} formatting issue(s) in {files} file(s)", file=sys.stderr)
    return 1 if violations and not args.exit_zero else 0


def _check_structure(args: argparse.Namespace) -> int:
    from nanoif.check.structure import check_structure, format_findings

    overrides = args.overrides or args.src.parent / "story-overrides.txt"
    findings = check_structure(args.src, overrides_path=overrides)
    output = format_findings(findings, args.format)
    if output:
        print(output)
    errors = sum(1 for finding in findings if finding.level == "error")
    warnings = sum(1 for finding in findings if finding.level == "warning")
    infos = len(findings) - errors - warnings
    print(f"{errors} error(s), {warnings} warning(s), {infos} info", file=sys.stderr)
    return 1 if errors and not args.exit_zero else 0


def _ai_review(args: argparse.Namespace) -> int:
    from nanoif.github.commands import write_github_output
    from nanoif.llm.errors import LLMConfigError
    from nanoif.review.runner import preflight, review, summary_lines
    from nanoif.schemas.artifacts import write_artifact

    mode = args.mode or ("passage" if args.passage else "changed")
    if args.passage and mode != "passage":
        print("ai review could not run: --passage needs --mode passage", file=sys.stderr)
        return 2
    if args.estimate_only and mode != "all":
        print("ai review could not run: --estimate-only needs --mode all", file=sys.stderr)
        return 2
    if args.github_output is not None and not args.estimate_only:
        print("ai review could not run: --github-output needs --estimate-only", file=sys.stderr)
        return 2
    editors = tuple(name.strip() for name in args.editors.split(",") if name.strip())
    try:
        if args.estimate_only:
            estimate, refused = preflight(args.repo, mode, None, editors, client=args.llm_client)
        else:
            artifact = review(args.repo, mode, args.passage, editors, client=args.llm_client)
    except (LLMConfigError, NanoifError) as exc:
        print(f"ai review could not run: {exc}", file=sys.stderr)
        return 2
    if args.estimate_only:
        if refused is None:
            # AC-continuity-review-11: the estimate is posted before the review starts.
            print(estimate.summary())
            if args.github_output is not None:
                write_github_output(args.github_output, estimate.outputs())
            return 0
        # AC-continuity-review-35: the estimate does not fit under the monthly cap, so the
        # review is not started; the refusal is written for the reporter to publish.
        artifact = refused
    out = args.out or args.repo / "dist" / "ai-review.json"
    write_artifact(out, artifact, "ai_review")
    for line in summary_lines(artifact):
        print(line)
    print(f"Wrote {out}")
    return 0 if all(editor["status"] == "ok" for editor in artifact["editors"]) else 1


def _ai_eval(args: argparse.Namespace) -> int:
    import json
    import tempfile

    from nanoif.eval.report import to_json
    from nanoif.eval.run import run_eval
    from nanoif.llm.client import LLMClient
    from nanoif.llm.errors import LLMConfigError
    from nanoif.llm.profiles import Settings
    from nanoif.schemas.artifacts import write_artifact

    def could_not_run(reason: object) -> int:
        print(f"eval could not run: {reason}", file=sys.stderr)
        return 2

    try:
        client = args.llm_client or LLMClient(Settings.from_env())
    except LLMConfigError as exc:
        return could_not_run(exc)
    baseline = None
    if args.baseline is not None:
        try:
            baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return could_not_run(f"baseline {args.baseline} is unreadable: {exc}")
    fixture = args.fixture or args.repo / "tests" / "fixtures" / "eval-story"
    with tempfile.TemporaryDirectory(prefix="nanoif-eval-") as scratch:
        try:
            outcome = run_eval(fixture, client, Path(scratch) / "story", baseline)
        except (LLMConfigError, NanoifError) as exc:
            return could_not_run(exc)
    out = args.out or args.repo / "dist" / "eval-results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(outcome.scores), encoding="utf-8")
    markdown_path = out.with_suffix(".md")
    markdown_path.write_text(outcome.markdown, encoding="utf-8")
    review_path = out.with_name("eval-ai-review.json")
    write_artifact(review_path, outcome.review, "ai_review")
    print(outcome.markdown)
    if not outcome.review_ok:
        print("eval incomplete: an editor did not review every unit", file=sys.stderr)
    if not outcome.extraction_ok:
        extraction = outcome.extraction
        detail = f" ({extraction['reason']})" if extraction.get("reason") else ""
        print(f"eval incomplete: extraction {extraction['status']}{detail}", file=sys.stderr)
    if outcome.diff is not None and not outcome.diff["ok"]:
        print("eval below baseline", file=sys.stderr)
    print(f"Wrote {out}, {markdown_path} and {review_path}")
    return 0 if outcome.ok else 1


def _bible_extract(args: argparse.Namespace) -> int:
    from nanoif.bible.run import extract_bible
    from nanoif.bible.store import ExtractStore, resolve_store_dir
    from nanoif.llm.client import LLMClient
    from nanoif.llm.errors import LLMRunHalted
    from nanoif.llm.profiles import Settings

    if args.preview != (args.cache_out is not None):
        print("error: --preview and --cache-out go together", file=sys.stderr)
        return 2
    paths = ProjectPaths.from_repo(args.repo, cache=args.cache)
    mode = "full" if args.full else "incremental"
    diff_out = args.diff_out or paths.bible_diff
    store = ExtractStore.open(resolve_store_dir())

    def warn() -> None:
        # Store problems cost money, not correctness: GitHub annotations, never a failure.
        for warning in store.warnings:
            print(f"::warning::{warning}")

    try:
        client = args.llm_client or LLMClient(Settings.from_env())
        outcome = extract_bible(
            paths.repo, mode, client, paths.cache, args.dry_run, diff_out=diff_out, store=store,
            preview=args.preview, cache_out=args.cache_out,
        )
    except LLMRunHalted as exc:
        warn()
        print(f"bible extract did not run: {exc.reason}; nothing was written", file=sys.stderr)
        return 1
    except NanoifError as exc:
        warn()
        print(f"bible extract failed: {exc}; nothing was written", file=sys.stderr)
        return 1
    warn()
    print(outcome.summary)
    for failure in outcome.diff["passages_failed"]:
        print(f"not read: {failure['passage']}: {failure['reason']}")
    for pending in outcome.diff["pending"]:
        print(f"pending: {pending['entity']}: {pending['reason']}")
    if outcome.cache_written:
        print(f"Wrote {paths.cache}")
    if args.cache_out is not None:
        if outcome.cache_out_written:
            print(f"Wrote {args.cache_out}")
        else:
            print(f"No would-be cache written to {args.cache_out}: nothing has been extracted")
    print(f"Wrote {diff_out}")
    return outcome.exit_code


def _intent_check(args: argparse.Namespace) -> int:
    from nanoif.intent import check_repo

    findings = check_repo(args.repo.resolve())
    for finding in findings:
        print(finding.render())
    errors = sum(1 for f in findings if f.level == "error")
    print(f"intent check: {errors} error(s)")
    return 1 if errors else 0


def _intent_commit_msg(args: argparse.Namespace) -> int:
    from nanoif.intent.gate import check_staged

    message = args.message_file.read_text(encoding="utf-8")
    result = check_staged(args.repo.resolve(), message)
    if not result.ok:
        print(result.message, file=sys.stderr)
        return 1
    return 0


def _intent_range(args: argparse.Namespace) -> int:
    from nanoif.intent import check_range

    failures = check_range(args.repo.resolve(), args.base, args.head)
    for sha, result in failures:
        print(f"{sha[:12]}: {result.message}", file=sys.stderr)
    print(f"intent range {args.base}..{args.head}: {len(failures)} commit(s) failing")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="nanoif", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"nanoif {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    build = subparsers.add_parser("build", help="build story outputs")
    targets = build.add_subparsers(dest="target")
    core = _add_build(
        targets, "core", "parse the compiled story into the core artifacts", _build_core
    )
    core.add_argument("--html", type=Path, default=None, help="Tweego-compiled HTML to parse")
    core.add_argument(
        "--lookup", type=Path, default=None, help="where to write PathIdLookup.twee"
    )
    allpaths = _add_build(targets, "allpaths", "enumerate every path", _build_allpaths)
    allpaths.add_argument(
        "--base-ref",
        default=None,
        help="git ref to categorize against (default: GITHUB_MERGE_BASE, else HEAD)",
    )
    metrics = _add_build(targets, "metrics", "writing statistics page", _build_metrics)
    metrics.add_argument("--include", nargs="+", help="only files whose names start with these")
    metrics.add_argument("--exclude", nargs="+", help="skip files whose names start with these")
    metrics.add_argument("--top", type=int, default=10, help="longest passages to list")
    bible = _add_build(targets, "story-bible", "render the Story Bible", _build_story_bible)
    bible.add_argument(
        "--cache", type=Path, default=None, help="default: <repo>/ai/story-bible-cache.json"
    )
    bible.add_argument(
        "--extraction-result",
        choices=["success", "failure", "cancelled", "skipped"],
        default="success",
        help="how the latest extraction job ended; the page says when it did not succeed",
    )
    bible.add_argument(
        "--preview-passages",
        type=Path,
        default=None,
        help="pull request preview (ADR-026): dist/changes.json; facts from these passages are "
        "marked as from this pull request, and no canon pack is built",
    )
    bible.add_argument(
        "--preview-diff",
        type=Path,
        default=None,
        help="the preview extraction's bible-diff.json; its failed passages are listed as not "
        "read with the reason",
    )
    bible.add_argument(
        "--preview-reason",
        default=None,
        help="why the preview extraction did not run; given for every unread pull request "
        "passage",
    )
    canon = _add_build(
        targets, "canon-pack", "the Continuity Editor's canon (no model)", _build_canon_pack
    )
    canon.add_argument(
        "--cache", type=Path, default=None, help="default: <repo>/ai/story-bible-cache.json"
    )
    _add_build(targets, "passages", "passage index page", _build_passages)
    _add_build(targets, "landing", "landing page with the story title", _build_landing)
    everything = _add_build(
        targets, "all", "every build step, ending with the landing page", _build_all
    )
    everything.add_argument("--html", type=Path, default=None, help=argparse.SUPPRESS)
    everything.add_argument("--lookup", type=Path, default=None, help=argparse.SUPPRESS)
    everything.add_argument("--base-ref", default=None, help="see `build allpaths`")
    everything.add_argument("--cache", type=Path, default=None, help="see `build story-bible`")
    everything.set_defaults(include=None, exclude=None, top=10)
    build.set_defaults(handler=lambda _args: (build.print_help(), 2)[1])

    lint = subparsers.add_parser("lint", help="report Twee formatting issues (never edits files)")
    lint.add_argument("path", type=Path, help=".twee file or directory")
    lint.add_argument("--format", choices=["text", "github"], default="text")
    lint.add_argument(
        "--exit-zero",
        action="store_true",
        help="report issues but exit 0; a linter error still exits 1 (report-only CI)",
    )
    lint.set_defaults(handler=_lint)

    check = subparsers.add_parser("check", help="deterministic story checks")
    checks = check.add_subparsers(dest="check")
    structure = checks.add_parser(
        "structure", help="broken links, duplicates, orphans, StoryData, naming, overrides"
    )
    structure.add_argument("src", type=Path, help="story source directory")
    structure.add_argument("--format", choices=["text", "json", "github"], default="text")
    structure.add_argument(
        "--overrides", type=Path, default=None, help="default: <src>/../story-overrides.txt"
    )
    structure.add_argument(
        "--exit-zero",
        action="store_true",
        help="report errors but exit 0 (report-only rollout)",
    )
    structure.set_defaults(handler=_check_structure)
    check.set_defaults(handler=lambda _args: (check.print_help(), 2)[1])

    ai = subparsers.add_parser("ai", help="AI editors (paid inference)")
    ai_commands = ai.add_subparsers(dest="ai_command")
    ai_review = ai_commands.add_parser(
        "review",
        help="run the Continuity and Style editors; exit 1 when an editor could not finish",
    )
    ai_review.add_argument("--repo", type=Path, required=True, help="repository root (built)")
    ai_review.add_argument(
        "--mode",
        choices=["changed", "all", "passage"],
        default=None,
        help="changed (default), all, or passage (with --passage)",
    )
    ai_review.add_argument("--passage", default=None, help="passage name for --mode passage")
    ai_review.add_argument(
        "--editors", default="continuity,style", help="comma-separated: continuity,style"
    )
    ai_review.add_argument(
        "--out", type=Path, default=None, help="default: <repo>/dist/ai-review.json"
    )
    ai_review.add_argument(
        "--estimate-only",
        action="store_true",
        help="with --mode all: print the estimated cost and check the monthly cap for it, "
        "calling no model; exit 0 when the review may start, else write the not-run "
        "review to --out and exit 1",
    )
    ai_review.add_argument(
        "--github-output",
        type=Path,
        default=None,
        help="with --estimate-only: append estimate_usd, estimate_calls and estimate_priced",
    )
    ai_review.set_defaults(handler=_ai_review)
    ai_eval = ai_commands.add_parser(
        "eval",
        help="extract the eval story's Story Bible, review it, and score both against truth.json",
    )
    ai_eval.add_argument("--repo", type=Path, required=True, help="repository root")
    ai_eval.add_argument(
        "--fixture", type=Path, default=None, help="default: <repo>/tests/fixtures/eval-story"
    )
    ai_eval.add_argument(
        "--out", type=Path, default=None, help="default: <repo>/dist/eval-results.json"
    )
    ai_eval.add_argument(
        "--baseline", type=Path, default=None, help="tests/eval/baselines/<profile>.json"
    )
    ai_eval.set_defaults(handler=_ai_eval)
    ai.set_defaults(handler=lambda _args: (ai.print_help(), 2)[1])

    bible_cmd = subparsers.add_parser("bible", help="Story Bible extraction (paid inference)")
    bible_commands = bible_cmd.add_subparsers(dest="bible_command")
    extract = bible_commands.add_parser(
        "extract",
        help="extract changed passages into ai/story-bible-cache.json; exit 3 when partial",
    )
    extract.add_argument("--repo", type=Path, required=True, help="repository root")
    which = extract.add_mutually_exclusive_group()
    which.add_argument(
        "--incremental", action="store_true", help="only passages whose text changed (default)"
    )
    which.add_argument("--full", action="store_true", help="re-read every passage, keeping ids")
    which.add_argument(
        "--preview",
        action="store_true",
        help="pull request preview: incremental, no reconcile, never writes ai/ (needs "
        "--cache-out)",
    )
    extract.add_argument(
        "--dry-run", action="store_true", help="write only the diff, never the cache"
    )
    extract.add_argument(
        "--cache-out",
        type=Path,
        default=None,
        help="with --preview: where to write the would-be cache for the preview Story Bible",
    )
    extract.add_argument(
        "--cache", type=Path, default=None, help="default: <repo>/ai/story-bible-cache.json"
    )
    extract.add_argument(
        "--diff-out", type=Path, default=None, help="default: <repo>/dist/bible-diff.json"
    )
    extract.set_defaults(handler=_bible_extract)
    bible_cmd.set_defaults(handler=lambda _args: (bible_cmd.print_help(), 2)[1])
    intent = subparsers.add_parser("intent", help="traceability of intent docs, tests and commits")
    intents = intent.add_subparsers(dest="intent_command")
    icheck = intents.add_parser("check", help="criteria ids, test citations and ADR statuses")
    icheck.add_argument("--repo", type=Path, required=True)
    icheck.set_defaults(handler=_intent_check)
    imsg = intents.add_parser("commit-msg", help="git commit-msg hook: gate staged changes")
    imsg.add_argument("message_file", type=Path)
    imsg.add_argument("--repo", type=Path, required=True)
    imsg.set_defaults(handler=_intent_commit_msg)
    irange = intents.add_parser("range", help="gate every non-merge commit in base..head")
    irange.add_argument("--repo", type=Path, required=True)
    irange.add_argument("--base", required=True)
    irange.add_argument("--head", default="HEAD")
    irange.set_defaults(handler=_intent_range)
    intent.set_defaults(handler=lambda _args: (intent.print_help(), 2)[1])

    from nanoif.github.cli import register as register_github

    register_github(subparsers)
    return parser


def main(argv: list[str] | None = None, *, client: Completer | None = None) -> int:
    """Run the CLI and return an exit status.

    Args:
        argv: Arguments without the program name; defaults to ``sys.argv[1:]``.
        client: Completer for the ``ai`` commands instead of one built from the
            ``NANOIF_LLM_*`` settings (tests inject a fake here).

    Returns:
        The exit status.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    args.llm_client = client
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return args.handler(args)
    except NanoifError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
