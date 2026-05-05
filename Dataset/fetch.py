"""
Fetch all run data from speedrun.com API v1.

For each game in config.GAMES:
  1. Search for the game by name → get game_id
  2. Find the matching category → get category_id
  3. Fetch all verified runs sorted by date (paginated)
  4. Save every valid run (date + time) as all_runs
  5. Compute WR progression (running minimum) and save separately

Re-running is safe: already-fetched files are skipped.
Files missing all_runs (old format) are automatically re-fetched.
Run: python fetch.py
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

from config import API_BASE, GAMES, REQUEST_DELAY

RAW_DIR = Path(__file__).parent / "data" / "raw"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _get(url: str, params: dict = None) -> dict:
    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"    API error: {exc}")
        return {}


def search_game(name: str) -> dict | None:
    data = _get(f"{API_BASE}/games", params={"name": name, "max": 1}).get("data", [])
    return data[0] if data else None


def get_categories(game_id: str) -> list:
    return _get(f"{API_BASE}/games/{game_id}/categories").get("data", [])


def find_category(categories: list, target: str) -> dict | None:
    per_game = [c for c in categories if c["type"] == "per-game"]
    for cat in per_game:
        if target.lower() in cat["name"].lower():
            return cat
    # fallback: first per-game category
    return per_game[0] if per_game else None


def fetch_all_runs(game_id: str, category_id: str) -> list:
    runs, offset = [], 0
    while True:
        page = _get(f"{API_BASE}/runs", params={
            "game": game_id,
            "category": category_id,
            "status": "verified",
            "orderby": "date",
            "direction": "asc",
            "max": 200,
            "offset": offset,
        }).get("data", [])
        if not page:
            break
        runs.extend(page)
        print(f"    {len(runs)} runs fetched...", end="\r", flush=True)
        if len(page) < 200:
            break
        offset += 200
    return runs


def extract_all_runs(runs: list) -> list:
    """Strip each run down to the three fields we actually need."""
    result = []
    for run in runs:
        t = run.get("times", {}).get("primary_t")
        d = run.get("date")
        if t and d and t > 0:
            result.append({"date": d, "time_seconds": t, "run_id": run["id"]})
    return result


def compute_wr_progression(runs: list) -> list:
    best = float("inf")
    progression = []
    for run in runs:
        t = run.get("times", {}).get("primary_t")
        d = run.get("date")
        if t and d and t > 0 and t < best:
            best = t
            progression.append({
                "date": d,
                "time_seconds": t,
                "run_id": run["id"],
            })
    return progression


def fetch_game(game_cfg: dict) -> dict | None:
    name = game_cfg["name"]
    genre = game_cfg["genre"]
    cat_filter = game_cfg["category"]

    out_path = RAW_DIR / f"{_slug(name)}_{_slug(cat_filter)}.json"
    if out_path.exists():
        cached = json.loads(out_path.read_text(encoding="utf-8"))
        if "all_runs" in cached:
            print(f"  [skip]  {name} — already in data/raw/")
            return cached
        print(f"  [upgrade] {name} — re-fetching to add all_runs")

    print(f"  [fetch] {name}  ({cat_filter})")

    game = search_game(name)
    if not game:
        print(f"    FAIL: not found on speedrun.com")
        return None

    game_id = game["id"]
    game_title = game["names"]["international"]
    categories = get_categories(game_id)
    category = find_category(categories, cat_filter)
    if not category:
        print(f"    FAIL: no per-game category found")
        return None

    cat_name = category["name"]
    cat_id = category["id"]
    print(f"    category matched: '{cat_name}'")

    runs = fetch_all_runs(game_id, cat_id)
    all_runs = extract_all_runs(runs)
    progression = compute_wr_progression(runs)
    print(f"    {len(runs)} total runs → {len(all_runs)} valid runs, {len(progression)} WRs")

    result = {
        "game": game_title,
        "genre": genre,
        "category": cat_name,
        "game_id": game_id,
        "category_id": cat_id,
        "total_runs": len(runs),
        "all_runs": all_runs,
        "wr_progression": progression,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    saved → {out_path.name}")
    return result


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(GAMES)} games from speedrun.com API v1\n")

    ok, failed = [], []
    for i, game_cfg in enumerate(GAMES, 1):
        print(f"[{i:02d}/{len(GAMES)}] {game_cfg['name']}")
        result = fetch_game(game_cfg)
        if result:
            ok.append(result)
        else:
            failed.append(game_cfg["name"])

    print(f"\n{'='*50}")
    print(f"Done: {len(ok)} fetched, {len(failed)} failed")
    if failed:
        print("Failed games:")
        for name in failed:
            print(f"  - {name}")
    print(f"Raw files in: {RAW_DIR}")


if __name__ == "__main__":
    main()
