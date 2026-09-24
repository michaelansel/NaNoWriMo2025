"""Command-line entry point for ``nanoif``.

Subcommands are registered by the modules that own them as they are migrated
into the package. Until then this only reports the version so that
``pip install -e .`` and the CI job have something to exercise.
"""

from __future__ import annotations

import argparse
import sys

from nanoif import __version__


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="nanoif", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"nanoif {__version__}")
    parser.add_subparsers(dest="command")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an exit status."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
