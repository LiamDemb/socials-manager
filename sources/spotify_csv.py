"""Pinned parser for the two proven Spotify for Artists CSV shapes. Unknown shapes are rejected, not guessed."""
import csv
import io
from dataclasses import dataclass, field
from datetime import date

from .metric_registry import AUDIENCE_HEADER, RECORDING_HEADER, column_metric_ids

PARSER_VERSION = "spotify-s4a-csv-v1"
MAX_COUNT = 2**63 - 1
MAX_ROWS = 20000


@dataclass
class ParseResult:
    scope: str | None
    header: list
    values: list = field(default_factory=list)  # (row_number, metric_id, date, int)
    issues: list = field(default_factory=list)  # (row_number, column, code, message)
    source_rows: int = 0


def detect_scope(header):
    if header == AUDIENCE_HEADER:
        return "artist"
    if header == RECORDING_HEADER:
        return "recording"
    return None


def decode(raw: bytes):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def parse(raw: bytes) -> ParseResult:
    text = decode(raw)
    if text is None:
        return ParseResult(None, [], issues=[(None, "", "encoding", "The file is not UTF-8 text.")])
    if "\x00" in text:
        return ParseResult(None, [], issues=[(None, "", "binary", "The file contains binary data.")])
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        return ParseResult(None, [], issues=[(None, "", "empty", "The file is empty.")])
    header = [h.strip() for h in header]
    scope = detect_scope(header)
    result = ParseResult(scope, header)
    if scope is None:
        result.issues.append((1, "", "unknown_header",
                              "Unrecognised columns. Supported: the Audience timeline export and a song's streams timeline export."))
        return result
    columns = column_metric_ids(scope)
    seen_dates = {}
    for index, row in enumerate(reader, start=2):
        if not row or all(not c.strip() for c in row):
            continue
        result.source_rows += 1
        if result.source_rows > MAX_ROWS:
            result.issues.append((index, "", "too_many_rows", f"More than {MAX_ROWS} rows."))
            break
        if len(row) != len(header):
            result.issues.append((index, "", "column_count", f"Expected {len(header)} columns, found {len(row)}."))
            continue
        raw_date = row[0].strip()
        try:
            day = date.fromisoformat(raw_date)
            if len(raw_date) != 10:
                raise ValueError
        except ValueError:
            result.issues.append((index, "date", "invalid_date", f"'{raw_date[:20]}' is not a YYYY-MM-DD date."))
            continue
        if day in seen_dates:
            result.issues.append((index, "date", "duplicate_date", f"{day} also appears on row {seen_dates[day]}."))
            continue
        seen_dates[day] = index
        for (column, metric_id), cell in zip(columns, row[1:]):
            cell = cell.strip()
            if cell == "":
                result.issues.append((index, column, "blank_count", "Blank value. Missing is not zero; fix or remove the row."))
                continue
            if not cell.isdigit():
                code = "negative_count" if cell.startswith("-") else "not_integer"
                result.issues.append((index, column, code, f"'{cell[:20]}' is not a non-negative whole number."))
                continue
            value = int(cell)
            if value > MAX_COUNT:
                result.issues.append((index, column, "oversize_count", "Value is too large."))
                continue
            result.values.append((index, metric_id, day, value))
    if result.source_rows == 0 and not result.issues:
        result.issues.append((None, "", "no_rows", "The file has a header but no data rows."))
    return result


def source_shaped_csv(scope, rows_by_date):
    """Rebuild the provider's CSV shape. rows_by_date: {date: {column: value}}."""
    header = AUDIENCE_HEADER if scope == "artist" else RECORDING_HEADER
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    for day in sorted(rows_by_date):
        values = rows_by_date[day]
        writer.writerow([day.isoformat(), *[values.get(c, "") for c in header[1:]]])
    return out.getvalue().encode()
