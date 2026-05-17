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

---

## Extended Analysis — F3a, F3b, and TAS Comparison (added 2026-05-15)

These analyses extend Q3 with three additional questions about the structure of WR
improvement and the proximity to a theoretical minimum. All results land in
`data/analysis/`.

---

### F3a — Post-Breakthrough Dynamics → `q3_stats.json["post_breakthrough_dynamics"]`

**Question:** After the single biggest WR improvement (breakthrough), does the game
continue improving rapidly or flatten out?

**Method:**

The WR time series is split at the largest single-step time reduction — the breakthrough.

1. **Identify the breakthrough:** scan consecutive WR pairs for the maximum improvement
   (first_time − second_time). This is the "glitch drop" or "route discovery" that caused
   the graph's big step.

2. **Pre-breakthrough velocity:** (sum of all pre-break improvements) / (days from first
   WR to the breakthrough WR). Units: seconds saved per day.

3. **Post-breakthrough velocity:** (sum of all post-break improvements) / (days from the
   breakthrough to the final WR). Same units.

4. **Flattening ratio = post_velocity / pre_velocity:**
   - < 0.5 → clear plateau: improvement collapsed after the breakthrough
   - > 1.0 → acceleration: the breakthrough triggered even faster improvement
   - 0.5–1.0 → gradual slowdown (most common)

5. **Post-breakthrough Spearman trend (rho):** rank correlation of post-break improvement
   sizes vs time. ρ < −0.2 = decelerating, ρ > 0.2 = accelerating, else stable.
   Returns `None` when all post-break improvements are identical (constant-input warning
   from scipy; handled gracefully).

6. **Days-to-10%-threshold:** how many days after the breakthrough until individual
   improvements shrink below 10 % of the breakthrough magnitude. A proxy for how quickly
   the community "digested" the discovery and returned to incremental progress.

**Output fields (per game):**

| Field | Description |
|-------|-------------|
| `breakthrough_magnitude_s` | Seconds saved in the single biggest drop |
| `breakthrough_date` | ISO date of that WR |
| `breakthrough_wr_number` | Sequential WR index |
| `breakthrough_pct_of_total` | Breakthrough as % of total ever saved |
| `pre_velocity_s_per_day` | Avg seconds/day saved before the breakthrough |
| `post_velocity_s_per_day` | Avg seconds/day saved after the breakthrough |
| `flattening_ratio` | post_velocity / pre_velocity |
| `post_trend.rho` | Spearman ρ on post-break improvement sizes vs time |
| `post_trend.interpretation` | "decelerating" / "accelerating" / "stable" |
| `days_to_10pct_threshold` | Days until improvements < 10 % of breakthrough |
| `interpretation` | "flattens_after_breakthrough" / "accelerates_after_breakthrough" / "gradual_slowdown" |

**Key design decisions:**
- Breakthrough = max single improvement, NOT the Chow-test break (which is the steepest
  slope change). A route discovery often appears as the biggest single WR, not the
  biggest slope change.
- Velocity (s/day) rather than median improvement is used because it accounts for the
  time between WRs — a game where only 3 WRs were set in 10 years post-break is very
  different from one where 30 WRs happened in 2 years.
- The 10 % threshold is an arbitrary but interpretable proxy for "the community absorbed
  the breakthrough." It is not a formal statistical test.

---

### F3b (Model) — TAS Proximity via Asymptote → `q3_stats.json["tas_proximity"]`

**Question:** How close is the current world record to the theoretical minimum
(TAS floor), and how fast is the gap closing?

**Background:** TAS (Tool Assisted Speedruns) define the optimal route with perfect
execution — the mathematical lower bound for a given category. The WR cannot go below
the TAS time. Modelling how WRs converge toward this floor lets us estimate how much
room for improvement remains.

**Method:**

1. **Fit exp_decay and Gompertz** to each game's WR time series (x = days since first
   WR, y = WR time in seconds). Both models have an explicit floor parameter:
   - exp_decay: `y = a·exp(−b·x) + c`  →  floor = `c`
   - Gompertz:  `y = floor + amp·exp(b·exp(−c·x))`  →  floor = `floor`
   R² threshold of 0.70 required; below this the model is too noisy to trust the
   asymptote estimate.

2. **If no saturating model fits** (R² < 0.70 for both), or the inferred floor is ≥ the
   current WR, the game is classified as `none_detected` — it is still in a log or
   power_law improvement regime with no hard floor visible in the data.

3. **Gap metrics:**
   - `gap_to_floor_s` = current_wr − floor (seconds remaining)
   - `gap_to_floor_pct_of_first_wr` = gap / first_wr × 100 (normalised)
   - `pct_of_theoretical_reduction_achieved` = (first_wr − current_wr) / (first_wr − floor) × 100
     (how much of the mathematically possible improvement has been realised)

4. **Convergence velocity:** average seconds closed per year, computed from the last
   min(5, n−1) WRs. Uses recent improvement rate rather than the full historical average
   because improvement rates change over time.

5. **Estimated years to floor:** gap / convergence_velocity. A rough forward projection;
   subject to large uncertainty because improvement rates are not constant.

**Output fields (per game):**

| Field | Description |
|-------|-------------|
| `floor_model` | "exp_decay" / "gompertz" / "none_detected" |
| `theoretical_floor_s` | Asymptote in seconds (TAS proxy) |
| `current_wr_s` | Current world record in seconds |
| `gap_to_floor_s` | Remaining gap in seconds |
| `gap_to_floor_pct_of_first_wr` | Gap as % of the first-ever WR time |
| `pct_of_theoretical_reduction_achieved` | % of (first − floor) already cut |
| `convergence_velocity_s_per_year` | Seconds/year currently closing the gap |
| `estimated_years_to_floor` | Rough projection at current pace |
| `note` | Set only when `floor_model = none_detected` |

**Key design decisions:**
- The asymptote is used as a TAS *proxy*, not a true TAS time. See F3b (Reference) below
  for the approach that uses actual TAS times.
- R² ≥ 0.70 is a conservative threshold. Some games with valid floors may be excluded
  if the WR series is too noisy or too short to fit a reliable asymptote.
- Games with `none_detected` are typically younger games still in active discovery
  (Celeste, Hollow Knight) or games where improvement is fundamentally unbounded.

---

### F3b (Reference) — TAS vs Human WR → `f3b_tas_stats.json`

**Question:** For games where actual TAS times are publicly documented, how close is
the human WR and how fast is the gap closing?

**Why a separate module from the asymptote approach above:**
speedrun.com prohibits TAS submissions on standard leaderboards (site rules). The
canonical TAS archive is TASVideos.org which has no public API. TAS times are therefore
sourced from a manually curated reference file (`data/reference/tas_known.json`).

**Academic framing:**
Wooten (2022, *Production and Operations Management*, "Leaps in Innovation and the
Bannister Effect in Contests") formally models how benchmark innovations stimulate
subsequent progress through technique diffusion. TAS serves exactly this role in
speedrunning: once TAS demonstrates a strategy is possible, the human RTA community
works to adopt it. The gap narrows through route diffusion, not independent re-discovery.

The Sports Science literature on the "Bannister Effect" (first sub-4-minute mile in 1954)
shows the same mechanism: the post-Bannister clustering of sub-4-minute miles is better
explained by training/technique diffusion than psychological barrier removal (Science of
Running, 2017). For speedrunning, the diffusion channel is TAS route documentation.

**Method:**

1. **TAS reference file** (`data/reference/tas_known.json`):
   - Manually curated TAS times for games where the TAS category is directly comparable
     to the human Any% category we track.
   - `null` for games where no comparable TAS exists (procedural games, score-based games,
     or games where ACE glitches make the categories incomparable).
   - Currently includes: Super Mario Bros. (294.265 s, TASVideos/Maru370, 2023),
     Super Metroid (~2446 s), Half-Life 2 (~4494 s).

2. **Gap computation per game:**
   - `current_gap_s` = max(0, human_wr − tas_time)
   - `current_gap_pct` = current_gap / first_wr × 100
   - `pct_closed` = (first_wr − current_wr) / (first_wr − tas_time) × 100

3. **Historical gap timeline:** for every WR in the progression, the gap to TAS is
   recorded. This shows whether the gap has been narrowing consistently or in jumps.

4. **Gap velocity:** average gap-closing rate (s/year) from the last 5 WRs. Projects
   how long until the human WR matches the TAS.

5. **Model validation:** for games where both an actual TAS time AND an asymptote
   estimate exist, `model_vs_tas_delta_s` = model_floor − tas_time. A positive delta
   means the model overestimates the floor (too pessimistic about how good humans can get).

**Output:**

`data/analysis/f3b_tas_stats.json`

| Key | Description |
|-----|-------------|
| `games[]` | Per-game comparison results |
| `skipped[]` | Games without a comparable TAS reference (with reason) |
| `summary` | Cross-game aggregates: mean gap %, games that matched TAS, model accuracy |

---

### Tests → `Dataset/Test/`

All analysis modules are covered by a pytest suite. Run from `Dataset/` with:

```powershell
python -m pytest Test/ -v
```

| File | Covers |
|------|--------|
| `test_models.py` | All curve-fitting functions, AIC ordering, Chow test |
| `test_q1_analysis.py` | `_velocity_trend`, `_power_law_on_improvements` |
| `test_q2_analysis.py` | `_detect_structural_break`, `_analyse_game` |
| `test_q3_analysis.py` | `_gini`, `_kaplan_meier`, `_km_predict`, F3a DTO, F3b proxy DTO |
| `test_f3b_tas_analysis.py` | `_build_gap_history`, `_gap_velocity`, `_analyse_game`, `_cross_game_summary`, DTOs |

**Total: 134 tests, 0 failures.**

**Notable test design choices:**
- No CSV or JSON data files are required — all tests use synthetic in-memory data.
- The Chow test is NOT tested on a perfect straight line because floating-point arithmetic
  makes RSS_pooled slightly larger than RSS1+RSS2, giving a spurious F > 3.0. A small-
  noise linear trend is used instead, asserting F < 15 (true breaks have F >> 100).
- Gini max is (n−1)/n, so the "single dominant value → Gini near 1" test uses n=20 to
  reach a ceiling of 0.95 rather than n=5 which caps at 0.80.
- `spearmanr` returns NaN when its input is a constant array. `_post_breakthrough_dynamics`
  catches this and stores `None` in `post_trend.rho`; the tests account for this.
- `_gap_velocity` uses the last 5 WRs; the "stagnant gap" test uses 7 rows so that all
  5 recent WRs are identical (using 6 rows would include the earlier 500→350 drop).

---

### DTOs → `shared/DTOs/`

Analysis functions that return structured objects use DTOs (Data Transfer Objects).

| Class | File | Returned by |
|-------|------|-------------|
| `PostBreakthroughResult` | `q3_dtos.py` | `_post_breakthrough_dynamics()` |
| `PostTrendDTO` | `q3_dtos.py` | embedded in `PostBreakthroughResult` |
| `TasProximityResult` | `q3_dtos.py` | `_tas_proximity()` |
| `TasComparisonResult` | `f3b_dtos.py` | `_analyse_game()` in `f3b_tas_analysis.py` |
| `TasGapSnapshot` | `f3b_dtos.py` | embedded in `TasComparisonResult.gap_history` |

**Why DTOs instead of raw dicts:**
- Typed fields — missing a required field raises `TypeError` at construction, not a silent
  `KeyError` at read time
- Attribute access (`result.floor_s`) over `result.get("floor_s")`
- `.to_dict()` produces the exact JSON structure expected by `run.py` and the tests
- All new analysis functions must follow this pattern

---

### Visualisation → `visualise/`

Two new terminal charts are registered in `visualise/charts/registry.py`:

| Input file | Chart function | What it shows |
|-----------|---------------|---------------|
| `data/analysis/q3_stats.json` | `graph_f3a_post_breakthrough` | Flattening ratios + breakthrough magnitude % per game |
| `data/analysis/f3b_tas_stats.json` | `graph_f3b_tas_comparison` | TAS gap per game + gap history timeline |

To view:
```powershell
# From visualise/ directory:
python main.py
# At prompt, type:  q3_stats   or   f3b_tas_stats
```

Or use the `all` mode with `analysis` to see all analysis charts at once.

The Model project (`Model/`) reads from `Dataset/data/analysis/` via `ANALYSIS_DIR` in
`Model/config.py`. The new `f3b_tas_stats.json` is therefore automatically available to
the LLM council for F3b inference without any Model code changes.

---

---

## TAS Fetch — Per-Game TAS Improvement Timelines (added 2026-05-17)

Two new scripts fetch TAS evolution data for all 17 games in the dataset, creating
individual JSON files in `data/reference/tas_{game_slug}.json`.

---

### Scripts

| Script | Purpose |
|--------|---------|
| `fetch_tas.py` | Fetches TAS timelines from TASVideos.org API for games hosted there |
| `curate_tas_external.py` | Creates manually-curated TAS timelines for games hosted outside TASVideos |

Run `python main.py --tas` to run `fetch_tas.py`, or run the scripts independently.
Use `python fetch_tas.py --force` to re-fetch all TASVideos data.

---

### TAS Data per Game

| Game | Status | Source | n TAS records | Time range |
|------|--------|--------|---------------|-----------|
| Super Mario Bros. | found | TASVideos pub chain (warps branch) | 13 | 2003–2011 |
| Super Mario 64 | found | TASVideos (16 stars branch) | 6 | 2005–2026 |
| Celeste | found | TASVideos (baseline branch) | 1 | 2019 |
| Super Metroid | found ⚠️ | TASVideos (baseline branch, category mismatch) | 11 | 2004–2018 |
| Zelda: OoT | found | TASVideos (baseline branch, ACE route) | 6 | 2006–2014 |
| Pokemon Red/Blue | found | TASVideos (baseline + warp/save glitch branches) | 7 | 2005–2011 |
| Final Fantasy VII | found | TASVideos (baseline branch) | 3 | 2019–2025 |
| Doom | found ⚠️ | TASVideos (The Ultimate Doom, all 4 episodes) | 4 | 2015–2020 |
| Donkey Kong | found | TASVideos (arcade, single pub) | 1 | 2018 |
| Quake | found | Quake Done Quick / Speed Demos Archive | 6 | 1997–2024 |
| Half-Life 2 | found | SourceRuns.org | 2 | 2014–2016 |
| Portal | found | SourceRuns.org (OoB TAS, Jukspa et al.) | 2 | 2012–2016 |
| Portal 2 | found | Portal 2 TASing community / SourceRuns | 1 | 2022 |
| Hollow Knight | found | YouTube community TAS (ConstructiveCynicism) | 1 | 2021 |
| Pac-Man | found_proxy ⚠️ | TASVideos NES Tengen proxy (arcade not on TASVideos) | 1 | 2023 |
| Minecraft: Java Edition | no_tas_available | — (procedural generation prevents meaningful TAS) | 0 | — |
| The Talos Principle | no_tas_available | — (no documented TAS exists anywhere as of 2025) | 0 | — |

⚠️ = category mismatch or proxy (TAS branch does not exactly match human Any% category).

---

### Output JSON Schema

Each file `data/reference/tas_{game_slug}.json` contains:

```json
{
  "game": "...",
  "tasvideos_game_id": 1,
  "source": "TASVideos.org",
  "source_url": "https://tasvideos.org/Movies-List-1G-Obs",
  "status": "found",
  "branch": "warps",
  "branch_note": "...",
  "category_mismatch": false,
  "timeline": [
    {
      "publication_id": 665,
      "date": "2003-12-06",
      "time_s": 315.65,
      "authors": ["Bisqwit"],
      "is_current": false
    }
  ],
  "first_tas": {"date": "2003-12-06", "time_s": 315.65},
  "current_best": {"date": "2011-01-06", "time_s": 297.31},
  "n_improvements": 13,
  "pct_improvement_total": 5.81
}
```

`timeline` = only entries that set a new TAS record (progression, like WR progression for humans).
`all_publications` = every valid publication for the branch, including non-improving ones.

---

### Unrealistic Run Filter

`fetch_tas.py` applies the same filter as `clean.py`'s `sanitize_wr_progressions`:

- Compute **median time** across all publications for the branch
- Drop any entry where `time_s < min(1.0, 0.01 × median)` AND `median > 10.0`

This catches ACE-based TAS entries that appear in the wrong branch (e.g., an arbitrary-code-
execution run filed under a non-ACE branch), which would be impossibly fast relative to the
genuine TAS progression.

---

### How TASVideos API Was Used

- `GET /api/v1/publications/{id}` — works for **both current and obsoleted** publications.
  The TAS timeline requires obsoleted publications since they represent historical improvements.
- `GET /Movies-List-{gameId}G-Obs` — HTML page listing all publication IDs (current + obsoleted)
  for a game. Used to discover which pub IDs to fetch.
- Branch field: TASVideos uses `"baseline"` as the API branch name for the primary/Any% category.
  The human-readable branch name (e.g., "warps", "game end glitch") appears in the `title` field.
- Time calculation: `frames / systemFrameRate = seconds`.

---

## F3b+ — TAS Release Impact on WR Velocity (added 2026-05-17)

**Question:** Does a new TAS record accelerate human WR improvement in the following months?
This is the quantitative Bannister Effect: a TAS acts as an "existence proof" that faster times
are possible, motivating human runners to adopt the same route.

### Method

For each TAS record release across all 17 games, `f3b_tas_analysis.py` computes a
**before/after event study** in a fixed `window_days` window (default: 180 days):

| Metric | Formula | Interpretation |
|--------|---------|---------------|
| `wr_at_tas_s` | last human WR with date ≤ TAS date | baseline WR active when TAS came out |
| `wr_post_s` | min(WR times in `(tas_date, tas_date + window_days]`) | best WR achieved in the window |
| `improvement_s` | `wr_at_tas_s − wr_post_s` | seconds improved (0 if no new WR in window) |
| `improvement_pct` | `improvement_s / wr_at_tas_s × 100` | relative improvement |
| `n_wrs_in_window` | count of WRs in `(tas_date, tas_date + window_days]` | activity in the period |
| `vel_pre_s_per_year` | `(wr_start − wr_end) / span_days × 365` over `[tas_date − window, tas_date]` | WR velocity before TAS |
| `vel_post_s_per_year` | same formula over `(tas_date, tas_date + window]` | WR velocity after TAS |
| `velocity_ratio` | `vel_post / vel_pre` | > 1 = TAS accelerated improvement (Bannister Effect) |

### Aggregate summary across all TAS events

From 42 TAS-impact events (games with non-mismatch TAS data):

- **19/42** TAS releases were followed by at least one WR improvement within 180 days
- **Mean improvement**: 48.6 s per TAS event
- Velocity ratio computed for 5 events (requires ≥2 WRs in both pre and post windows)
- **Half-Life 2 (2016)**: velocity ratio 1.35× — the only clear accelerated improvement case

### Notes / Limitations

- **Category mismatches** (⚠ games) distort the comparison; e.g., Hollow Knight TAS is NMG-restricted
  while human any% uses unrestricted glitches.
- **Short human WR history on speedrun.com**: games whose WR data starts after 2010 may miss
  TAS events from the 1990s–2000s (Quake Done Quick, early SourceRuns).
- A velocity ratio < 1 does not necessarily mean TAS had no effect — the human WR might already
  have been improving rapidly before the TAS, and the TAS simply maintained that pace.
- No regression was run due to insufficient per-game TAS data points (1–13 events per game).
  The before/after event study is the appropriate non-parametric alternative.

### Output

Added to `data/analysis/f3b_tas_stats.json` under key `"tas_impact"`:
```json
{
  "window_days": 180,
  "events": [ { "game": "...", "tas_date": "...", "improvement_s": ..., "velocity_ratio": ..., ... } ],
  "summary": { "n_tas_events": 42, "n_with_wr_improvement": 19, "mean_velocity_ratio": 0.6, ... }
}
```

### New DTO: `TasImpactWindow` (`shared/DTOs/f3b_dtos.py`)

One instance per TAS event. Key fields: `tas_date`, `tas_time_s`, `wr_at_tas_s`, `wr_post_s`,
`improvement_s`, `improvement_pct`, `n_wrs_in_window`, `vel_pre_s_per_year`,
`vel_post_s_per_year`, `velocity_ratio`, `window_days`.

---

## References

### Data Sources

| # | Source | Used for |
|---|--------|---------|
| [1] | speedrun.com API v1 — https://github.com/speedruncomorg/api | Primary data source: all WR runs, categories, leaderboards |
| [2] | TASVideos.org — https://tasvideos.org | TAS reference times for F3b (curated manually; no public API) |
| [3] | Speed Demos Archive — https://speeddemosarchive.com/TAS.html | TAS methodology documentation; route-transfer mechanism description |

### Academic / Research Literature

| # | Reference | Used for |
|---|-----------|---------|
| [4] | Wooten, D. B. (2022). *Leaps in Innovation and the Bannister Effect in Contests*. Production and Operations Management. https://doi.org/10.1111/poms.13707 | Theoretical framework for F3b: TAS as a benchmark innovation that stimulates subsequent human WR progress through technique diffusion |
| [5] | Magness, S. (2017). *The Roger Bannister Effect: The Myth of the Psychological Breakthrough*. Science of Running. https://www.scienceofrunning.com/2017/05/the-roger-bannister-effect | Counter-argument to purely psychological framing; supports technique/route diffusion as the real mechanism — directly applicable to TAS route adoption |
| [6] | Akaike, H. (1974). A new look at the statistical model identification. *IEEE Transactions on Automatic Control*, 19(6), 716–723. | AIC model selection criterion used in Q2 curve fitting (models.py) |
| [7] | Kaplan, E. L., & Meier, P. (1958). Nonparametric estimation from incomplete observations. *Journal of the American Statistical Association*, 53(282), 457–481. | Kaplan-Meier estimator used in Q3 (right-censoring treatment for WR lifetimes) |
| [8] | Chow, G. C. (1960). Tests of equality between sets of coefficients in two linear regressions. *Econometrica*, 28(3), 591–605. | Chow test for structural break detection in WR time series (Q2, models.py) |
| [9] | Kruskal, W. H., & Wallis, W. A. (1952). Use of ranks in one-criterion variance analysis. *Journal of the American Statistical Association*, 47(260), 583–621. | Kruskal-Wallis H-test used for cross-genre improvement rate comparison (Q1, Q3) |
| [10] | Mann, H. B., & Whitney, D. R. (1947). On a test of whether one of two random variables is stochastically larger than the other. *Annals of Mathematical Statistics*, 18(1), 50–60. | Mann-Whitney U test for pairwise genre comparison (Q3) |
| [11] | Spearman, C. (1904). The proof and measurement of association between two things. *The American Journal of Psychology*, 15(1), 72–101. | Spearman rank correlation for improvement velocity trend detection (Q1) |
| [12] | Gompertz, B. (1825). On the nature of the function expressive of the law of human mortality. *Philosophical Transactions of the Royal Society*, 115, 513–583. | Gompertz S-curve model used for asymmetric saturation fitting (Q2, models.py) |

### Community / Analytical Sources

| # | Source | Used for |
|---|--------|---------|
| [13] | Bamsoftware.com speedrun WR visualisation — https://www.bamsoftware.com/computers/speedrun-wr/ | Referenced as prior descriptive WR analysis; confirms structural-break visual patterns |
| [14] | *Setting World Records in Speedrunning: Technical, Strategic and Psychological Considerations* — Academia.edu (2024) — https://www.academia.edu/144611877 | Frames TAS as "research tool" not competitor; supports F3b framing |
| [15] | LessWrong linkpost: *Analysis of World Records in Speedrunning* — https://www.lesswrong.com/posts/nhjaegqWxbBhiqMGS | Identifies "successive cascades of improvements" pattern; validates structural break model approach |
| [16] | speedrun.com site rules — https://www.speedrun.com/support/learn/site-rules | Confirms TAS prohibition on standard leaderboards; explains why no TAS API exists |
| [17] | TASVideos REST API — https://tasvideos.org/api (Swagger UI) | TAS timeline fetch: `/publications/{id}` returns frame count + framerate for obsoleted and current runs; used by `fetch_tas.py` |
| [18] | TASVideos Movies-List pages — https://tasvideos.org/Movies-List-{id}G-Obs | Lists all publication IDs for a game (current + obsoleted); used to discover which pubs to fetch for the TAS timeline |
| [19] | Quake Done Quick — https://quake.speeddemosarchive.com/quake/qdq/ | Full history of Quake TAS (QdQ series, 1997–2024): 19:49 → 8:43 across all episodes on Nightmare difficulty |
| [20] | Wikipedia: Quake done Quick — https://en.wikipedia.org/wiki/Quake_Done_Quick | Release dates and total times for QdQ, QdQ Quicker, QdQ with a Vengeance; confirms September 2000 release and bunny-hopping breakthrough |
| [21] | SourceRuns.org — https://sourceruns.org | Half-Life 2 "Done Quicker" TAS (40:49, 2016); Portal TAS documentation by Jukspa (5:13.665, 2016) |
| [22] | Jukspa Portal TASing documentation — https://www.speedrun.com/Portal/guide/ptmif | Documents Portal OoB TAS routing and techniques; basis for Portal timeline entry |
| [23] | Portal 2 TAS premiere (SGDQ 2022) — https://www.youtube.com/watch?v=MZi1dXwCqG8 | First ever Portal 2 full-game TAS: 47:13.033, Inbounds No SLA, by "Can't Even" and mlugg |
| [24] | Hollow Knight Any% NMG TAS — https://www.youtube.com/watch?v=XBpo9j-I4kI | ConstructiveCynicism NMG TAS in 28:59.37 (2021); first major community Hollow Knight TAS |
| [25] | TASVideos Pac-Man (NES Tengen) pub #5231 — https://tasvideos.org/5231M | NES Tengen Pac-Man TAS by eien86 in 12:02.86 (2023); used as proxy for arcade Pac-Man (original arcade not on TASVideos) |
| [26] | Campbell, D.T., & Stanley, J.C. (1963). *Experimental and Quasi-Experimental Designs for Research*. Rand McNally. | Theoretical basis for the before/after event-study methodology used in F3b+ TAS impact analysis; specifically the interrupted time-series design (Chapter 5) |
| [27] | MacKinlay, A.C. (1997). Event studies in economics and finance. *Journal of Economic Literature*, 35(1), 13–39. https://www.jstor.org/stable/2729691 | Event-study methodology for measuring the impact of discrete events on time-series outcomes — adapted here to measure the effect of TAS publication on human WR velocity |
| [28] | Wooten, D.B. (2022). *Leaps in Innovation and the Bannister Effect in Contests*. Production and Operations Management. https://doi.org/10.1111/poms.13707 | Formal model of the Bannister Effect (also cited as [4]); `velocity_ratio` operationalises Wooten's "diffusion acceleration" hypothesis |
