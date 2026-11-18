"""Command line interface for the AML transaction risk pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config
from .io import DataError, read_table
from .pipeline import STEPS, run_pipeline
from .scoring import top_risky_customers

COMMANDS = (*STEPS, "all")
GLOBAL_VALUE_OPTIONS = ("--root", "--config")
GLOBAL_FLAGS = ("-q", "--quiet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aml-risk",
        description=(
            "Run the AML transaction risk pipeline: clean the synthetic datasets, "
            "engineer features, apply the monitoring rules, score customers and "
            "refresh the reports."
        ),
    )
    parser.add_argument("--root", default=None, help="project root (defaults to the current directory)")
    parser.add_argument("--config", default=None, help="TOML or JSON configuration file")
    parser.add_argument("-q", "--quiet", action="store_true", help="only report errors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.add_parser("clean", help="clean the raw synthetic datasets")
    subparsers.add_parser("features", help="build customer and transaction features")
    subparsers.add_parser("monitor", help="apply the monitoring rules and write alerts")
    subparsers.add_parser("score", help="score customers")
    report = subparsers.add_parser("report", help="refresh the alert summary and rule breakdown")
    report.add_argument(
        "--top",
        type=int,
        default=5,
        metavar="N",
        help="how many of the highest scoring customers to print (default: 5)",
    )
    subparsers.add_parser("all", help="run every step in order (default)")
    return parser


def _split_global_options(argv: list[str]) -> tuple[dict[str, object], list[str]]:
    """Accept ``--root``/``--config``/``--quiet`` before or after the sub-command."""
    options: dict[str, object] = {}
    rest: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        name, separator, inline = token.partition("=")
        if separator and name in GLOBAL_VALUE_OPTIONS:
            options[name[2:]] = inline
            index += 1
            continue
        if token in GLOBAL_VALUE_OPTIONS:
            if index + 1 >= len(argv):
                raise SystemExit(f"aml-risk: error: {token} needs a value")
            options[token[2:]] = argv[index + 1]
            index += 2
            continue
        if token in GLOBAL_FLAGS:
            options["quiet"] = True
            index += 1
            continue
        rest.append(token)
        index += 1
    return options, rest


def _normalise(argv: list[str]) -> tuple[dict[str, object], list[str]]:
    options, rest = _split_global_options(argv)
    if not rest:
        rest = ["all"]
        return options, rest
    first = rest[0]
    if first in {"-h", "--help", "--version"}:
        return options, rest
    if not first.startswith("-") and first not in COMMANDS:
        raise SystemExit(
            f"aml-risk: error: unknown command {first!r}; choose from {', '.join(COMMANDS)}"
        )
    if first.startswith("-"):
        rest = ["all", *rest]
    return options, rest


def _print_summary(summary, config, quiet: bool) -> None:
    if quiet:
        return
    alert_tiers = ", ".join(f"{label} {count}" for label, count in summary.alert_tiers.items())
    print(f"transactions scored: {summary.transactions_cleaned:,}")
    print(f"alerts: {summary.alerts:,} ({alert_tiers})")
    if summary.customers_scored:
        print(f"customers scored: {summary.customers_scored:,}")
    print(f"alert threshold: {config.rules.alert_threshold:g}")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    try:
        options, rest = _normalise(raw)
    except SystemExit as stop:
        print(str(stop), file=sys.stderr)
        return 2

    args = parser.parse_args(rest)
    root_value = options.get("root", args.root)
    root = Path(root_value) if root_value else Path.cwd()
    config_path = options.get("config", args.config)
    quiet = bool(options.get("quiet", args.quiet))

    steps = STEPS if args.command == "all" else (args.command,)
    top = getattr(args, "top", None) if args.command == "report" else None

    try:
        if top is not None and top < 1:
            raise ValueError(f"--top must be at least 1, got {top}")
        config = load_config(config_path)
        summary = run_pipeline(root, config, steps)
        if top is not None:
            risk_file = root / "data" / "processed" / "customer_risk.csv"
            if risk_file.is_file():
                scored = read_table(risk_file)
                top_customers = top_risky_customers(scored, top)
                if not quiet:
                    print()
                    print(top_customers.to_string(index=False))
            elif not quiet:
                print(f"no customer scores at {risk_file}; run the score step first")
    except (ConfigError, DataError, FileNotFoundError, ValueError) as error:
        print(f"aml-risk: error: {error}", file=sys.stderr)
        return 2

    _print_summary(summary, config, quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
