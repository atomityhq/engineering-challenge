"""Dependency-free command-line boundary for offline G2 file reports."""

import argparse
import json
import logging
from pathlib import Path
from collections.abc import Sequence

from .errors import ValidationError
from .fixtures import load_fixture
from .policy import load_policy
from .reports import evaluate_case, report_to_dict
from .sensitivity import compare_weights, comparison_to_json

SUBMISSION = Path(__file__).resolve().parents[1]
STARTER_FIXTURE = SUBMISSION.parents[1] / "fixtures" / "g2-cases.json"
DEFAULT_POLICY = SUBMISSION / "config" / "policy.json"
ADDITIONAL_FIXTURE = SUBMISSION / "fixtures" / "additional-cases.json"
LOGGER = logging.getLogger("g2.cli")


class _SafeParser(argparse.ArgumentParser):
    """Avoid reflecting external argument values in parser errors."""

    def error(self, message: str) -> None:
        LOGGER.error("ARGUMENT_ERROR: Invalid arguments; consult --help.")
        raise SystemExit(2)


def _parser() -> argparse.ArgumentParser:
    parser = _SafeParser(description="Offline synthetic G2 evaluation; no installation required.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, default, description in (
        ("evaluate", STARTER_FIXTURE, "Evaluate every fixture case with the selected policy."),
        ("compare", ADDITIONAL_FIXTURE, "Compare chosen, equal, and authority-heavy weights."),
    ):
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("--fixture", type=Path, default=default,
                             help="UTF-8 synthetic fixture JSON; defaults are module-relative.")
        command.add_argument("--config", type=Path, default=DEFAULT_POLICY,
                             help="UTF-8 policy JSON; default is submission config/policy.json.")
        command.add_argument("--output", type=Path, required=True,
                             help="New UTF-8 JSON file; parent must exist; existing files are refused.")
    return parser


def _protect_inputs(output: Path, fixture: Path, config: Path) -> None:
    """Refuse malformed paths and aliases of all protected inputs."""
    if any("\x00" in str(path) for path in (output, fixture, config)):
        raise ValidationError("INVALID_PATH", "$.paths", "Filesystem paths must not contain null bytes.")
    for source in (fixture, config, STARTER_FIXTURE, DEFAULT_POLICY, ADDITIONAL_FIXTURE):
        if output.resolve() == source.resolve() or (
            output.exists() and source.exists() and output.samefile(source)
        ):
            raise ValidationError("OUTPUT_INPUT_CONFLICT", "$.output", "Output must not overwrite an input file.")


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 for completed reports and 2 for argument, validation, or I/O errors.

    Evaluation decisions are data, not process failures. Existing destinations
    are refused using exclusive creation; output parents are never created.
    """
    logging.basicConfig(level=logging.ERROR, format="%(message)s")
    args = _parser().parse_args(argv)
    try:
        _protect_inputs(args.output, args.fixture, args.config)
        inputs = load_fixture(args.fixture)
        policy = load_policy(args.config)
        if args.command == "compare":
            text = comparison_to_json(compare_weights(inputs, policy))
        else:
            data = {
                "schema_version": "1.0", "gate": "G2", "synthetic": inputs.synthetic,
                "as_of": inputs.as_of.isoformat(),
                "reports": [report_to_dict(evaluate_case(case, inputs.as_of,
                            inputs.news_max_event_age_days, policy)) for case in inputs.cases],
            }
            text = json.dumps(data, ensure_ascii=False, allow_nan=False,
                              sort_keys=True, indent=2) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(text)
    except ValidationError as error:
        LOGGER.error("%s: %s", error.issue.code, error.issue.message)
        return 2
    except FileExistsError:
        LOGGER.error("OUTPUT_EXISTS: Existing output files are never overwritten.")
        return 2
    except (OSError, UnicodeError, RuntimeError):
        LOGGER.error("FILE_IO_ERROR: Could not resolve or write the output file.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
