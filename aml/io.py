"""CSV input and output helpers.

The repository ships its processed datasets and reports as CRLF files.  Python
on a POSIX platform writes ``\\n`` by default, so every run used to rewrite the
whole repository with different line endings.  Output is written with an
explicit ``\\r\\n`` terminator so a re-run produces the same bytes on any
platform.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

CSV_LINETERMINATOR = "\r\n"


class DataError(ValueError):
    """Raised when an input file is missing, unreadable or malformed."""


def read_table(
    path: str | Path,
    *,
    parse_dates: Sequence[str] = (),
    required: Iterable[str] = (),
) -> pd.DataFrame:
    """Read a CSV file and check that the expected columns are present."""
    table_path = Path(path)
    if not table_path.is_file():
        raise DataError(f"input file not found: {table_path}")
    try:
        frame = pd.read_csv(table_path, parse_dates=list(parse_dates))
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as error:
        raise DataError(f"cannot read {table_path.name}: {error}") from error
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise DataError(
            f"{table_path.name} is missing required column(s): {', '.join(missing)}"
        )
    return frame


def write_table(frame: pd.DataFrame, path: str | Path) -> Path:
    """Write a CSV file with the repository's CRLF convention."""
    table_path = Path(path)
    table_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(table_path, index=False, lineterminator=CSV_LINETERMINATOR)
    return table_path


def write_json(payload: object, path: str | Path) -> Path:
    """Write a JSON file with the repository's CRLF convention."""
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2).replace("\n", CSV_LINETERMINATOR)
    json_path.write_bytes((text + CSV_LINETERMINATOR).encode("utf-8"))
    return json_path
