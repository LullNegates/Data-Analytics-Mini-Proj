# Dataset -- Speedrun World Record Data

Source: speedrun.com API v1 (https://github.com/speedruncomorg/api)
Coverage: 17 games across 7 genres, Any% category (or equivalent)

---

## Pipeline

```
fetch.py  ->  data/raw/*.json
clean.py  ->  data/clean/*.csv
analysis/ ->  data/analysis/*.json
```

Run everything:

```powershell
# fetch + clean only:
python main.py

# fetch + clean + statistical analysis:
python main.py --stats

# statistical analysis only (if clean data already exists):
python analysis/run.py
```

---

## Fetcher (fetch.py)

Calls the speedrun.com v1 `/runs` endpoint for each game in `config.py`.

**Pagination:** The API has a hard limit of offset < 10000 (400 error beyond that).
For games with >10000 runs (e.g. Minecraft), `fetch.py` performs two passes:
1. Forward pass -- date ascending, up to offset 9800
2. Reverse pass -- date descending, up to offset 9800, fills the tail end

Results are merged by run_id and sorted by date. Games with 10000-20000 runs
will have full coverage. Games with >20000 runs may have a gap in the middle,
but all WR-setting runs (which span the full time range) will be captured.

**Resumable:** already-fetched game files are skipped. Old-format files missing
`all_runs` are automatically re-fetched. Re-running is always safe.

**Rate limiting:** 0.65 second delay between requests (config.py `REQUEST_DELAY`).

---

## Cleaner (clean.py)

Reads every file in `data/raw/` and outputs five CSVs to `data/clean/`.

### all_runs.csv

Every valid run for every game, with an `is_wr` flag.

| Column | Description |
|--------|-------------|
| game, genre, category | Game metadata |
| date | Run submission date (ISO 8601) |
| time_seconds | Primary time in seconds |
| run_id | speedrun.com run ID |
| is_wr | True if this run set a new world record |

### wr_progression.csv

Only WR-setting runs -- the running minimum time series per game.

| Column | Description |
|--------|-------------|
| game, genre, category | Game metadata |
| wr_number | Sequential WR index (1 = first ever) |
| date | Date WR was set |
| time_seconds | WR time in seconds |

### q1_reduction.csv

One summary row per game -- computed statistics for Q1.

| Column | Description |
|--------|-------------|
| pct_reduction | (first_time - last_time) / first_time * 100 |
| years_span | Years between first and last WR |
| annual_rate_pct | pct_reduction / years_span |
| wr_density_per_year | WR count / years_span |
| improvement_velocity_s_per_day | Avg seconds saved per day over the full span |
| median_improvement_s | Median seconds saved per individual WR |

### q2_saturation.csv

One row per WR for games with >= 5 WRs spanning >= 2 years.
Used for curve fitting (log, power law, exponential decay).

| Column | Description |
|--------|-------------|
| days_since_first | Days elapsed since the first WR |
| time_seconds | WR time in seconds (y-axis for regression) |
| improvement_s | Seconds saved vs previous WR (0 for first) |
| pct_of_total_reduction | Cumulative % of total reduction achieved at this WR |

### q3_lifetimes.csv

One row per WR -- how long each record stood before being broken.
The final WR per game has `is_final=True` (still standing; open lifetime).

| Column | Description |
|--------|-------------|
| wr_set_date | Date the record was set |
| wr_broken_date | Date it was broken (empty if is_final) |
| duration_days | Days the record stood (empty if is_final) |
| decade | Decade the record was set in (e.g. "2010s") |
| improvement_s | Seconds saved when this record was later broken |
| is_final | True if this is the current standing WR |

---

## Statistical Analysis (analysis/)

Reads from `data/clean/`, writes JSON results to `data/analysis/`.

### models.py

Curve fitting utilities used by all three analysis modules.

| Model | Formula | Best for |
|-------|---------|---------|
| log | a * ln(x+1) + b | Classic diminishing returns |
| power_law | a * x^b | Front-loaded improvement; b < 0 = diminishing returns |
| exp_decay | a * exp(-b*x) + c | Times converging on a hard floor (asymptote c) |
| poly2 | a*x^2 + b*x + c | Baseline / U-shaped curves |
| lowess | Non-parametric smoother | Detecting regime changes without assuming a formula |

Model selection uses AIC (Akaike Information Criterion) -- lower is better.
AIC penalises model complexity so exp_decay (3 params) must outperform log (2 params)
by more than the penalty to win.

### q1_analysis.py -> data/analysis/q1_stats.json

- Power law fit to per-WR improvement sizes (confirms / quantifies diminishing returns)
- Spearman correlation: improvement size vs time (velocity trend: accelerating/decelerating)
- Genre aggregation: mean/median annual rate, WR density
- Kruskal-Wallis test across genres: H0 = annual rates drawn from same distribution

### q2_analysis.py -> data/analysis/q2_stats.json

- Per-game: fits log, power law, exp_decay, poly2; ranks by AIC
- Best model identification with R2, RMSE, AIC, BIC
- Saturation point estimation (exp_decay only): days until 95% of max reduction reached
- Improvement acceleration: linear trend on per-WR improvement sizes over time

### q3_analysis.py -> data/analysis/q3_stats.json

- Per-genre lifetime stats: mean, median, std, 25th/75th percentile
- Gini coefficient (duration): inequality of record lifetimes (0=equal, 1=one record dominates)
- Gini coefficient (improvement): inequality of improvement sizes per genre
- Kruskal-Wallis: are lifetime distributions different across genres?
- Mann-Whitney U: pairwise genre comparisons (corrected for multiple comparisons by reporting p-values)
- Decade comparison: are modern WRs shorter-lived than older ones?

---

## Games

| Genre | Game | Category |
|-------|------|---------|
| Platformer | Super Mario Bros. | Any% |
| Platformer | Super Mario 64 | Any% |
| Platformer | Celeste | Any% |
| Action-Adventure | Super Metroid | Any% |
| Action-Adventure | The Legend of Zelda: Ocarina of Time | Any% |
| Action-Adventure | Hollow Knight | Any% |
| RPG | Pokemon Red/Blue | Any% |
| RPG | Final Fantasy VII | Any% |
| FPS | Doom | Any% |
| FPS | Quake | Any% |
| FPS | Half-Life 2 | Any% |
| Puzzle | Portal | Out of Bounds |
| Puzzle | Portal 2 | Any% |
| Puzzle | The Talos Principle | Any% |
| Sandbox | Minecraft: Java Edition | Any% |
| Arcade | Pac-Man | Any% |
| Arcade | Donkey Kong | Any% |
