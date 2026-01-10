"""Command line interface."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from daylog.config import DEFAULT_CONFIG_PATH, load_config
from daylog.io.validate import validate_processed_dir
from daylog.pipeline.run import run_pipeline


def _configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def _run(args: argparse.Namespace) -> int:
    _configure_logging(args.debug)
    config = load_config(Path(args.config))
    outputs = run_pipeline(
        input_path=Path(args.input),
        config=config,
        date_override=args.date,
        start_time=args.start_time,
        use_mtime=args.use_mtime,
    )
    for out in outputs:
        logging.info("Wrote outputs to %s", out)
    return 0


def _validate(args: argparse.Namespace) -> int:
    _configure_logging(args.debug)
    input_path = Path(args.input)
    processed_dir = input_path / "processed" if (input_path / "processed").exists() else input_path
    errors = validate_processed_dir(processed_dir)
    if errors:
        for error in errors:
            logging.error(error)
        return 1
    logging.info("Validation passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daylog")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the daylog pipeline")
    run_parser.add_argument("--input", required=True, help="input file or folder")
    run_parser.add_argument("--date", help="override date as YYYY-MM-DD")
    run_parser.add_argument("--start-time", help="absolute start time ISO string")
    run_parser.add_argument(
        "--use-mtime", action="store_true", help="use input file mtime as start time"
    )
    run_parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH), help="path to config TOML"
    )
    run_parser.set_defaults(func=_run)

    validate_parser = subparsers.add_parser("validate", help="validate output folder")
    validate_parser.add_argument("--input", required=True, help="processed or recording folder")
    validate_parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH), help="path to config TOML"
    )
    validate_parser.set_defaults(func=_validate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())