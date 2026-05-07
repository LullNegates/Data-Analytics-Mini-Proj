# Model Context Strategy — Smart Input for phi4-mini

**Project:** FHDW Data Analytics Mini-Project — Speedrunning World Records  
**Date:** 2026-05-06  
**Status:** Approved — ready to implement

---

## Problem

The LLM (phi4-mini via Ollama) currently only receives `q1_reduction.csv` as input for Q1, and Q2/Q3 have no runner files at all. Three issues compound this:

1. **Ollama defaults to 4,096 tokens** — phi4-mini supports 128K, but without `num_ctx` in the request options the model is cut off at 4K regardless of how much data we send.
2. **Raw CSVs are high-noise, low-signal** — `all_runs.csv` is 1.3M tokens, `q3_lifetimes.csv` is ~18K tokens row-by-row. The model gains nothing from seeing every individual run — it needs aggregated evidence.
3. **Pre-computed analysis JSONs are not being passed to the LLM** — `q1_stats.json`, `q2_stats.json`, `q3_stats.json` already contain the computed statistics (AIC rankings, KM survival curves, structural breaks). These are exactly the "compressed" representation the model should reason over.

---

## Research Findings

### 1. Ollama `num_ctx` — Most Critical Fix

phi4-mini's model card specifies 128K context. Ollama defaults to **4,096 tokens** unless overridden via `"options": {"num_ctx": N}` in the request payload. Without this, any data beyond 4K is silently truncated. All current runs are likely happening with severely clipped context.

**Fix:** Add `"num_ctx": 16384` to the `options` dict in `_call_ollama_streaming`. Budget can be tuned per question.

Sources: [phi4-mini on Ollama](https://ollama.com/library/phi4-mini), [Ollama context length docs](https://docs.ollama.com/context-length)

---

### 2. TableRAG — Schema-first + Cell Retrieval Pattern

TableRAG (NeurIPS 2024) handles million-token tables by splitting retrieval into two stages:
- **Schema retrieval**: give the model column names and descriptions first, so it knows what fields exist
- **Cell retrieval**: selectively retrieve only the rows/values relevant to the question

**Applied to our project:** The `Dataset.md` serves as the schema layer (column semantics per CSV). The stats JSONs serve as the cell layer (pre-indexed, already compressed to per-game aggregates). We do not need a live RAG index — our pipeline already pre-computes the relevant aggregates.

Source: [TableRAG (arxiv 2410.04739)](https://arxiv.org/html/2410.04739v1)

---

### 3. LLMLingua / Prompt Compression

Microsoft's LLMLingua uses a small model (GPT-2 or LLaMA-7B) to score token perplexity and prune low-entropy tokens from prompts — up to 20x compression with minimal loss. LLMLingua-2 is faster and handles out-of-domain data better.

**Decision: Not used here.** Requires a separate model running alongside the inference model — too heavyweight for a local offline setup. Our pre-aggregation strategy (see below) achieves the same goal without a second model.

Source: [LLMLingua (Microsoft)](https://llmlingua.com/llmlingua.html), [LLMLingua GitHub](https://github.com/microsoft/LLMLingua)

---

### 4. Pre-aggregation as Attention Proxy

The core insight from contextual compression research: **redundant rows share the same statistical signal**. Feeding 877 individual WR records to the model is equivalent to asking it to re-derive the statistics your analysis pipeline already computed. The stats JSONs *are* the attention output — they capture what matters (best-fit model, AIC delta, structural break date, KM median, survival probability) and discard what does not (individual run timestamps, intermediate WR indices).

This is the "attention mask" you described — instead of training a neural attention layer over the raw data, the Python analysis pipeline acts as the attention mechanism, and its output (stats JSONs) is the attended summary.

**Applied rule:**
- Never pass raw per-run rows when a pre-computed aggregate exists.
- Pass raw data only when no aggregate covers it (e.g. the 17-row `q1_reduction.csv` — small enough that the LLM can cross-check values).

Source: [Contextual Compression in RAG — Survey](https://arxiv.org/html/2409.13385v1)

---

### 5. JSON vs CSV for Structured Data

Research on tabular LLM prompting confirms that **JSON outperforms CSV for structured/analytical queries** (fact-checking, QA, reasoning over schema). CSV is better for simple lookups.

**Applied rule:** Stats JSONs are passed as-is. For the compact per-game CSV summaries, format them as a markdown table (LLMs parse aligned columns better than comma-delimited strings).

Source: [Three Paths to Table Understanding with LLMs (Medium)](https://medium.com/@kate.ruksha/three-paths-to-table-understanding-with-llms-dc0648be4192)

---

### 6. Hallucination and Small Models

Research (2025) confirms that small models hallucinate more when given unstructured or irrelevant context. Structured prompting (system + user roles, explicit schema) and chain-of-thought instructions significantly reduce hallucinations. The system prompt should explicitly tell the model *what the data represents* and *what it should not invent*.

**Applied rule:** System prompt includes a one-line description of each data section. The "Regeln" block explicitly bans inventing values not in the data.

Source: [Hallucination Mitigation Review (MDPI 2025)](https://www.mdpi.com/2227-7390/13/5/856)

---

## Token Budget Per Question

phi4-mini supports 128K context. We set `num_ctx = 16384` (16K) as the safe working budget — well within the model's capability, avoids memory pressure on local hardware.

| Layer | Q1 | Q2 | Q3 |
|---|---|---|---|
| System prompt | ~400 | ~400 | ~400 |
| Dataset.md excerpt (Q section + CSV schema) | ~600 | ~700 | ~700 |
| Stats JSON | 2,400 (`q1_stats`) | 9,800 (`q2_stats`) | 1,400 (`q3_stats`) |
| CSV table / per-game summary | 532 (full `q1_reduction.csv`) | ~350 (per-game summary) | ~350 (per-game summary) |
| User prompt wrapper text | ~200 | ~200 | ~200 |
| **Total estimate** | **~4,100** | **~11,450** | **~3,050** |
| **Budget used** | **25%** | **70%** | **19%** |

`all_runs.csv` (~1.3M tokens) is **never** included.  
`wr_progression.csv` (~11.7K tokens) is redundant — covered by `q2_saturation.csv` data and `q2_stats.json`.

### Q2 Compression Note

`q2_stats.json` at 9.8K is the largest input. If token pressure becomes an issue, the context builder can compress it by emitting only the winning model + AIC delta from the second-best, rather than all 5 model fits per game. This would reduce Q2 input to ~5K. Default: include full stats for maximum interpretability.

---

## Architecture: `context_builder.py`

A new module `Model/questions/context_builder.py` handles all data assembly. Each Q module calls its builder function and receives ready-to-use strings.

```
context_builder.py
├── dataset_excerpt(dataset_path, q_num)     → str   (Dataset.md section)
├── load_stats_json(analysis_dir, q_num)     → str   (JSON as formatted string)
├── build_q1_context(data_dir, analysis_dir) → (table_str, stats_str, schema_str, tok_estimate)
├── build_q2_context(data_dir, analysis_dir) → (summary_str, stats_str, schema_str, tok_estimate)
└── build_q3_context(data_dir, analysis_dir) → (summary_str, stats_str, schema_str, tok_estimate)
```

**`dataset_excerpt`**: Parses Dataset.md by section header (`**Q1 —`, `### q1_reduction.csv`, etc.) and returns only the relevant blocks. Avoids hardcoding line numbers — uses regex to split on `###` and `**Q` markers.

**Per-game CSV summaries (Q2/Q3)**: Instead of passing 877 rows, aggregate to one row per game with key metrics:

- Q2 summary: `game | genre | n_wrs | span_days | first_time | last_time | pct_reduction`
- Q3 summary: `game | genre | n_wrs | n_standing | median_duration_days | pct_broken`

17 rows × 6-7 columns ≈ 300-350 tokens.

**Token guard**: Each builder prints an estimated token count (bytes / 4). If the estimate exceeds 13,000 tokens, it warns before sending.

---

## Implementation Steps

### Step 1 — Critical: Fix `num_ctx` in `config.py`
Add `NUM_CTX = 16384` and pass it in the Ollama options dict. Without this, everything else is moot.

### Step 2 — Create `questions/context_builder.py`
Implement all builder functions per the architecture above.

### Step 3 — Update `questions/q1.py`
Replace the manual `_build_table` + hardcoded user prompt with `build_q1_context()`. Add Dataset.md excerpt + q1_stats.json to the user message.

### Step 4 — Create `questions/q2.py`
New runner for Q2 — Sättigungs-Analyse. Uses `build_q2_context()`. System prompt instructs the model to interpret AIC rankings, structural breaks, and deceleration patterns.

### Step 5 — Create `questions/q3.py`
New runner for Q3 — WR-Lebensdauer / Kaplan-Meier. Uses `build_q3_context()`. System prompt instructs the model to reason about survival probabilities, genre differences, and right-censoring.

### Step 6 — Update `config.py` and `registry.py`
- `config.py`: add `ANALYSIS_DIR`, `DATASET_MD`, `NUM_CTX`
- `registry.py`: register Q2 and Q3

---

## What is NOT Done (Out of Scope)

| Technique | Why skipped |
|---|---|
| LLMLingua token pruning | Requires second model; local setup overhead not justified |
| Live RAG index (FAISS/ChromaDB) | Data is static and small; index adds complexity for no gain |
| Fine-tuning phi4-mini on speedrun data | Out of scope for a school project; data volume too small |
| Passing `all_runs.csv` | 1.3M tokens — never. The analysis pipeline is the attention layer over this file. |
| Passing `wr_progression.csv` raw | 11.7K tokens; fully redundant with `q2_saturation.csv` + `q2_stats.json` |

---

## Open Issues

- Visualization color overlap bug (Q1 bar chart, run time distribution, Q3 KM median chart) — tracked in `Issues/data-analytics/visualisation-colour-overlap.md`
- Verify end-to-end pipeline with new context builder — tracked in `Issues/data-analytics/verify-analysis-pipeline.md`
