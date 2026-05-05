API_BASE = "https://www.speedrun.com/api/v1"
REQUEST_DELAY = 0.65  # seconds between requests — stay under API rate limit

# 16 games across 7 genres.
# Genre spread is required for Q3 (WR lifetime by genre): aim for >= 2 games per genre.
# Era spread is required for Q2 (saturation): arcade games go back to 1980/81.
GAMES = [
    # Platformer — 3 games (1985–2018)
    {"name": "Super Mario Bros.",                     "genre": "Platformer",      "category": "Any%"},
    {"name": "Super Mario 64",                        "genre": "Platformer",      "category": "Any%"},
    {"name": "Celeste",                               "genre": "Platformer",      "category": "Any%"},

    # Action-Adventure — 3 games (1994–2017)
    {"name": "Super Metroid",                         "genre": "Action-Adventure","category": "Any%"},
    {"name": "The Legend of Zelda: Ocarina of Time",  "genre": "Action-Adventure","category": "Any%"},
    {"name": "Hollow Knight",                         "genre": "Action-Adventure","category": "Any%"},

    # RPG — 2 games
    {"name": "Pokemon Red/Blue",                      "genre": "RPG",             "category": "Any%"},
    {"name": "Final Fantasy VII",                     "genre": "RPG",             "category": "Any%"},

    # FPS — 3 games (1993–2004)
    {"name": "Doom",                                  "genre": "FPS",             "category": "Any%"},
    {"name": "Quake",                                 "genre": "FPS",             "category": "Any%"},
    {"name": "Half-Life 2",                           "genre": "FPS",             "category": "Any%"},

    # Puzzle — 3 games (2007–2015)
    {"name": "Portal",                                "genre": "Puzzle",          "category": "Out of Bounds"},
    {"name": "Portal 2",                              "genre": "Puzzle",          "category": "Any%"},
    {"name": "The Talos Principle",                   "genre": "Puzzle",          "category": "Any%"},

    # Sandbox — 1 game
    {"name": "Minecraft: Java Edition",               "genre": "Sandbox",         "category": "Any%"},

    # Arcade — 2 games (1980–1981), critical for Q2: decades of WR history
    {"name": "Pac-Man",                               "genre": "Arcade",          "category": "Any%"},
    {"name": "Donkey Kong",                           "genre": "Arcade",          "category": "Any%"},
]
