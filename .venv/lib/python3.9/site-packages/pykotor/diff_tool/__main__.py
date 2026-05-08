"""Entry point for running pykotor.diff_tool as a module (python -m pykotor.diff_tool)."""

from __future__ import annotations

import argparse
import sys

from collections.abc import Sequence
from typing import Any


def main(argv: Sequence[str] | None = None) -> int:
    from pykotor.diff_tool.cli import execute_cli, parse_args

    args: argparse.Namespace | Any | object = (
        parse_args()
        if argv is None
        else (
            parse_args.__wrapped__(argv)
            if hasattr(parse_args, "__wrapped__")
            else _parse_with_argv(argv)
        )
    )
    try:
        execute_cli(args)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    return 0


def _parse_with_argv(argv: Sequence[str]) -> object:
    """Parse arguments from an explicit argv list."""
    old_argv = sys.argv
    try:
        sys.argv = ["pykotor.diff_tool", *argv]
        from pykotor.diff_tool.cli import parse_args

        return parse_args()
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    sys.exit(main())
