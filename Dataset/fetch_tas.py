"""
Fetch TAS timeline data from TASVideos.org for the 17 games in config.GAMES.

For each game:
  1. Look up TASVideos game ID from the hardcoded TAS_GAME_MAP
  2. Fetch /Movies-List-{id}G-Obs to get all publication IDs (current + obsoleted)
  3. For each pub ID, call /api/v1/publications/{id} for structured data
  4. Filter to the branch comparable to the human Any% category we track
  5. Remove unrealistic entries (same threshold as clean.py sanitize_wr_progressions)
  6. Save to data/reference/tas_{game_slug}.json

Re-running is safe: already-fetched files are skipped.
Use --force to re-fetch all.

Run: python fetch_tas.py
Run: python fetch_tas.py --force
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GAMES, REQUEST_DELAY

REFERENCE_DIR = Path(__file__).parent / "data" / "reference"
TASVIDEOS_BASE = "https://tasvideos.org"
API_BASE = f"{TASVIDEOS_BASE}/api/v1"
USER_AGENT = (
    "DataAnalytics-TAS-Fetcher/1.0 "
    "(academic research project; contact: arungopala25@gmail.com)"
)

# ---------------------------------------------------------------------------
# TASVideos game configuration
# ---------------------------------------------------------------------------
# branch_include: a publication is KEPT if its branch contains ANY of these
#                 substrings (case-insensitive). Empty list = accept all.
# branch_exclude: a publication is DROPPED if its branch contains ANY of these
#                 (applied after include check).
# category_mismatch: True if the TAS branch does not match the human Any% route.
# game_id: None = not on TASVideos.

TAS_GAME_MAP: dict[str, dict] = {
    "Super Mario Bros.": {
        "game_id": 1,
        "branch_include": ["warps"],
        "branch_exclude": [
            "walkathon", "warpless", "maximum", "minimum",
            "arbitrary code", "minimum presses",
        ],
        "title_exclude": ["europe"],  # PAL version runs at 50fps, not comparable
        "branch_note": (
            "'warps' branch = Any% using warp zones (NES US/FDS versions only). "
            "Directly comparable to human speedrun.com Any%."
        ),
        "category_mismatch": False,
    },
    "Super Mario 64": {
        "game_id": 246,
        "branch_include": ["16 stars"],
        "branch_exclude": ["70 stars", "120 stars", "0 stars", "1 star", "1 key", "no backwards"],
        "branch_note": (
            "16-star TAS branch. Human Any% uses 16-star route — directly comparable."
        ),
        "category_mismatch": False,
    },
    "Celeste": {
        "game_id": 2115,
        "branch_include": ["baseline"],
        "branch_exclude": ["100%"],
        "branch_note": (
            "'baseline' branch = the standard Any% run comparable to human speedrun.com Any%."
        ),
        "category_mismatch": False,
    },
    "Super Metroid": {
        "game_id": 121,
        "branch_include": ["baseline"],
        "branch_exclude": [
            "low%", "100%", "reverse boss", "x-ray",
            "game end", "in-game time",
        ],
        "branch_note": (
            "'baseline' = TASVideos standard Any% route (currently 35:58). "
            "Note: human WR uses a deeper glitch set giving sub-30 min times. "
            "Category mismatch — TAS 'baseline' is not the same route."
        ),
        "category_mismatch": True,
    },
    "The Legend of Zelda: Ocarina of Time": {
        "game_id": 301,
        "branch_include": ["baseline"],
        "branch_exclude": [
            "100%", "glitchless", "mst", "game end",
            "triforce", "all dungeons", "no doors", "no stale",
        ],
        "branch_note": (
            "'baseline' = standard Any% TAS with ACE. "
            "Human Any% also uses ACE, so routes are broadly comparable. "
            "Includes both the original 2:33h route and the later 20-minute ACE route."
        ),
        "category_mismatch": False,
    },
    "Hollow Knight": {
        "game_id": None,
        "notes": (
            "Not on TASVideos. Modern PC game (2017) — TAS tooling exists via "
            "libTAS but no published TAS on TASVideos for this category."
        ),
    },
    "Pokemon Red/Blue": {
        "game_id": 16,
        "branch_include": ["baseline", "warp glitch", "save glitch", "brock through walls"],
        "branch_exclude": ["co-op", "playaround", "minimum", "diploma", "green", "yellow"],
        "branch_note": (
            "Includes baseline (original any%), warp glitch, save glitch, and "
            "Brock-through-walls branches. These represent the main progression of "
            "fastest GB Red/Blue any% TAS techniques over time."
        ),
        "category_mismatch": False,
    },
    "Final Fantasy VII": {
        "game_id": 2165,
        "branch_include": ["baseline"],
        "branch_exclude": ["no slots", "100%", "low level"],
        "branch_note": (
            "'baseline' = PSX Any% with slots manipulation. "
            "Comparable to human speedrun.com Any% which also uses slots."
        ),
        "category_mismatch": False,
    },
    "Doom": {
        "game_id": 1655,
        "branch_include": ["episode 1", "episode 2", "episode 3", "episode 4"],
        "branch_exclude": ["no monsters"],
        "no_progression": True,  # episodes are separate series; progression across them is meaningless
        "branch_note": (
            "The Ultimate Doom (PC), all 4 episode TAS runs listed individually. "
            "No full-game Any% TAS exists on TASVideos. "
            "Human dataset tracks all-episodes Any% — category mismatch. "
            "Summed episode time provides a rough full-game TAS proxy."
        ),
        "category_mismatch": True,
    },
    "Quake": {
        "game_id": None,
        "notes": (
            "Not on TASVideos. The original PC Quake is TAS'd by the "
            "'Quake Done Quick' community (quake.speeddemosarchive.com). "
            "No emulator-based TAS exists on TASVideos for the PC version."
        ),
    },
    "Half-Life 2": {
        "game_id": None,
        "notes": (
            "Not on TASVideos. SourceRuns.org holds the TAS record. "
            "Already tracked in f3b_tas_stats.json with full gap history."
        ),
    },
    "Portal": {
        "game_id": None,
        "notes": (
            "Not on TASVideos as a PC game. The human 'Out of Bounds' category "
            "has no established comparable TAS on TASVideos."
        ),
    },
    "Portal 2": {
        "game_id": None,
        "notes": "Not on TASVideos.",
    },
    "The Talos Principle": {
        "game_id": None,
        "notes": "Not on TASVideos. No documented TAS for this puzzle game.",
    },
    "Minecraft: Java Edition": {
        "game_id": None,
        "notes": (
            "Not on TASVideos. Procedurally-generated world makes TAS fundamentally "
            "incomparable to human runs."
        ),
    },
    "Pac-Man": {
        "game_id": None,
        "notes": (
            "Score-based game. The original arcade Pac-Man is not on TASVideos. "
            "No time-based TAS is applicable."
        ),
    },
    "Donkey Kong": {
        "game_id": 2017,
        "branch_include": [],
        "branch_exclude": [],
        "branch_note": (
            "Original 1981 arcade Donkey Kong. Only one TAS publication exists — "
            "no multi-entry improvement timeline available."
        ),
        "category_mismatch": False,
    },
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_html(url: str) -> str:
    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"    HTTP error fetching {url}: {exc}")
        return ""


def _get_json(url: str) -> dict | list | None:
    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"    API error {url}: {exc}")
        return None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Publication ID extraction
# ---------------------------------------------------------------------------

def extract_pub_ids_from_page(game_id: int) -> list[int]:
    """Fetch /Movies-List-{id}G-Obs and return all publication IDs found."""
    url = f"{TASVIDEOS_BASE}/Movies-List-{game_id}G-Obs"
    html = _get_html(url)
    if not html:
        return []
    # Publication links look like href="/665M" or href="/1715M" in the HTML
    raw = re.findall(r'href=["\']?/(\d+)M["\']?', html, re.IGNORECASE)
    ids = sorted(set(int(x) for x in raw))
    return ids


# ---------------------------------------------------------------------------
# API publication fetch
# ---------------------------------------------------------------------------

def fetch_publication(pub_id: int) -> dict | None:
    """Fetch a single publication by ID (works for both current and obsoleted)."""
    data = _get_json(f"{API_BASE}/publications/{pub_id}")
    if not isinstance(data, dict):
        return None
    return data


def pub_to_entry(pub: dict) -> dict | None:
    """Convert a raw API publication response to our timeline entry format."""
    frames = pub.get("frames")
    fps = pub.get("systemFrameRate")
    ts = pub.get("createTimestamp")
    branch = pub.get("branch") or ""
    authors = pub.get("authors") or []
    system_code = pub.get("systemCode") or ""

    if not frames or not fps or fps == 0 or not ts:
        return None

    time_s = round(frames / fps, 3)
    if time_s <= 0:
        return None

    # Parse ISO timestamp to date string
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        date_str = ts[:10]

    return {
        "publication_id": pub.get("id"),
        "date": date_str,
        "time_s": time_s,
        "branch": branch,
        "system_code": system_code,
        "authors": authors,
        "is_current": pub.get("obsoletedById") is None,
        "title": pub.get("title", ""),
    }


# ---------------------------------------------------------------------------
# Branch filtering
# ---------------------------------------------------------------------------

def _branch_ok(branch: str, include: list[str], exclude: list[str]) -> bool:
    b = branch.lower()
    if exclude and any(ex.lower() in b for ex in exclude if ex):
        return False
    if not include:
        return True
    return any(inc.lower() in b for inc in include if inc)


# ---------------------------------------------------------------------------
# Unrealistic run filter
# ---------------------------------------------------------------------------

def filter_unrealistic(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Drop TAS entries that are implausibly fast relative to the branch median.

    Mirrors the logic in clean.py sanitize_wr_progressions:
      - Compute median time across all entries
      - Drop any entry with time_s < min(1.0, 0.01 * median) when median > 10.0

    Returns (kept, dropped).
    """
    if len(entries) < 3:
        return entries, []

    times = sorted(e["time_s"] for e in entries)
    median = times[len(times) // 2]

    if median <= 10.0:
        return entries, []

    threshold = min(1.0, 0.01 * median)
    kept, dropped = [], []
    for e in entries:
        if e["time_s"] < threshold:
            dropped.append(e)
        else:
            kept.append(e)
    return kept, dropped


# ---------------------------------------------------------------------------
# TAS WR progression
# ---------------------------------------------------------------------------

def compute_tas_progression(entries: list[dict]) -> list[dict]:
    """
    Compute the TAS record progression from a list of entries sorted by date.

    Mirrors compute_wr_progression in fetch.py: keeps only entries that set
    a new (faster) record relative to all previous entries for that game.
    Entries on the same date are de-duplicated by keeping the faster one first.
    """
    progression: list[dict] = []
    best = float("inf")
    for entry in entries:
        if entry["time_s"] < best:
            best = entry["time_s"]
            progression.append(entry)
    return progression


# ---------------------------------------------------------------------------
# Timeline builder
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_timeline(game_name: str, cfg: dict) -> dict:
    slug = _slug(game_name)
    game_id = cfg.get("game_id")

    base = {
        "game": game_name,
        "game_slug": slug,
        "tasvideos_game_id": game_id,
    }

    if game_id is None:
        return {
            **base,
            "status": "not_on_tasvideos",
            "notes": cfg.get("notes", ""),
            "timeline": [],
        }

    movies_url = f"{TASVIDEOS_BASE}/Movies-List-{game_id}G-Obs"
    print(f"    Fetching publication list: {movies_url}")
    pub_ids = extract_pub_ids_from_page(game_id)
    print(f"    Found {len(pub_ids)} publication IDs: {pub_ids}")

    if not pub_ids:
        return {
            **base,
            "source": "TASVideos.org",
            "source_url": movies_url,
            "status": "no_publications_found",
            "branch": "",
            "timeline": [],
        }

    # Fetch each publication individually (API supports obsoleted ones)
    all_entries: list[dict] = []
    for pub_id in pub_ids:
        pub = fetch_publication(pub_id)
        if pub is None:
            print(f"      [skip] pub {pub_id}: fetch failed")
            continue
        entry = pub_to_entry(pub)
        if entry is None:
            print(f"      [skip] pub {pub_id}: missing frames/fps/timestamp")
            continue
        all_entries.append(entry)

    print(f"    Fetched {len(all_entries)} publication records")

    # Title-based exclude (catches region variants embedded in title, not branch)
    title_exclude = cfg.get("title_exclude", [])
    if title_exclude:
        pre_te = len(all_entries)
        all_entries = [
            e for e in all_entries
            if not any(te.lower() in e.get("title", "").lower() for te in title_exclude)
        ]
        if len(all_entries) < pre_te:
            print(f"    {len(all_entries)} after title_exclude ({title_exclude}, dropped {pre_te - len(all_entries)})")

    # Branch filter
    branch_include = cfg.get("branch_include", [])
    branch_exclude = cfg.get("branch_exclude", [])
    filtered = [
        e for e in all_entries
        if _branch_ok(e["branch"], branch_include, branch_exclude)
    ]
    print(f"    {len(filtered)} after branch filter (include={branch_include})")

    # Unrealistic filter
    kept, dropped = filter_unrealistic(filtered)
    for d in dropped:
        print(
            f"    [filter] Dropped unrealistic: "
            f"pub={d['publication_id']} {d['date']} t={d['time_s']}s branch='{d['branch']}'"
        )

    # Sort by date, then by time_s (faster first) for same-date duplicates
    all_valid = sorted(kept, key=lambda e: (e["date"], e["time_s"]))

    # Compute TAS record progression (only entries that set a new TAS best time)
    # Skip for multi-series games (e.g. Doom episodes) where cross-series progression is meaningless
    if cfg.get("no_progression"):
        timeline = all_valid
    else:
        timeline = compute_tas_progression(all_valid)

    status = "found" if timeline else "no_publications_for_branch"
    branch_label = (
        ", ".join(branch_include) if branch_include else "all"
    )

    result: dict = {
        **base,
        "source": "TASVideos.org",
        "source_url": movies_url,
        "status": status,
        "branch": branch_label,
        "branch_note": cfg.get("branch_note", ""),
        "category_mismatch": cfg.get("category_mismatch", False),
        # timeline = only entries that set a new TAS record (improvement progression)
        "timeline": timeline,
        # all_publications = every valid pub for the branch (includes non-improving entries)
        "all_publications": all_valid,
    }

    if timeline:
        if cfg.get("no_progression"):
            # Multi-series mode: best is the individually fastest entry; also sum all
            best = min(timeline, key=lambda e: e["time_s"])
            result["current_best"] = {"date": best["date"], "time_s": best["time_s"]}
            total_s = sum(e["time_s"] for e in timeline)
            result["summed_time_s"] = round(total_s, 3)
            result["summed_time_note"] = (
                "Sum of all episode/part TAS times — rough full-game proxy"
            )
            result["n_improvements"] = len(timeline)
        else:
            first = timeline[0]
            best = timeline[-1]  # last entry is always the best in the progression
            result["first_tas"] = {"date": first["date"], "time_s": first["time_s"]}
            result["current_best"] = {"date": best["date"], "time_s": best["time_s"]}
            result["n_improvements"] = len(timeline)
            if len(timeline) > 1 and first["time_s"] > 0:
                pct = 100.0 * (first["time_s"] - best["time_s"]) / first["time_s"]
                result["pct_improvement_total"] = round(pct, 2)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    force = "--force" in sys.argv
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    game_names = [g["name"] for g in GAMES]
    print(f"Fetching TAS timelines for {len(game_names)} games from TASVideos.org\n")

    found, not_on_tv, errors = [], [], []

    for i, name in enumerate(game_names, 1):
        print(f"[{i:02d}/{len(game_names)}] {name}")

        if name not in TAS_GAME_MAP:
            print(f"    [skip] Not in TAS_GAME_MAP — add it to fetch_tas.py")
            errors.append(name)
            print()
            continue

        slug = _slug(name)
        out_path = REFERENCE_DIR / f"tas_{slug}.json"

        if out_path.exists() and not force:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            n = len(existing.get("timeline", []))
            print(f"    [skip] Already fetched → {out_path.name} ({n} entries)")
            (found if existing.get("status") == "found" else not_on_tv).append(name)
            print()
            continue

        cfg = TAS_GAME_MAP[name]
        result = build_timeline(name, cfg)

        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        status = result["status"]
        n = len(result.get("timeline", []))
        print(f"    saved → {out_path.name}  status={status}  timeline={n} entries")

        if status == "found":
            found.append(name)
            if result.get("first_tas") and result.get("current_best"):
                f_t = result["first_tas"]["time_s"]
                b_t = result["current_best"]["time_s"]
                pct = result.get("pct_improvement_total", 0)
                print(f"    first={f_t}s  best={b_t}s  improvement={pct}%")
        elif status == "not_on_tasvideos":
            not_on_tv.append(name)
        else:
            errors.append(name)

        print()

    print("=" * 55)
    print(f"Done: {len(found)} with timeline, {len(not_on_tv)} not on TASVideos, {len(errors)} errors/no branch")
    if not_on_tv:
        print(f"Not on TASVideos: {', '.join(not_on_tv)}")
    if errors:
        print(f"Problems: {', '.join(errors)}")
    print(f"Files saved to: {REFERENCE_DIR}")


if __name__ == "__main__":
    main()
