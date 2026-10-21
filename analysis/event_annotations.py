"""Preserve session context in portable MNE annotation descriptions.

Legacy four-column files and manual labels remain verbatim. Structured session
events carry their context in the description so a FIF export is self-contained.
Invalidation is resolved across the complete event file, including events that
are later excluded because their sample position is outside the recording.
"""
import math


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        if value.is_integer():
            return str(int(value))
    return str(value)


def event_descriptions(rows):
    """Return one description per row; incomplete attempts are never called valid."""
    rows = [{key: _text(value) for key, value in row.items()} for row in rows]

    def trial_key(row):
        if row.get("source") != "automatic" or row.get("trial", "") in ("", "0"):
            return None
        return tuple(row.get(field, "") for field in ("run", "block", "trial", "attempt"))

    invalid, completed = set(), set()
    for row in rows:
        key = trial_key(row)
        if key is not None:
            if row["label"] == "trial_invalidated":
                invalid.add(key)
            elif row["label"] == "trial_end":
                completed.add(key)

    descriptions = []
    fields = ("run", "condition", "block", "trial", "attempt", "phase", "start_number", "subtract", "reason")
    for row in rows:
        if row.get("source") != "automatic":
            descriptions.append(row["label"])
            continue
        parts = [row["label"]]
        for field in fields:
            value = row.get(field, "")
            if value and (field not in ("start_number", "subtract") or value != "0"):
                parts.append(f"{field}={value}")
        key = trial_key(row)
        if key is not None:
            status = "invalid" if key in invalid else "completed" if key in completed else "incomplete"
            parts.append(f"status={status}")
        descriptions.append(" | ".join(parts))
    return descriptions
