# Dataset -- Speedrun World Record Data

Source: speedrun.com API v1 (https://github.com/speedruncomorg/api)
Coverage: 17 games across 7 genres, Any% category (or equivalent)
Project: FHDW Data Analytics Mini-Project -- Speedrunning World Records

---

## Research Questions (KAOS)

The entire pipeline exists to answer three questions:

**Q1 — How much have world records improved?**
Compare total time reduction, annual improvement rate, and WR frequency across games
and genres. Determine whether improvement rates differ significantly between genres
(e.g. do FPS games improve faster than RPGs?) and whether each game's improvement
is accelerating or decelerating.

**Q2 — Is the rate of improvement slowing down (saturation)?**
Model the WR time series for each game as a mathematical curve. If exp_decay or
Gompertz wins the AIC comparison, the game is approaching a hard floor (theoretical
human limit). Detect structural breaks -- sudden inflection points where a new
glitch or route discovery "reset" the game's improvement trajectory.

**Q3 — How long do world records last?**
Measure WR lifetimes (days a record stood before being broken) by genre and decade.
Account for right-censoring: the current record is still standing and must not be
dropped from the analysis. Use Kaplan-Meier survival analysis to estimate the true
median lifespan including ongoing records.

---

## Pipeline

```
fetch.py  →  data/raw/*.json
clean.py  →  data/clean/*.csv
analysis/ →  data/analysis/*.json
```

Run everything:

```powershell
# Fetch + clean only:
python main.py

# Fetch + clean + statistical analysis:
python main.py --stats

# Statistical analysis only (if clean data already exists):
python analysis/run.py
```

---

## Fetcher (fetch.py)

Calls the speedrun.com v1 `/runs` endpoint for each game in `config.py`.

**Pagination:** The API enforces a hard ceiling of offset < 10,000 (returns 400
beyond that). For games with more than 10,000 runs (e.g. Minecraft), `fetch.py`
uses two passes:

1. Forward pass — date ascending, up to offset 9,800 (oldest runs first)
2. Reverse pass — date descending, up to offset 9,800 (newest runs first)

Results are merged by run_id (deduplication via Python dict) and sorted by date.
This strategy gives full coverage for games with up to ~19,600 runs. Games with
more submissions may have a gap in the middle of their run history. However, WR
progression is computed as a running minimum over time, so WR-setting runs are
captured in both the oldest and newest slices -- the gap affects `all_runs.csv`
completeness, not `wr_progression.csv` correctness.

**Note on the API:** The speedrun.com v1 API does not support date-based filtering
on the `/runs` endpoint, so windowed pagination is not possible without a different
data source.

**Resumable:** already-fetched game files are skipped. Files missing `all_runs`
(old format from an earlier pipeline version) are automatically re-fetched.

**Rate limiting:** 0.65s delay between requests (`config.py REQUEST_DELAY`).

---

## Cleaner (clean.py)

Reads every JSON file in `data/raw/` and outputs five CSVs to `data/clean/`.

### all_runs.csv

Every valid run for every game, with an `is_wr` flag.

| Column | Description |
|--------|-------------|
| game, genre, category | Game metadata |
| date | Run submission date (ISO 8601) |
| time_seconds | Primary time in seconds |
| run_id | speedrun.com run ID |
| is_wr | True if this run set a new world record |

**Why it matters:** Used in Q1 to compute `wr_rate` (WR count ÷ total submissions).
This normalizes WR density by community activity: a game with 2 WRs per year but
10,000 submissions per year is very hard to improve; a game with 2 WRs per year
and 50 submissions is being actively optimized at high success rate.

---

### wr_progression.csv

Only WR-setting runs -- the running minimum time series per game, sorted by date.

| Column | Description |
|--------|-------------|
| game, genre, category | Game metadata |
| wr_number | Sequential WR index (1 = first ever) |
| date | Date WR was set |
| time_seconds | WR time in seconds |

**Why it matters:** This is the ground truth for all three questions. Q1 reads the
first and last entry to compute total reduction. Q2 fits curves to this time series.
Q3 measures the gap between consecutive entries.

---

### q1_reduction.csv

One summary row per game/category — compressed statistics for Q1.

| Column | Description |
|--------|-------------|
| wr_count | Number of WRs ever set |
| total_runs | Total submissions fetched |
| pct_reduction | (first_time − last_time) / first_time × 100 |
| years_span | Years between first and last WR |
| annual_rate_pct | pct_reduction / years_span |
| wr_density_per_year | WR count / years_span |
| improvement_velocity_s_per_day | Average seconds saved per day over full span |
| median_improvement_s | Median seconds saved per individual WR |

**Why it matters:** Provides the per-game input for genre comparisons (Q1) and
the Kruskal-Wallis test across genres.

---

### q2_saturation.csv

One row per WR for games with ≥ 5 WRs spanning ≥ 2 years. Used for curve fitting.

| Column | Description |
|--------|-------------|
| days_since_first | Days elapsed since the first WR (x-axis for regression) |
| time_seconds | WR time in seconds (y-axis for regression) |
| improvement_s | Seconds saved vs previous WR (0 for first entry) |
| pct_of_total_reduction | Cumulative % of total reduction achieved at this WR |

**Why it matters:** This is the input for Q2 saturation modelling. The x-axis
(`days_since_first`) is elapsed time; the y-axis (`time_seconds`) is the WR.
Fitting a decreasing curve to this series and selecting by AIC reveals whether
the game is converging on a floor (exp_decay / Gompertz) or still improving
steadily (log / power_law). Games with < 5 WRs or < 2 years of history are
excluded because there are not enough data points to distinguish curve shapes.

---

### q3_lifetimes.csv

One row per WR — how long each record stood. Includes the current standing record.

| Column | Description |
|--------|-------------|
| wr_set_date | Date the record was set |
| wr_broken_date | Date it was broken (empty if still standing) |
| duration_days | Days the record stood; for standing records, days since it was set |
| decade | Decade the record was set in (e.g. "2010s") |
| time_seconds | WR time in seconds |
| improvement_s | Seconds saved when this record was later broken (empty if standing) |
| is_final | True if this is the current standing WR |
| event | 1 = record was broken (event observed); 0 = still standing (right-censored) |

**Why the `event` column matters (right-censoring):**
If you compute the average lifetime of WRs by only looking at broken records, you
systematically exclude the most durable records -- exactly the ones that define
whether a game has reached its human limit. This is called survivorship bias.

The Kaplan-Meier estimator in q3_analysis.py requires both `duration_days` (for
all rows, including current records) and `event` (0 or 1). Current records
contribute to the at-risk pool for as long as they are observed, then "drop out"
without counting as events. This produces an unbiased estimate of median record
lifetime and survival probabilities at benchmark durations (1 year, 2 years).

---

## Statistical Analysis (analysis/)

Reads from `data/clean/`, writes JSON results to `data/analysis/`.

---

### models.py — Curve Fitting Library

Shared utilities used by all three Q-modules.

**Information Criteria (model selection)**

AIC (Akaike Information Criterion) is the primary selection metric. Lower AIC =
better model. AIC penalises complexity: a 3-parameter model (exp_decay) must
fit materially better than a 2-parameter model (log) to win. BIC applies a
heavier penalty for sample size and is reported alongside AIC.

| Model | Formula | Best for |
|-------|---------|---------|
| log | a × ln(x + 1) + b | Classic diminishing returns with no floor |
| power_law | a × x^b | Front-loaded improvement; b < 0 = diminishing returns |
| exp_decay | a × exp(−b × x) + c | Convergence on a hard floor (asymptote c = human limit) |
| poly2 | a×x² + b×x + c | Baseline / anomalous U-shaped curves |
| gompertz | floor + amplitude × exp(b × exp(−c × x)) | Asymmetric S-curve with a hard floor; 4 parameters (vs exp_decay's 3), so AIC penalises it unless the S-shape provides a materially better fit. Best for games where improvement was slow early, accelerated after a breakthrough, then plateaued. |
| lowess | Non-parametric | Detecting regime changes without assuming a formula; excluded from AIC ranking |

**Why Gompertz beats exp_decay for some games:**
A pure exponential decay assumes improvement was fastest on day 1 and has slowed
monotonically ever since. Speedrunning often shows the opposite: early records
improve slowly (community learning the game), then accelerate as glitches are
discovered, then slow as the game approaches its limit. The Gompertz S-curve
captures this asymmetric shape with the same number of parameters as exp_decay.

**Chow Test (structural break detection)**

`chow_test(x, y, split_idx)` computes the F-statistic for the hypothesis that
data before and after `split_idx` follows a different linear regression:

```
F = [ (RSS_pooled − (RSS₁ + RSS₂)) / k ] / [ (RSS₁ + RSS₂) / (N − 2k) ]
```

A high F-statistic means the data is better described by two separate lines than
one continuous line -- evidence of a structural break (new glitch discovered,
major route change, version patch). `q2_analysis.py` scans all valid split points
and reports the one with the highest F-statistic per game. Requires at least 3
points on each side of the split to fit a valid regression. The significance
threshold is F > 3.0, which corresponds to the p = 0.05 critical value for
F(2, ∞) -- a conservative but standard cutoff for large samples.

---

### q1_analysis.py → data/analysis/q1_stats.json

**Answers:** How much have WRs improved, and do improvement rates differ by genre?

**Methods:**

- **Power law fit on per-WR improvement sizes:** x = WR number, y = seconds saved.
  Exponent b < 0 confirms diminishing returns -- each successive WR saves less time
  than the one before it. This is the mathematical signature of saturation.

- **Spearman velocity trend:** Rank correlation between date and improvement size.
  ρ < 0 means improvements are shrinking over time (decelerating toward a limit).
  Spearman (not Pearson) because improvement sizes are right-skewed: a single glitch
  discovery can save orders of magnitude more time than a typical WR. Pearson is
  sensitive to those outliers; Spearman works on ranks and is robust to them.

- **WR rate (wr_count ÷ total_runs):** Fraction of all submitted runs that set a new
  record. A low wr_rate means the community is running frequently but breaking
  records rarely -- a saturation signal. A high wr_rate means the game was in active
  optimization. Normalized by total community activity, unlike raw WR density which
  would confuse "hard to break" with "nobody is playing."

- **Kruskal-Wallis across genres:** Tests whether the distribution of annual
  improvement rates differs significantly across genres. H₀: all genres are drawn
  from the same distribution. Non-parametric because annual rates are skewed (a few
  games with massive glitch-based improvements pull the mean). p < 0.05 means genre
  is a statistically significant predictor of improvement rate.

---

### q2_analysis.py → data/analysis/q2_stats.json

**Answers:** Is improvement slowing down, and when did major breakthroughs happen?

**Methods:**

- **Multi-model fit (log, power_law, exp_decay, poly2, Gompertz) per game:**
  Each model is fitted to (days_since_first, time_seconds). AIC selects the best.
  - exp_decay or Gompertz winning → game is converging on a theoretical minimum
  - log or power_law winning → game is still steadily improving (no floor in sight)
  - poly2 winning → anomalous; usually means insufficient data or non-monotonic history

- **Saturation point (exp_decay only):** The day at which the WR time is within
  5% of the asymptote c. Derived by solving a·exp(−b·x) = 0.05·a for x:
  t = −ln(0.05) / b. This is the "theoretical limit date" -- the point at which
  further improvement would be smaller than typical run-to-run variance. Stored
  in the JSON as `saturation_days_95pct` relative to the first recorded WR.

- **Improvement acceleration (linear slope on improvement sizes over time):**
  A negative slope means each successive WR saves less time → decelerating → saturation.
  A positive slope means improvements are growing → accelerating (active discovery phase).

- **Structural break detection (Chow Test):** Scans every valid split point in the
  WR time series. The split with the highest F-statistic is the most likely
  breakthrough event. Reported with the WR number, date, and whether the F-statistic
  exceeds the p = 0.05 critical value (F > 3.0 for large samples). This directly
  answers the question: "Was there a discrete discovery that caused a step-change in
  improvement rate?" -- the speedrunning equivalent of the Fosbury Flop in high jump.

---

### q3_analysis.py → data/analysis/q3_stats.json

**Answers:** How long do world records last, and which genres produce the most durable records?

**Methods:**

- **Kaplan-Meier Estimator (survival analysis):**
  S(t) = probability that a world record survives longer than t days.
  At each unique event time t: S(t) = S(t−) × (1 − d/n), where d = records broken
  at time t, n = records at risk at time t. Censored records (still standing) reduce n
  but do not count as events.

  *Why this matters:* A simple median of broken records ignores the current standing
  WR. That WR has been standing for some number of days right now, and it will
  continue standing until it's broken. Dropping it artificially makes records appear
  shorter-lived. Kaplan-Meier corrects this by treating the current record's observed
  survival time as a lower bound on its true lifetime.

  **Output per genre:** KM median (days), survival probability at 365 days, survival
  probability at 730 days, number of records still standing.

- **Survival at 1 and 2 years:** Benchmark survival probabilities. A genre with
  survival_at_365 = 0.60 means 60% of records in that genre survive at least one
  year. This is more interpretable than a raw median when records have heavy tails.

- **Gini coefficient (improvement sizes):** Measures inequality of WR improvements.
  A Gini close to 1 means a single WR (likely a glitch discovery) accounted for
  nearly all time reduction -- the game's improvement history is one massive step
  followed by marginal gains. A Gini close to 0 means improvements were distributed
  equally across many WRs (steady optimization).

- **Kruskal-Wallis + pairwise Mann-Whitney U:** Tests whether genres have
  significantly different WR lifetime distributions. Non-parametric because lifetimes
  are right-skewed (a few dominant records pull means far above medians). Mann-Whitney
  U identifies which specific genre pairs are significantly different.

- **Decade comparison:** Descriptive statistics (mean, median, count, standing records)
  per decade. Tells whether modern records are broken faster than historical ones.
  If 2010s records have shorter median lifetimes than 1990s records, the community
  is more competitive now -- which may reflect platform growth rather than the game
  approaching its limit.

---

## Games

| Genre | Game | Category | Notes |
|-------|------|---------|-------|
| Platformer | Super Mario Bros. | Any% | 1985; massive community; likely Gompertz shape due to glitch eras |
| Platformer | Super Mario 64 | Any% | 1996; 120-star excluded intentionally (Any% is shorter, more competitive) |
| Platformer | Celeste | Any% | 2018; younger game; still in active optimization phase |
| Action-Adventure | Super Metroid | Any% | 1994; strong glitch/sequence-break community |
| Action-Adventure | The Legend of Zelda: Ocarina of Time | Any% | 1998; one of the most-studied speedgames |
| Action-Adventure | Hollow Knight | Any% | 2017; modern; active discovery phase |
| RPG | Pokemon Red/Blue | Any% | 1996; timer manipulation glitches cause massive early breaks |
| RPG | Final Fantasy VII | Any% | 1997; slower improvement curve than Pokemon |
| FPS | Doom | Any% | 1993; episode-based category fallback in fetch.py |
| FPS | Quake | Any% | 1996 |
| FPS | Half-Life 2 | Any% | 2004 |
| Puzzle | Portal | Out of Bounds | 2007; OOB chosen over Any% as it's the primary competitive category |
| Puzzle | Portal 2 | Any% | 2011 |
| Puzzle | The Talos Principle | Any% | 2014 |
| Sandbox | Minecraft: Java Edition | Any% | Large submission volume; possible data gap in middle of all_runs |
| Arcade | Pac-Man | Any% | 1980; decades of WR history; critical for Q2 long-arc saturation |
| Arcade | Donkey Kong | Any% | 1981; high-profile WR disputes; provides long time span for Q2 |

**Genre design rationale:**
- ≥ 2 games per genre is required for the Kruskal-Wallis genre test to be meaningful
- Era spread (1980–2018) is required for Q2 decade comparison and long-arc saturation curves
- Arcade games are the most valuable for Q2: they have 40+ years of WR history, which
  gives curve fitting enough signal to distinguish saturation from ongoing improvement
