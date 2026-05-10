"""Terminal pretty-printing + JSON transcript writer for council runs.

Headers use ANSI escape codes; if stdout isn't a TTY (e.g. redirected to a
file), colour codes are suppressed so the transcript stays clean.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ── ANSI colours ──────────────────────────────────────────────────────────────

_USE_COLOUR = sys.stdout.isatty()

_RESET   = "\033[0m"   if _USE_COLOUR else ""
_BOLD    = "\033[1m"   if _USE_COLOUR else ""
_DIM     = "\033[2m"   if _USE_COLOUR else ""
_CYAN    = "\033[36m"  if _USE_COLOUR else ""
_YELLOW  = "\033[33m"  if _USE_COLOUR else ""
_MAGENTA = "\033[35m"  if _USE_COLOUR else ""
_RED     = "\033[31m"  if _USE_COLOUR else ""
_GREEN   = "\033[32m"  if _USE_COLOUR else ""

ROUND_COLOURS = {1: _CYAN, 2: _YELLOW}


def banner(title: str, *, colour: str = _BOLD, width: int = 70) -> None:
    line = "═" * width
    print()
    print(f"{colour}{line}{_RESET}")
    print(f"{colour}  {title}{_RESET}")
    print(f"{colour}{'─' * width}{_RESET}")


def round_header(round_no: int, idx: int, total: int, label: str, model: str) -> None:
    colour = ROUND_COLOURS.get(round_no, _BOLD)
    banner(f"[{idx}/{total}] {label}  ·  {model}  ·  Runde {round_no}", colour=colour)


def manager_header(model: str, attempt: int = 0) -> None:
    suffix = "" if attempt == 0 else f" (Revision {attempt})"
    banner(f"Manager  ·  {model}  ·  Synthese{suffix}", colour=_MAGENTA)


def thinking_section_header() -> None:
    """Printed once before the manager's CoT trace begins streaming."""
    print(f"\n{_DIM}  ── Reasoning trace (not included in output) ──{_RESET}")


def answer_section_header() -> None:
    """Printed once when the manager transitions from thinking to final JSON."""
    print(f"\n{_MAGENTA}  ── Final answer ──{_RESET}")


def fact_check_header(passed: bool, summary: str) -> None:
    colour = _GREEN if passed else _RED
    label  = "Faktencheck OK" if passed else "Faktencheck fehlgeschlagen"
    banner(f"{label}  —  {summary}", colour=colour)


def info(msg: str) -> None:
    print(f"{_DIM}  {msg}{_RESET}")


def warn(msg: str) -> None:
    print(f"{_RED}  [warn] {msg}{_RESET}")


# ── Diff-vs-baseline summary ──────────────────────────────────────────────────


def print_diff_summary(council: dict, baseline_path: Path) -> None:
    if not baseline_path.exists():
        info(f"No single-agent baseline at {baseline_path} — skipping diff.")
        return
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warn(f"Baseline {baseline_path.name} is not valid JSON — skipping diff.")
        return

    banner("Vergleich: Council vs Single-Agent", colour=_BOLD)

    def cnt(d: dict, key: str) -> int:
        v = d.get(key)
        return len(v) if isinstance(v, list) else 0

    rows = [
        ("Findings",         cnt(baseline, "findings"),         cnt(council, "findings")),
        ("Genre patterns",   cnt(baseline, "genre_patterns"),   cnt(council, "genre_patterns")),
        ("Saturation games", cnt(baseline, "saturation_by_game"), cnt(council, "saturation_by_game")),
        ("Genre survival",   cnt(baseline, "genre_survival"),   cnt(council, "genre_survival")),
    ]
    print(f"  {'Metric':<22} {'Baseline':>10} {'Council':>10}  Δ")
    print(f"  {'-' * 22} {'-' * 10} {'-' * 10}  {'-' * 4}")
    for name, b, c in rows:
        if b == 0 and c == 0:
            continue
        delta = c - b
        sign  = "+" if delta > 0 else ""
        print(f"  {name:<22} {b:>10} {c:>10}  {sign}{delta}")


# ── Transcript writer ─────────────────────────────────────────────────────────


def write_transcript(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **payload,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
