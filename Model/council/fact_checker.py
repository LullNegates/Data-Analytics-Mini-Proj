"""Deterministic numeric fact-checker for council outputs.

The verifier never calls an LLM. It builds an index of every value in the
question's source data (CSV cells + JSON leaves) and then walks the manager's
draft JSON, extracting every number/percentage/date with a regex and looking
each one up in the index with rounding tolerance.

Coverage caveat (also noted in docs/council-architecture.md):
    Pure regex catches numeric drift only. Categorical errors like "Minecraft
    is RPG" must be filtered by the council itself, not by this verifier.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# A claim found in the manager's draft. ``path`` is a JSON-Pointer-ish breadcrumb
# (e.g. "findings[2].text") and ``snippet`` is the surrounding sentence so the
# manager can fix the right place when given the report.
@dataclass(frozen=True)
class Claim:
    value:    float
    path:     str
    snippet:  str
    raw:      str  # original token as it appeared, e.g. "0.284" or "1.95%"


@dataclass
class VerificationReport:
    verified:           list[Claim] = field(default_factory=list)
    unverified:         list[Claim] = field(default_factory=list)
    categorical_errors: list[str]   = field(default_factory=list)

    @property
    def all_verified(self) -> bool:
        return not self.unverified and not self.categorical_errors

    @property
    def n_total(self) -> int:
        return len(self.verified) + len(self.unverified)

    def summary_line(self) -> str:
        cat = f", {len(self.categorical_errors)} categorical" if self.categorical_errors else ""
        return (
            f"verified {len(self.verified)} / {self.n_total} numeric claims, "
            f"{len(self.unverified)} unverified{cat}"
        )

    def revision_brief(self) -> str:
        """Compact list passed to the manager when asking for a revision."""
        parts: list[str] = []
        if self.unverified:
            lines = [
                "Folgende Zahlen in deinem Entwurf finden sich NICHT in den Quelldaten "
                "(CSV oder stats.json). Korrigiere sie oder entferne die Aussage:"
            ]
            for c in self.unverified:
                lines.append(f"  • {c.path}: '{c.raw}' im Kontext: \"{c.snippet}\"")
            parts.append("\n".join(lines))
        if self.categorical_errors:
            lines = ["Folgende strukturelle Fehler wurden gefunden — korrigiere sie exakt:"]
            for err in self.categorical_errors:
                lines.append(f"  • {err}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)


# ─── Source index ────────────────────────────────────────────────────────────


def _walk_json(obj: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    """Recursive walk yielding (path, leaf_value) for every leaf."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_json(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_json(v, f"{path}[{i}]")
    else:
        yield path, obj


def build_source_index(
    csv_paths: list[Path],
    json_paths: list[Path],
) -> set[float]:
    """Collect every numeric value from the source files into a single set.

    We don't need the path of each value for verification — only "is this number
    somewhere in the source data?". Storing as a flat set keeps lookup O(1).
    Strings are skipped; only numerics enter the index.
    """
    values: set[float] = set()

    for path in csv_paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for v in row.values():
                    n = _try_float(v)
                    if n is not None:
                        values.add(n)

    for path in json_paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for _, v in _walk_json(data):
            n = _try_float(v)
            if n is not None:
                values.add(n)

    return values


def _try_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


# ─── Number extraction from manager draft ────────────────────────────────────

# Matches: 12, 12.5, 12,5 (de-locale), 95%, 95.9%, .284
_NUMBER_RE = re.compile(r"(?<![\w.])(-?\d+(?:[.,]\d+)?|\.\d+)\s*(%?)")
# Common stop-numbers: list ids ("F1"), date components, "1." section markers.
_IGNORE_PREFIXES = {"F", "Q"}


def _extract_numbers_from_text(text: str) -> list[tuple[str, float]]:
    """Find every numeric token in a string. Returns [(raw_match, value), ...]."""
    out: list[tuple[str, float]] = []
    for m in _NUMBER_RE.finditer(text):
        raw_num, pct = m.group(1), m.group(2)
        # Skip "F1", "F2" finding ids — match would have to be preceded by F,
        # but the regex already requires \W before the digit; the F is part of
        # a word boundary, so "F1" never matches. Years (2018) match — that's
        # fine, they appear in q*_stats.json's date strings as components.
        try:
            value = float(raw_num.replace(",", "."))
        except ValueError:
            continue
        # Percent sign converts the value into the index's representation.
        # The CSV stores pct_reduction=100.0 (as a percent number), so a token
        # like "95%" matches CSV value 95.0 directly. We also keep the raw
        # token so the report can quote it back to the manager.
        raw_token = raw_num + pct
        out.append((raw_token, value))
    return out


def _walk_text_leaves(obj: Any, path: str = "") -> Iterable[tuple[str, str]]:
    """Yield (path, string_value) for every string leaf in the draft."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_text_leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_text_leaves(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def _walk_numeric_leaves(obj: Any, path: str = "") -> Iterable[tuple[str, float]]:
    """Yield (path, numeric_value) for every numeric leaf in the draft."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_numeric_leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_numeric_leaves(v, f"{path}[{i}]")
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        yield path, float(obj)


# ─── The verifier ────────────────────────────────────────────────────────────


# Tolerances in fractions-of-the-value. ±1% covers most rounding (e.g. 7.96 ↔ 7.9627).
# Absolute tolerance handles tiny near-zero values.
_REL_TOL = 0.01
_ABS_TOL = 0.05


def _is_in_index(value: float, index: set[float]) -> bool:
    if value in index:
        return True
    # Bounded absolute tolerance for tiny values (e.g. 0.001 last_time_s).
    if any(abs(value - v) <= _ABS_TOL for v in index if abs(v) < 1.0):
        return True
    # Relative tolerance for everything else.
    if any(abs(value - v) <= _REL_TOL * max(abs(value), abs(v)) for v in index):
        return True
    # Year-like integers are usually part of dates in the JSON; allow a wider
    # window so 2018 matches 2018.0 and the like.
    if value.is_integer() and 1900 <= value <= 2100:
        return any(int(v) == int(value) for v in index)
    # Whole-number small counts (e.g. n_wrs=78) — already covered by exact set
    # membership, but tolerate ±1 for things like "around 80 records".
    if value.is_integer() and abs(value) < 100:
        return any(abs(v - value) <= 1 for v in index)
    return False


# Top-level keys that are council metadata, not LLM-generated claims.
_METADATA_KEYS = {"question", "generated_at", "token_estimate", "fact_check_warnings"}


def verify(draft: dict, source_index: set[float]) -> VerificationReport:
    """Walk every text + numeric leaf in ``draft`` and verify each number."""
    report = VerificationReport()

    # Strip metadata keys so timestamp components and token counts are not
    # checked against the source data — they are injected by the orchestrator.
    content = {k: v for k, v in draft.items() if k not in _METADATA_KEYS}

    # 1. Numbers embedded in string fields (findings.text, summary, etc.)
    for path, text in _walk_text_leaves(content, ""):
        for raw, value in _extract_numbers_from_text(text):
            snippet = _shorten(text, raw)
            claim = Claim(value=value, path=path, snippet=snippet, raw=raw)
            # Percentage tokens (e.g. "5,19%") are checked both as the literal
            # value (5.19) and as a proportion (0.0519) because some source files
            # store survival probabilities as decimals rather than whole-number %.
            if _is_in_index(value, source_index) or (
                raw.endswith("%") and _is_in_index(value / 100, source_index)
            ):
                report.verified.append(claim)
            else:
                report.unverified.append(claim)

    # 2. Top-level numeric leaves (km_median_days, survival_at_365, etc.)
    for path, value in _walk_numeric_leaves(content, ""):
        snippet = f"{path} = {value}"
        claim = Claim(value=value, path=path, snippet=snippet, raw=str(value))
        if _is_in_index(value, source_index):
            report.verified.append(claim)
        else:
            report.unverified.append(claim)

    return report


def _shorten(text: str, around: str, width: int = 80) -> str:
    """Return a windowed substring of ``text`` centred on ``around``."""
    idx = text.find(around)
    if idx < 0:
        return text[:width]
    start = max(0, idx - width // 2)
    end   = min(len(text), idx + len(around) + width // 2)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


# ─── Convenience: per-question source-index loader ───────────────────────────


def check_q2_structural_breaks(draft: dict, q2_stats_path: Path) -> list[str]:
    """Return error messages for every game where the council output has a null
    structural_break but q2_stats.json shows significant_at_0.05 = true.

    Also flags games where saturation is set to true for log/poly2/power_law models.
    """
    if not q2_stats_path.exists():
        return []
    with open(q2_stats_path, encoding="utf-8") as f:
        stats = json.load(f)

    # Map game name → (split_date, significant)
    break_map: dict[str, str] = {}
    for g in stats.get("games", []):
        sb = g.get("structural_break") or {}
        if sb.get("significant_at_0.05"):
            break_map[g["game"]] = (g.get("structural_break") or {}).get("split_date", "")[:10]

    non_saturating = {"log", "power_law", "poly2"}
    errors: list[str] = []

    for entry in draft.get("saturation_by_game", []):
        game  = entry.get("game", "?")
        sb    = entry.get("structural_break")
        model = entry.get("best_model", "")
        sat   = entry.get("saturation")

        if game in break_map and (sb is None or str(sb).strip().lower() in ("null", "none", "")):
            errors.append(
                f"structural_break für '{game}' ist null, aber q2_stats hat "
                f"significant_at_0.05=true (split_date: {break_map[game]}). Datum eintragen."
            )

        if model in non_saturating and sat is True:
            errors.append(
                f"saturation für '{game}' ist true, aber best_model='{model}' sättigt NICHT. "
                f"saturation muss false sein."
            )

    return errors


def build_index_for_question(
    question: str,
    data_dir: Path,
    analysis_dir: Path,
) -> set[float]:
    """Assemble the source index for q1/q2/q3 from the standard locations."""
    csv_map = {
        "q1": ["q1_reduction.csv"],
        "q2": ["q2_saturation.csv"],
        "q3": ["q3_lifetimes.csv"],
    }
    if question not in csv_map:
        raise ValueError(f"unknown question: {question}")

    csv_paths  = [data_dir / name for name in csv_map[question]]
    json_paths = [analysis_dir / f"{question}_stats.json"]
    return build_source_index(csv_paths, json_paths)
