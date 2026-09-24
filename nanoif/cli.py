"""Command-line entry point for ``nanoif``.

Subcommands are registered by the modules that own them as they are migrated
into the package.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nanoif import __version__
from nanoif.errors import NanoifError


def _add_build_core(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "core",
        help="parse Tweego HTML into story_graph.json, passages_deduplicated.json and "
        "the PathIdLookup passage",
    )
    parser.add_argument("--html", type=Path, required=True, help="Tweego-compiled HTML to parse")
    parser.add_argument("--src", type=Path, required=True, help="story source directory")
    parser.add_argument("--out", type=Path, required=True, help="artifact directory")
    parser.add_argument(
        "--lookup",
        type=Path,
        default=None,
        help="where to write PathIdLookup.twee (default: <src>/PathIdLookup.twee)",
    )
    parser.set_defaults(handler=_run_build_core)


def _run_build_core(args: argparse.Namespace) -> int:
    from nanoif.build.core import build_core

    result = build_core(
        html_path=args.html,
        src_dir=args.src,
        out_dir=args.out,
        lookup_path=args.lookup or args.src / "PathIdLookup.twee",
    )
    print(f"Parsed {result.passage_count} passages; start passage: {result.start_passage}")
    print(f"Wrote {result.story_graph_path}")
    print(f"Wrote {result.passages_path}")
    print(f"Wrote {result.lookup_path} ({result.path_count} routes)")
    return 0


def _add_build_allpaths(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "allpaths",
        help="enumerate every path and write the allpaths outputs under --out",
    )
    parser.add_argument("--repo", type=Path, required=True, help="repository root")
    parser.add_argument("--src", type=Path, required=True, help="story source directory")
    parser.add_argument(
        "--story-graph", type=Path, required=True, help="story_graph.json from `build core`"
    )
    parser.add_argument("--out", type=Path, required=True, help="output directory (dist/)")
    parser.add_argument(
        "--base-ref",
        default=None,
        help="git ref to categorize against (default: GITHUB_MERGE_BASE, else HEAD)",
    )
    parser.set_defaults(handler=_run_build_allpaths)


def _run_build_allpaths(args: argparse.Namespace) -> int:
    import os

    from nanoif.formats.allpaths import AllPathsConfig, resolve_base_ref, run

    base_ref = args.base_ref or resolve_base_ref(os.environ)
    result = run(
        AllPathsConfig(
            repo_root=args.repo,
            src_dir=args.src,
            story_graph_path=args.story_graph,
            output_dir=args.out,
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
    print(f"Wrote {result.html_path} and {len(result.paths)} path files under {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="nanoif", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"nanoif {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    build = subparsers.add_parser("build", help="build story outputs")
    build_targets = build.add_subparsers(dest="target")
    _add_build_core(build_targets)
    _add_build_allpaths(build_targets)
    build.set_defaults(handler=lambda _args: (build.print_help(), 2)[1])
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
