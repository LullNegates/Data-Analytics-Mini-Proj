"""Shared normalisation utilities for the speedrun analysis pipeline.

Two entry points:

  normalize_columns(rows)
      For CSV output. Given a list of row dicts, returns a new list where
      every numeric value in a "float-bearing" column is formatted as a
      string with exactly N decimal places, where N is the maximum decimal
      places seen for any float in that column across all rows.  Trailing
      zeros are preserved so every cell in a column looks identical in Excel
      (e.g. "89.7550", "25.5000").  Integer values in the same column are
      also formatted (e.g. 20 -> "20.000" when other rows have three dp).

  normalize_floats(data)
      For JSON output. Recursively walks any nested dict / list structure.
      Wherever a list of same-schema dicts (or a dict whose values are all
      dicts) is found, float values at the same key are rounded to the
      maximum decimal places seen for that key across all sibling entries.
      Returns actual float values -- JSON cannot represent trailing zeros, so
      "89.755" stays "89.755" even if another entry has four places. The
      rounding is consistent, even if the representation isn't.

      Scientific-notation floats (e.g. 9.138e-05) are left unchanged to
      avoid silent precision loss when rounding to a dp derived from
      regular neighbours.
"""

from __future__ import annotations


# ---------- shared primitives ----------

def _count_dp(v: float) -> int:
    """Decimal places in the string representation of a float.

    Uses str() because that is what json.dumps and Python's csv writer use
    internally.  Scientific notation (e.g. 1e-10) returns 0 -- normalising
    such values would require arbitrary-precision arithmetic and is out of
    scope.
    """
    if isinstance(v, bool):
        return 0
    s = str(v)
    if "." in s and "e" not in s.lower():
        return len(s.split(".")[1])
    return 0


def _is_numeric(v) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float))


def _is_sci(v: float) -> bool:
    return "e" in str(v).lower()


# ---------- CSV ----------

def normalize_columns(rows: list[dict]) -> list[dict]:
    """Normalise numeric columns for CSV output.

    For each column that ever contains a float, find the maximum number of
    decimal places across all rows, then format every numeric value (int or
    float) in that column to exactly that many decimal places as a string.

    Non-numeric values (str, bool, None) pass through unchanged.
    Purely integer columns (no float in any row) are left as-is.
    """
    if not rows:
        return rows

    # Identify columns that contain at least one float value
    float_cols = {
        k
        for row in rows
        for k, v in row.items()
        if not isinstance(v, bool) and isinstance(v, float)
    }

    # Max dp per float-bearing column (scanning float values only)
    max_dp: dict[str, int] = {}
    for row in rows:
        for k, v in row.items():
            if k not in float_cols:
                continue
            if not isinstance(v, bool) and isinstance(v, float):
                dp = _count_dp(v)
                if dp > max_dp.get(k, 0):
                    max_dp[k] = dp

    out = []
    for row in rows:
        new_row = {}
        for k, v in row.items():
            if k in max_dp and _is_numeric(v):
                new_row[k] = f"{float(v):.{max_dp[k]}f}"
            else:
                new_row[k] = v
        out.append(new_row)
    return out


# ---------- JSON ----------

def normalize_floats(data) -> object:
    """Recursively normalise float precision in a nested JSON-serialisable structure.

    Shape detection order (first match wins):
    1. list[dict]          -> normalise float values per key via _norm_list_of_dicts.
    2. dict[str, dict]     -> virtual-list approach, same normalisation per key.
    3. dict[str, numeric]  -> flat numeric dict; round all values to max dp seen.
    4. dict (mixed)        -> recurse into each value.
    5. list (non-dict)     -> recurse each item.
    6. scalar              -> return unchanged.

    Scientific-notation floats are left unchanged (see module docstring).
    """
    if isinstance(data, list):
        if data and all(isinstance(item, dict) for item in data):
            return _norm_list_of_dicts(data)
        return [normalize_floats(item) for item in data]

    if isinstance(data, dict):
        # (2) Homogeneous dict-of-dicts (e.g. genre_stats)
        if data and all(isinstance(v, dict) for v in data.values()):
            virtual = [{"__lbl__": lbl, **v} for lbl, v in data.items()]
            normalised = _norm_list_of_dicts(virtual)
            return {
                item["__lbl__"]: {k: v for k, v in item.items() if k != "__lbl__"}
                for item in normalised
            }

        # (3) Flat dict[str, numeric] (e.g. improvement_gini)
        if data and all(_is_numeric(v) for v in data.values()):
            max_dp = max(
                (_count_dp(v) for v in data.values()
                 if isinstance(v, float) and not _is_sci(v)),
                default=0,
            )
            return {
                k: round(float(v), max_dp) if not isinstance(v, bool) else v
                for k, v in data.items()
            }

        # (4) Mixed dict -- recurse
        return {k: normalize_floats(v) for k, v in data.items()}

    return data


def _norm_list_of_dicts(items: list[dict]) -> list[dict]:
    """Normalise a list of same-schema dicts by rounding numeric values per key.

    Float-bearing keys (those with at least one float across all items) are
    normalised: every numeric value (int or float) in such a key is rounded
    to the maximum dp seen for any float in that key.  Scientific-notation
    floats are left unchanged.  Non-numeric values recurse via normalize_floats.
    """
    # Keys that contain at least one non-scientific float
    float_keys = {
        k
        for item in items
        for k, v in item.items()
        if not isinstance(v, bool) and isinstance(v, float) and not _is_sci(v)
    }

    max_dp: dict[str, int] = {}
    for item in items:
        for k, v in item.items():
            if k not in float_keys:
                continue
            if not isinstance(v, bool) and isinstance(v, float):
                dp = _count_dp(v)
                if dp > max_dp.get(k, 0):
                    max_dp[k] = dp

    out = []
    for item in items:
        new_item = {}
        for k, v in item.items():
            if k in max_dp and _is_numeric(v) and not isinstance(v, bool):
                if isinstance(v, float) and _is_sci(v):
                    new_item[k] = v  # preserve scientific-notation floats
                else:
                    new_item[k] = round(float(v), max_dp[k])
            else:
                new_item[k] = normalize_floats(v)
        out.append(new_item)
    return out
