"""JSON-safe snapshots for JSONField columns (dates, UUIDs, nested structures)."""
from datetime import date, datetime
from decimal import Decimal
import uuid


def jsonable_snapshot(value):
    """Return a structure safe for Django JSONField and json.dumps."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): jsonable_snapshot(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable_snapshot(v) for v in value]
    if isinstance(value, set):
        return [jsonable_snapshot(v) for v in sorted(value, key=str)]
    return str(value)
