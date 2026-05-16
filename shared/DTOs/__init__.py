"""
DTOs (Data Transfer Objects) for the speedrun analysis pipeline.

All analysis functions that return structured data should use a DTO instead of
a raw dict. Benefits:
  - Type-checked fields at construction time
  - .to_dict() produces the exact JSON structure expected by run.py / tests
  - IDE autocomplete on field access
  - Explicit None handling rather than dict.get() scattered across callers

Usage:
    from shared.DTOs.q3_dtos import PostBreakthroughResult, TasProximityResult

    result = PostBreakthroughResult(game="Celeste", ...)
    json_safe = result.to_dict()          # for JSON serialisation
    game_name = result.game               # typed attribute access
"""
