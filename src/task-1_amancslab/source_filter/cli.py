"""Command-line interface for source normalisation and filtering."""

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Define the supported command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate, normalise, deduplicate and filter "
            "saved source records."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input JSON file.",
    )

    parser.add_argument(
        "--policy",
        required=True,
        help="Path to the source policy JSON file.",
    )

    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where results will be written.",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Execute the pipeline and report its result."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summary = run_pipeline(
            input_path=args.input,
            policy_path=args.policy,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("Source normalisation and filtering completed.")
    print()

    for name, value in summary.items():
        label = name.replace("_", " ").capitalize()
        print(f"{label}: {value}")

    print()
    print(f"Output directory: {Path(args.output_dir).resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())