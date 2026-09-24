"""Command-line entry point for ``nanoif``.

Build commands take ``--repo`` and derive every other path from it
(``src/``, ``lib/artifacts/``, ``dist/``, ``story-bible-cache.json``); each
can be overridden. Nothing is resolved against the current directory.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from nanoif import __version__
from nanoif.build.paths import ProjectPaths
from nanoif.errors import NanoifError

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


def _build_story_bible(args: argparse.Namespace) -> int:
    from nanoif.formats.story_bible import StoryBibleConfig, build_story_bible

    paths = _paths(args)
    result = build_story_bible(
        StoryBibleConfig(
            repo_root=paths.repo,
            cache_path=paths.cache,
            story_graph_path=paths.story_graph,
            passages_path=paths.passages,
            output_dir=paths.dist,
        )
    )
    if result.placeholder:
        print(f"Story Bible cache not found at {paths.cache}; rendered the placeholder page")
    else:
        stats = result.statistics
        print(
            f"Story Bible ({result.view_type}): {stats['total_constants']} constants, "
            f"{stats['total_variables']} variables, {stats['total_characters']} characters"
        )
    print(f"Wrote {result.html_path} and {result.json_path}")
    return 0


def _build_passages(args: argparse.Namespace) -> int:
    from nanoif.formats.passages import build_passages

    paths = _paths(args)
    result = build_passages(paths.src, paths.story_graph, paths.dist)
    print(f"Passage index: {result.passage_count} passages in {result.file_count} files")
    print(f"Wrote {result.html_path}")
    return 0


def _build_all(args: argparse.Namespace) -> int:
    for step in (_build_core, _build_allpaths, _build_metrics, _build_story_bible, _build_passages):
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
    return 1 if violations else 0


def _check_structure(args: argparse.Namespace) -> int:
    from nanoif.check.structure import check_structure, format_findings

    overrides = args.overrides or args.src.parent / "story-overrides.txt"
    findings = check_structure(args.src, overrides_path=overrides)
    output = format_findings(findings, args.format, args.src.resolve().parent)
    if output:
        print(output)
    errors = sum(1 for finding in findings if finding.level == "error")
    warnings = sum(1 for finding in findings if finding.level == "warning")
    infos = len(findings) - errors - warnings
    print(f"{errors} error(s), {warnings} warning(s), {infos} info", file=sys.stderr)
    return 1 if errors and not args.exit_zero else 0


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
    bible.add_argument("--cache", type=Path, default=None, help="extraction cache")
    _add_build(targets, "passages", "passage index page", _build_passages)
    everything = _add_build(
        targets, "all", "core, allpaths, metrics, story-bible and passages", _build_all
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
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
