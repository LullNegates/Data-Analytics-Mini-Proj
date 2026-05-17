"""Shared normalisation utilities for the speedrun analysis pipeline.

Two entry points:

  normalize_columns(rows)
      For CSV output. Given a list of row dicts, returns a new list where
      every float value is formatted as a string with exactly N decimal
      places, where N is the maximum decimal places seen in that column
      across all rows.  Trailing zeros are preserved so every cell in a
      column looks identical to Excel (e.g. "89.7550", "25.5000").

  normalize_floats(data)
      For JSON output. Recursively walks any nested dict / list structure.
      Wherever a list of same-schema dicts (or a dict whose values are all
      dicts) is found, float values at the same key are rounded to the
      maximum decimal places seen for that key across all sibling entries.
      Returns actual float values — JSON cannot represent trailing zeros, so
      "89.755" stays "89.755" even if another entry has four places. The
      rounding is consistent, even if the representation isn't.
"""

from __future__ import annotations


# ---------- shared primitive ----------

def _count_dp(v: float) -> int:
    """Decimal places in the string representation of a float.

    Uses str() because that is what json.dumps and Python's csv writer use
    internally.  Scientific notation (e.g. 1e-10) returns 0 — normalising
    such values would require arbitrary-precision arithmetic and is out of
    scope.
    """
    if isinstance(v, bool):
        return 0
    s = str(v)
    if "." in s and "e" not in s.lower():
        return len(s.split(".")[1])
    return 0


# ---------- CSV ----------

def normalize_columns(rows: list[dict]) -> list[dict]:
    """Normalise float columns for CSV output.

    For each column that ever contains a float, find the maximum number of
    decimal places across all rows, then format every float in that column
    to exactly that many decimal places as a string.

    Non-float values (int, str, bool, None) pass through unchanged.
    """
    if not rows:
        return rows

    max_dp: dict[str, int] = {}
    for row in rows:
        for k, v in row.items():
            if isinstance(v, bool) or not isinstance(v, float):
                continue
            dp = _count_dp(v)
            if dp > max_dp.get(k, 0):
                max_dp[k] = dp

    out = []
    for row in rows:
        new_row = {}
        for k, v in row.items():
            if not isinstance(v, bool) and isinstance(v, float) and k in max_dp:
                new_row[k] = f"{v:.{max_dp[k]}f}"
            else:
                new_row[k] = v
        out.append(new_row)
    return out


# ---------- JSON ----------

def normalize_floats(data) -> object:
    """Recursively normalise float precision in a nested JSON-serialisable structure.

    Rules:
    - list[dict]  (all items are dicts) → normalise float values per key to
                  the max decimal places seen for that key across the list.
    - dict        whose values are all dicts (e.g. genre_stats) → same rule,
                  treating the outer dict as a virtual list keyed by label.
    - dict        (mixed values) → recurse into each value.
    - list        (non-dict items) → recurse each item.
    - scalar      → return unchanged.

    Returns actual floats, not strings, so JSON consumers keep numeric types.
    Trailing zeros cannot be preserved in JSON without converting to strings
    (which would break downstream readers).
    """
    if isinstance(data, list):
        if data and all(isinstance(item, dict) for item in data):
            return _norm_list_of_dicts(data)
        return [normalize_floats(item) for item in data]

    if isinstance(data, dict):
        # Homogeneous dict-of-dicts (e.g. genre_stats, decade_stats):
        # treat the dict values as a "virtual list" and normalise per key.
        if data and all(isinstance(v, dict) for v in data.values()):
            virtual = [{"__lbl__": lbl, **v} for lbl, v in data.items()]
            normalised = _norm_list_of_dicts(virtual)
            return {
                item["__lbl__"]: {k: v for k, v in item.items() if k != "__lbl__"}
                for item in normalised
            }
        return {k: normalize_floats(v) for k, v in data.items()}

    return data


def _norm_list_of_dicts(items: list[dict]) -> list[dict]:
    """Normalise a list of same-schema dicts by rounding float values per key."""
    max_dp: dict[str, int] = {}
    for item in items:
        for k, v in item.items():
            if isinstance(v, bool) or not isinstance(v, float):
                continue
            dp = _count_dp(v)
            if dp > max_dp.get(k, 0):
                max_dp[k] = dp

    return [
        {
            k: (round(v, max_dp[k])
                if not isinstance(v, bool) and isinstance(v, float) and k in max_dp
                else normalize_floats(v))
            for k, v in item.items()
        }
        for item in items
    ]
