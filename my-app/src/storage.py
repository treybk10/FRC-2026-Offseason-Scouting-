"""Persistent local queue for match rows that have not reached Google Sheets."""

import json


_PENDING_MATCHES_KEY = "metal_muscle_pending_match_rows_v1"


async def load_pending_matches(preferences) -> list[list]:
    """Read queued rows from Flet's device/browser preferences."""
    stored_rows = await preferences.get(_PENDING_MATCHES_KEY)
    if not stored_rows:
        return []
    if not isinstance(stored_rows, list):
        raise ValueError("The saved match queue has an unexpected format.")
    try:
        rows = [json.loads(item) for item in stored_rows]
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("A saved match could not be read from local storage.") from error
    if any(not isinstance(row, list) for row in rows):
        raise ValueError("A saved match row has an unexpected format.")
    return rows


async def save_pending_matches(preferences, rows: list[list]) -> None:
    """Replace the saved queue; raise if browser/device storage refuses the write."""
    serialized_rows = [json.dumps(row, ensure_ascii=False) for row in rows]
    saved = await preferences.set(_PENDING_MATCHES_KEY, serialized_rows)
    if not saved:
        raise RuntimeError("Local storage did not confirm saving the match queue.")
