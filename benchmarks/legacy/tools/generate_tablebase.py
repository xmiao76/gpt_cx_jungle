from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jungle.ai.tablebase import (
    TablebaseError,
    default_tablebase_path,
    generate_tablebase,
    verify_tablebase,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or verify the exact Jungle two-piece tablebase."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_tablebase_path(),
        help="asset path (default: bundled source asset)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the existing asset instead of writing it",
    )
    parser.add_argument(
        "--reproduce",
        action="store_true",
        help="with --check, regenerate and compare every byte",
    )
    return parser


def _progress(message: str) -> None:
    print(f"[tablebase] {message}", flush=True)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.reproduce and not args.check:
        _parser().error("--reproduce requires --check")
    try:
        if args.check:
            stats = verify_tablebase(args.output, reproduce=args.reproduce, progress=_progress)
            if stats is None:
                print(f"Verified {args.output}")
            else:
                print(
                    f"Reproduced {args.output}: {stats.valid_positions:,} positions, "
                    f"max DTM {stats.max_distance}, {stats.elapsed_seconds:.2f}s"
                )
            return 0

        stats = generate_tablebase(args.output, progress=_progress)
        print(
            f"Generated {args.output}: {stats.valid_positions:,} positions "
            f"({stats.wins:,} W / {stats.draws:,} D / {stats.losses:,} L), "
            f"{stats.edges:,} edges, max DTM {stats.max_distance}, "
            f"{stats.elapsed_seconds:.2f}s"
        )
        return 0
    except (OSError, TablebaseError, ValueError) as exc:
        print(f"tablebase error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
