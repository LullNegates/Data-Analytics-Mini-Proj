"""
Curate TAS timeline data for games NOT on TASVideos.org.

These 8 games have their TAS records hosted by specialist communities
rather than TASVideos. This script writes manually-researched JSON files
to data/reference/ using the same format as fetch_tas.py.

Sources cited per game:
  Quake         — quake.speeddemosarchive.com (QdQ series)
  Half-Life 2   — SourceRuns.org
  Portal        — SourceRuns.org, Jukspa's TASing docs
  Portal 2      — portal2sr community / SourceRuns
  Hollow Knight — YouTube community TAS (ConstructiveCynicism)
  Pac-Man       — TASVideos NES Tengen port (proxy for arcade)
  Minecraft     — No viable TAS (procedural generation)
  Talos Principle — No documented TAS found

Run: python curate_tas_external.py
"""

import json
import re
from pathlib import Path

REFERENCE_DIR = Path(__file__).parent / "data" / "reference"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# Hand-curated TAS timeline data
# ---------------------------------------------------------------------------

EXTERNAL_TAS: list[dict] = [

    # ------------------------------------------------------------------
    # Quake (1996) — Quake Done Quick series
    # All-episodes, Nightmare difficulty. Not on TASVideos (demo-based TAS,
    # not emulator; SDA is the canonical archive).
    # Source: quake.speeddemosarchive.com and Wikipedia "Quake done Quick"
    # ------------------------------------------------------------------
    {
        "game": "Quake",
        "game_slug": "quake",
        "tasvideos_game_id": None,
        "source": "Quake Done Quick / Speed Demos Archive",
        "source_url": "https://quake.speeddemosarchive.com/quake/qdq/",
        "status": "found",
        "branch": "all episodes, Nightmare difficulty",
        "branch_note": (
            "Quake Done Quick (QdQ) series: full-game TAS on Nightmare difficulty "
            "across all 4 episodes. Uses demo-recording tooling rather than emulator; "
            "hosted at Speed Demos Archive, not TASVideos. "
            "Directly comparable to human any% all-episodes category."
        ),
        "category_mismatch": False,
        "timeline": [
            {
                "publication_id": None,
                "date": "1997-06-01",
                "time_s": 1189.0,  # 19:49
                "branch": "all episodes, Nightmare",
                "authors": ["Nolan Pflug and QdQ team"],
                "is_current": False,
                "title": "Quake done Quick — 19:49",
            },
            {
                "publication_id": None,
                "date": "1998-04-01",
                "time_s": 995.0,  # 16:35
                "branch": "all episodes, Nightmare",
                "authors": ["QdQ team"],
                "is_current": False,
                "title": "Quake done Quicker — 16:35",
            },
            {
                "publication_id": None,
                "date": "2000-09-13",
                "time_s": 743.0,  # 12:23
                "branch": "all episodes, Nightmare",
                "authors": ["QdQ team"],
                "is_current": False,
                "title": "Quake done Quick with a Vengeance — 12:23 (bunny-hopping breakthrough)",
            },
            {
                "publication_id": None,
                "date": "2011-12-29",
                "time_s": 689.0,  # 11:29
                "branch": "all episodes, Nightmare",
                "authors": ["QdQ team"],
                "is_current": False,
                "title": "Quake done Quickest — 11:29",
            },
            {
                "publication_id": None,
                "date": "2022-12-22",
                "time_s": 609.0,  # 10:09
                "branch": "all episodes, Nightmare",
                "authors": ["QdQ team"],
                "is_current": False,
                "title": "Quake done Quickest lite — 10:09",
            },
            {
                "publication_id": None,
                "date": "2024-06-22",
                "time_s": 523.0,  # 8:43
                "branch": "all episodes, Nightmare",
                "authors": ["QdQ team"],
                "is_current": True,
                "title": "Quake done double Quickest lite — 8:43",
            },
        ],
        "first_tas": {"date": "1997-06-01", "time_s": 1189.0},
        "current_best": {"date": "2024-06-22", "time_s": 523.0},
        "n_improvements": 6,
        "pct_improvement_total": round(100.0 * (1189.0 - 523.0) / 1189.0, 2),
        "all_publications": [],
    },

    # ------------------------------------------------------------------
    # Half-Life 2 (2004) — SourceRuns
    # Not on TASVideos (Source engine game, TAS'd via BunnymodXT).
    # Source: SourceRuns.org
    # ------------------------------------------------------------------
    {
        "game": "Half-Life 2",
        "game_slug": "half-life-2",
        "tasvideos_game_id": None,
        "source": "SourceRuns.org",
        "source_url": "https://sourceruns.org/",
        "status": "found",
        "branch": "any%",
        "branch_note": (
            "Full-game Any% TAS on Easy difficulty. Tool-assisted via BunnymodXT/hltas. "
            "Hosted by SourceRuns, not TASVideos. "
            "Directly comparable to human speedrun.com Any% (OoB, Easy). "
            "Note: human WR has surpassed the 2014 TAS reference time."
        ),
        "category_mismatch": False,
        "timeline": [
            {
                "publication_id": None,
                "date": "2014-01-01",
                "time_s": 4494.0,  # ~74:54 — SourceRuns/SDA documented reference
                "branch": "any%",
                "authors": ["SourceRuns Team"],
                "is_current": False,
                "title": "HL2 TAS — 1:14:54 (SourceRuns/SDA reference run)",
            },
            {
                "publication_id": None,
                "date": "2016-05-01",
                "time_s": 2449.0,  # 40:49 — "Done Quicker", premiered at GDQ
                "branch": "any%",
                "authors": ["SourceRuns Team"],
                "is_current": True,
                "title": "Half-Life 2: Done Quicker — 40:49 (premiered Games Done Quick 2016)",
            },
        ],
        "first_tas": {"date": "2014-01-01", "time_s": 4494.0},
        "current_best": {"date": "2016-05-01", "time_s": 2449.0},
        "n_improvements": 2,
        "pct_improvement_total": round(100.0 * (4494.0 - 2449.0) / 4494.0, 2),
        "all_publications": [],
    },

    # ------------------------------------------------------------------
    # Portal (2007) — SourceRuns / Jukspa
    # Not on TASVideos. TAS'd via hltas/BunnymodXT.
    # Human dataset tracks "Out of Bounds" category.
    # Source: SourceRuns.org, speeddemosarchive.com
    # ------------------------------------------------------------------
    {
        "game": "Portal",
        "game_slug": "portal",
        "tasvideos_game_id": None,
        "source": "SourceRuns.org",
        "source_url": "https://sourceruns.org/speedruns/portal-tas-by-jukspa/",
        "status": "found",
        "branch": "Out of Bounds (OoB)",
        "branch_note": (
            "Portal Out of Bounds TAS. Uses large-skip glitches comparable to human OoB "
            "category. Hosted by SourceRuns, not TASVideos. "
            "Human dataset tracks OoB — directly comparable."
        ),
        "category_mismatch": False,
        "timeline": [
            {
                "publication_id": None,
                "date": "2012-07-16",
                "time_s": 552.0,  # 9:12 — SourceRuns team segmented OoB run
                "branch": "Out of Bounds",
                "authors": ["SourceRuns Team"],
                "is_current": False,
                "title": "Portal OoB segmented TAS — 9:12 (SourceRuns Team 2012)",
            },
            {
                "publication_id": None,
                "date": "2016-01-24",
                "time_s": 313.665,  # 5:13.665 — Jukspa full TAS
                "branch": "Out of Bounds",
                "authors": ["Jukspa", "YaLTeR", "Fnzzy", "Mikael", "Imanex", "Nan0kub", "Rama"],
                "is_current": True,
                "title": "Portal TAS in 5:13.665 by Jukspa et al. (SourceRuns)",
            },
        ],
        "first_tas": {"date": "2012-07-16", "time_s": 552.0},
        "current_best": {"date": "2016-01-24", "time_s": 313.665},
        "n_improvements": 2,
        "pct_improvement_total": round(100.0 * (552.0 - 313.665) / 552.0, 2),
        "all_publications": [],
    },

    # ------------------------------------------------------------------
    # Portal 2 (2011) — SourceRuns / Portal 2 TASing community
    # Not on TASVideos. First formal TAS released in 2022.
    # Source: SourceRuns Showcase, YouTube
    # ------------------------------------------------------------------
    {
        "game": "Portal 2",
        "game_slug": "portal-2",
        "tasvideos_game_id": None,
        "source": "SourceRuns / Portal 2 TASing community",
        "source_url": "https://www.youtube.com/watch?v=MZi1dXwCqG8",
        "status": "found",
        "branch": "Inbounds No SLA (single player)",
        "branch_note": (
            "Portal 2 single-player TAS, Inbounds No-SLA category. "
            "Not on TASVideos. First ever full TAS released 2022 after ~1 year of work. "
            "Category mismatch with human Any% which may use different glitches."
        ),
        "category_mismatch": True,
        "timeline": [
            {
                "publication_id": None,
                "date": "2022-07-01",
                "time_s": 2833.033,  # 47:13.033
                "branch": "Inbounds No SLA",
                "authors": ["Can't Even", "mlugg", "Portal 2 TASing community"],
                "is_current": True,
                "title": "Portal 2 Inbounds No SLA TAS in 47:13.033 (premiered SGDQ 2022)",
            },
        ],
        "first_tas": {"date": "2022-07-01", "time_s": 2833.033},
        "current_best": {"date": "2022-07-01", "time_s": 2833.033},
        "n_improvements": 1,
        "all_publications": [],
    },

    # ------------------------------------------------------------------
    # Hollow Knight (2017) — Community TAS (YouTube)
    # Not on TASVideos. TAS'd via BepInEx/libTAS-compatible tools.
    # Source: ConstructiveCynicism YouTube channel (2021)
    # ------------------------------------------------------------------
    {
        "game": "Hollow Knight",
        "game_slug": "hollow-knight",
        "tasvideos_game_id": None,
        "source": "Community TAS (YouTube — ConstructiveCynicism)",
        "source_url": "https://www.youtube.com/watch?v=XBpo9j-I4kI",
        "status": "found",
        "branch": "Any% No Major Glitches (NMG)",
        "branch_note": (
            "Hollow Knight NMG TAS by ConstructiveCynicism (2021). "
            "Not on TASVideos. TAS tooling exists but formal archive does not. "
            "NMG comparable to human NMG Any% category. Full ACE% TAS also exists."
        ),
        "category_mismatch": False,
        "timeline": [
            {
                "publication_id": None,
                "date": "2021-11-01",
                "time_s": 1739.37,  # 28:59.37
                "branch": "Any% NMG",
                "authors": ["ConstructiveCynicism"],
                "is_current": True,
                "title": "Hollow Knight Any% NMG TAS in 28:59.37 (ConstructiveCynicism, 2021)",
            },
        ],
        "first_tas": {"date": "2021-11-01", "time_s": 1739.37},
        "current_best": {"date": "2021-11-01", "time_s": 1739.37},
        "n_improvements": 1,
        "all_publications": [],
    },

    # ------------------------------------------------------------------
    # Pac-Man (1980) — NES Tengen proxy from TASVideos
    # Original arcade Pac-Man is not on TASVideos.
    # NES Tengen Pac-Man (TASVideos pub 5231) used as the closest proxy.
    # Source: TASVideos.org pub #5231
    # ------------------------------------------------------------------
    {
        "game": "Pac-Man",
        "game_slug": "pac-man",
        "tasvideos_game_id": 2458,
        "source": "TASVideos.org (NES Tengen Pac-Man proxy)",
        "source_url": "https://tasvideos.org/5231M",
        "status": "found_proxy",
        "branch": "baseline (all 20 mazes)",
        "branch_note": (
            "TASVideos NES Pac-Man (Tengen version, game ID 2458, pub 5231). "
            "Original 1980 arcade Pac-Man is not on TASVideos (MAME support limited). "
            "NES Tengen port is the closest TAS proxy; category mismatch vs arcade original. "
            "Only 1 TAS publication exists — no improvement timeline available."
        ),
        "category_mismatch": True,
        "timeline": [
            {
                "publication_id": 5231,
                "date": "2023-04-23",
                "time_s": 722.858,  # 12:02.86 = 722.86s
                "branch": "baseline",
                "authors": ["eien86"],
                "is_current": True,
                "title": "NES Pac-Man (Tengen) by eien86 in 12:02.86 — completes all 20 mazes with luck manipulation",
            },
        ],
        "first_tas": {"date": "2023-04-23", "time_s": 722.858},
        "current_best": {"date": "2023-04-23", "time_s": 722.858},
        "n_improvements": 1,
        "all_publications": [],
    },

    # ------------------------------------------------------------------
    # Minecraft: Java Edition — No viable TAS
    # Procedurally-generated world makes TAS incomparable to human any%.
    # TASVideos entry exists (game ID 3409) but 0 publications, 1 rejection.
    # ------------------------------------------------------------------
    {
        "game": "Minecraft: Java Edition",
        "game_slug": "minecraft-java-edition",
        "tasvideos_game_id": 3409,
        "source": "N/A",
        "source_url": "https://tasvideos.org/3409G",
        "status": "no_tas_available",
        "branch": "",
        "branch_note": "",
        "category_mismatch": False,
        "notes": (
            "Minecraft's procedurally-generated world (RSG — Random Seed Glitchless — "
            "is the human community standard) makes a traditional TAS fundamentally "
            "incomparable: every run uses a different seed. A set-seed TAS would be "
            "comparable only to set-seed human categories, which our dataset does not "
            "track. TASVideos game entry ID 3409 exists but has 0 published TAS and "
            "1 rejected submission as of 2025."
        ),
        "timeline": [],
        "all_publications": [],
    },

    # ------------------------------------------------------------------
    # The Talos Principle — No documented TAS
    # Puzzle game; no formal TAS published anywhere as of 2025.
    # ------------------------------------------------------------------
    {
        "game": "The Talos Principle",
        "game_slug": "the-talos-principle",
        "tasvideos_game_id": None,
        "source": "N/A",
        "source_url": "",
        "status": "no_tas_available",
        "branch": "",
        "branch_note": "",
        "category_mismatch": False,
        "notes": (
            "No formal Tool-Assisted Speedrun of The Talos Principle has been published "
            "on TASVideos, SourceRuns, or any documented community archive as of 2025. "
            "The game is not listed in the TASVideos database. "
            "Human any% speedrunning exists on speedrun.com but no TAS benchmark exists."
        ),
        "timeline": [],
        "all_publications": [],
    },
]


# ---------------------------------------------------------------------------
# Write files
# ---------------------------------------------------------------------------

def main() -> None:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    for entry in EXTERNAL_TAS:
        slug = entry["game_slug"]
        out_path = REFERENCE_DIR / f"tas_{slug}.json"
        out_path.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        n = len(entry.get("timeline", []))
        status = entry.get("status")
        print(f"  [{status}] {entry['game']} → {out_path.name}  ({n} timeline entries)")

    print(f"\nWrote {len(EXTERNAL_TAS)} external TAS files to {REFERENCE_DIR}")


if __name__ == "__main__":
    main()
