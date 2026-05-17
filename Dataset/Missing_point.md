# Missing Points & Inconsistencies — Paper vs. Implementation

Comparing the submitted PDF (`Speedrunning_Weltrekord_Analyse.pdf`) against all session logs and the actual code as of 2026-05-17.

---

## Formula Issues

- **F3b Gap% formula vs. reported metric mismatch (CRITICAL)**
  - Paper (§2.2) defines: `Gap% = (t_WR − t_Floor) / t_first × 100`
  - Code (`q3_analysis.py:276`): `gap_to_floor_pct_of_first_wr = gap_to_floor_s / first_wr_s * 100` ← matches the formula
  - BUT Finding 6 and §4.1 report "95.5 % der möglichen Reduktion" and "82.5 %" — these are `pct_achieved`, computed as `(t_first − t_WR) / (t_first − t_Floor) × 100`
  - **These are two different metrics.** `Gap%` = remaining gap as share of first WR. `pct_achieved` = share of total possible reduction that has already been done. The paper defines one and reports the other.
  - Fix: either rename the formula to `pct_achieved = (t_first − t_WR) / (t_first − t_Floor) × 100`, or change the results to report actual `Gap%` values (~3.5 % for HL2, not 95.5 %).

- **F3a velocity formula — denominator not fully specified**
  - Paper: `v_pre = Σ∆t_pre / d_pre` where d is described as total days span of the segment
  - Code (`q3_analysis.py:179`): `pre_span = (pre_dates[-1] - pre_dates[0]).days` — span in days between first and last WR in the segment, NOT total calendar days from game release to breakthrough
  - Paper does not clarify this; a reader could misinterpret d_pre as calendar time from game release

- **η² formula source mismatch**
  - Paper cites Lakens [2013] for `η² = (H − k + 1) / (N − k)`, but Lakens 2013 covers t-tests and ANOVAs, not Kruskal-Wallis
  - The actual formula used for KW-based η² comes from other sources; citing Lakens here is technically inaccurate
  - Numerical result (0.044) is correct for the formula and the reported H/N/k values — only the citation is wrong

---

## Text vs. Table Inconsistencies

- **Model wins count in §3.2 (CONTRADICTION)**
  - Text says: "gefolgt von Gompertz (5/17), exponentiellem Zerfall (4/17)"
  - Table 3.2 shows: Gompertz = **4**, exp_decay = **4**, power_law = **1**
  - Table sums to 6+4+4+2+1 = 17 ✓ — table is correct, text is wrong (Gompertz is 4 not 5)

- **LOWESS listed in methods, absent from results**
  - §2.2 names LOWESS as one of the five candidate models
  - Table 3.2 lists only poly2, Gompertz, exp_decay, log, power_law — LOWESS not shown (0 wins)
  - Either add LOWESS row with 0 wins to Table 3.2, or explain in the text why it never won

- **power_law model not mentioned in the prose of §3.2**
  - Table 3.2 includes power_law (1 win, R² = 0.720) but the paragraph above the table only names poly2, Gompertz, exp_decay, and log — drops power_law entirely

---

## Outdated / Stale Claims

- **Test count: paper says 164, code now has 209**
  - §2.2 "Qualitätssicherung": "Die vollständige Analysepipeline ist durch **164** automatisierte pytest-Tests abgedeckt"
  - After submission, three more sessions added tests: 164 → 185 (rounding audit, +25 `test_utils.py` tests, but actually this was 164→164 in the first post-submission session then 164→209 in the TAS session)
  - Current count as of end of 2026-05-17: **209 tests**

- **F3b: paper says "direct TAS comparison was not feasible" — but we built it**
  - §2.2 F3b and §4.2 Limitations both state that no public API delivers reliable TAS data and frame-accurate video analysis was not feasible
  - Post-submission: `fetch_tas.py` retrieves per-game TAS timelines from TASVideos API (`/api/v1/publications/{id}`) for 9 games; `curate_tas_external.py` manually provides 6 more — 15/17 games now have actual TAS reference data
  - `f3b_tas_analysis.py` computes real `pct_closed`, gap_s, and velocity for each game using these times
  - **Decision: group has agreed to drop this from the paper and keep F3b as "not enough data."** The asymptote-proxy results (HL2 95.5 %, Pokemon 82.5 %) stay as-is. The TAS pipeline is code-only.

- **SMB TAS time corrected post-submission (not in paper)**
  - `tas_known.json` originally contained "Maru370 2023, 294.265 s" — this attribution does not exist on TASVideos
  - Corrected to HappyLee 2011, pub #1715, 297.31 s (warps any%)
  - Paper never cited this value, so no paper change needed, but the reference file is now correct

- **Super Mario 64 category mismatch (not addressed in paper)**
  - The code's SM64 dataset is 120-Star, not Any% (16-star)
  - The F3b TAS proxy used a 16-star TAS for comparison briefly — corrected to 120-star
  - Paper simply lists SM64 as "any%" in §2.1 without noting the category is actually 120-Star on speedrun.com

---

## Missing Content / Analyses Not in Paper

- **F3b+ Bannister Effect event study (post-submission, not going in paper)**
  - 42 TAS release events analyzed; 19/42 (45 %) followed by ≥1 WR improvement within 180 days
  - Half-Life 2 (2016 SourceRuns TAS) is the only clear Bannister case: velocity ratio 1.35×
  - Mean improvement following a TAS: 48.6 s; velocity ratio computable for only 5 events
  - Metric: `velocity_ratio = vel_post_s_per_year / vel_pre_s_per_year`
  - Not going in paper per group decision.

- **HL2 "surpassed" case not discussed (152 % pct_closed)**
  - The current human HL2 WR (≈2190 s) is faster than the 2014 TAS reference (≈4494 s from `tas_known.json`)
  - `pct_closed > 100 %` because the human route has evolved past what was TAS-optimal in 2014
  - The paper uses a model asymptote (1874.7 s floor), not this real TAS time, so there is no contradiction — but it is a notable omission in the F3b discussion

- **F3a segment-size threshold not stated**
  - Paper says "11 von 17 Spielen hatten unzureichende Segmentgröße" but never defines the minimum segment size required for velocity calculation
  - Code requires at least 2 WRs in both pre- and post-breakthrough segments; the minimum span must be > 0 days
  - Should be stated in §2.2

- **Spearman ρ significance thresholds for F3a not fully described**
  - Paper says ρ < −0.2 = abnehmend, ρ > 0.2 = zunehmend — these are the interpretation thresholds
  - The p-value cutoff for the ∗ and ∗∗∗ annotations in Table 3.4 is not stated in the methodology text (only implied by the table footnote)

- **Jahrzehnt breakdown for F3c not cross-referenced with Kaplan-Meier**
  - §3.3 reports decade means (665.8 / 172.7 / 82.4 / 95.2 days) as plain averages
  - These are raw means, not Kaplan-Meier medians — the method section says KM is used but the decade figures are arithmetic means
  - Should clarify which method was used for the decade comparison, or run KM per decade

- **No per-game F1 table for annual rate**
  - Table 3.1 shows annual rate per game but the Kruskal-Wallis test that finds no genre significance (H=6.24, p=0.284) uses these rates — the test inputs are per-game rates within each genre. With only 1–3 games per genre the test is severely underpowered (N=17, k=7). This limitation is not acknowledged.

- **Pac-Man TAS comparison is category-mismatched**
  - Pac-Man's TAS data is the NES Tengen port (~12 min); the human any% WR is arcade (~30 s)
  - This makes `pct_closed` meaningless for Pac-Man in the TAS pipeline
  - Not in the paper, but if F3b real-TAS results are ever added, Pac-Man must be filtered or flagged

---

## Minor / Polish

- **Paper references power_law as "Potenzgesetz"** — consistent, no issue
- **F3a Donkey Konga breakthrough date**: paper says "Dezember 2024" — correct per code/data
- **F3b Pokemon Red/Blue**: paper reports Floor 6004.4 s, Gap 215.6 s — these come from the asymptote proxy. Pokemon's TAS uses save-glitch/warp-glitch routes (category mismatch with human glitchless any%); the proxy result may coincidentally look valid but the interpretation should be caveated
- **LOWESS not in Table 3.2** — see "Text vs. Table" section above
- **References**: Wooten 2022 (Bannister Effect, *POM*, DOI 10.1111/poms.13707) and the event-study methodology sources (Campbell & Stanley 1963; MacKinlay 1997) were added to `Dataset.md` but are not in the paper's bibliography — irrelevant if F3b+ is dropped
