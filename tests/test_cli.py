"""Command line behaviour, including the commands the README documents."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from aml import __version__
from aml.cli import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "data_cleaning.py",
    "feature_engineering.py",
    "fraud_detection.py",
    "customer_risk.py",
    "generate_alert_report.py",
)


def copy_project(destination: Path) -> Path:
    ignore = shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.egg-info", "build", "dist")
    shutil.copytree(PROJECT_ROOT, destination, ignore=ignore)
    return destination


def test_help_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    assert "aml-risk" in capsys.readouterr().out


def test_version_is_printed(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_runs_the_whole_pipeline(data_root, capsys):
    assert main(["--root", str(data_root)]) == 0
    out = capsys.readouterr().out
    assert "alerts: 90" in out
    assert "customers scored: 300" in out
    assert (data_root / "reports" / "data_quality.json").is_file()


def test_global_options_are_accepted_after_the_command(data_root, capsys):
    assert main(["clean", "--root", str(data_root)]) == 0
    assert "transactions scored" in capsys.readouterr().out
    assert (data_root / "data" / "processed" / "transactions_clean.csv").is_file()


def test_root_option_accepts_the_equals_form(data_root, capsys):
    assert main([f"--root={data_root}", "clean", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_quiet_suppresses_the_summary(data_root, capsys):
    assert main(["all", "--root", str(data_root), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_unknown_command_exits_with_two(capsys):
    assert main(["publish"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_missing_configuration_file_exits_with_two(data_root, capsys):
    assert main(["all", "--root", str(data_root), "--config", str(data_root / "nope.toml")]) == 2
    assert "not found" in capsys.readouterr().err


def test_invalid_configuration_is_named(data_root, capsys):
    config = data_root / "config.toml"
    config.write_text("[rules]\nalert_threshold = 0\n", encoding="utf-8")
    assert main(["all", "--root", str(data_root), "--config", str(config)]) == 2
    assert "rules.alert_threshold" in capsys.readouterr().err


def test_configuration_is_applied_end_to_end(data_root, capsys):
    config = data_root / "config.toml"
    config.write_text("[rules]\nhigh_value_threshold = 20000\n", encoding="utf-8")
    assert main(["all", "--root", str(data_root), "--config", str(config)]) == 0
    out = capsys.readouterr().out
    assert "alerts: 74" in out


def test_report_prints_the_requested_number_of_customers(built_project, capsys):
    assert main(["report", "--root", str(built_project), "--top", "3"]) == 0
    out = capsys.readouterr().out
    table_lines = [line for line in out.splitlines() if line.strip().startswith("C0")]
    assert len(table_lines) == 3


@pytest.mark.parametrize("value", ["0", "-1"])
def test_report_rejects_a_nonsense_top_value(built_project, capsys, value):
    assert main(["report", "--root", str(built_project), "--top", value]) == 2
    assert "--top must be at least 1" in capsys.readouterr().err


def test_module_entry_point_works(data_root):
    completed = subprocess.run(
        [sys.executable, "-m", "aml", "clean", "--root", str(data_root), "--quiet"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (data_root / "data" / "processed" / "transactions_clean.csv").is_file()


def test_documented_scripts_run_in_order(tmp_path):
    """Every command in the README has to keep working from a clean copy."""
    root = copy_project(tmp_path / "project")
    for script in SCRIPTS:
        completed = subprocess.run(
            [sys.executable, f"src/{script}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, f"{script} failed:\n{completed.stderr}"
        assert "Traceback" not in completed.stderr

    alerts = (root / "reports" / "sample_alert_report.csv").read_bytes()
    assert alerts.count(b"\r\n") == 91
    assert alerts.count(b"\n") == 91
    summary = (root / "reports" / "alert_summary.csv").read_bytes()
    assert b"High,55" in summary
