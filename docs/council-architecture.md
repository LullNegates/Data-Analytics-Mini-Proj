# Council of Agents — Hallucination-Resistant Q1/Q2/Q3 Inference

## Context

The current `Model/questions/{q1,q2,q3}.py` runners each call **phi4-mini** once and parse the JSON. Because phi4-mini is 3.8B params, a single pass produces verifiable hallucinations even with the pre-aggregated context built in the previous session:

- `output/q1_analysis.json` claims "Minecraft: Java Edition hat eine vollständige Reduktion von 100%" — this is fabricated; the actual `pct_reduction` in `q1_reduction.csv` is far lower.
- Only 4 of 7 genres appear in `genre_patterns` (Sandbox, RPGs, FPS, Arcade) — Action-Adventure, Platformer, Puzzle are silently dropped.
- F6 is filler ("Unzureichende Daten") with no concrete numbers.

The literature suggests the right fix is **multi-agent debate + aggregation**:

- **Du et al., MIT, 2023** — *Improving Factuality and Reasoning in Language Models through Multiagent Debate* (arXiv:2305.14325, ICML 2024). Multiple LLM instances generate independently, then revise after seeing peers, then converge. Reduces hallucinations and improves factuality 10–15% on factual reasoning benchmarks.
- **Together AI, 2024** — *Mixture-of-Agents Enhances LLM Capabilities* (arXiv:2406.04692). Layered: N proposers → 1 aggregator. Empirical finding ("collaborativeness"): even weaker models produce stronger outputs when given peer outputs as auxiliary input. +7.6 pts AlpacaEval over GPT-4o using only OSS models.

This plan implements both ideas, scoped to the FHDW Data Analytics mini-project, runnable on the user's RTX A2000 8 GB.

## Goal

Replace the single-model Q1/Q2/Q3 inference with a **council of 3 small models** running 2 rounds of debate, plus a **manager** that synthesises and **deterministically fact-checks** every numeric claim against the source data. Final outputs land in `Model/output/council/` with the same JSON schema as the existing single-agent outputs, so `q1_council.json` can be diffed against `q1_analysis.json` to demonstrate the improvement in the Ausarbeitung.

## Architecture

### What happens to `questions/`

The single-agent runners (`q1.py`, `q2.py`, `q3.py`) and `registry.py` become **fully redundant** once the council ships — the council does everything they do, better. They are deleted. Their irreplaceable parts move:

- **`questions/context_builder.py`** → moves to `council/context_builder.py`. Pure utility, no LLM dependency, used unchanged.
- **`SYSTEM_PROMPT` schema constants in each q*.py** → migrated into `council/personas.py` as the per-question schema contract that every agent must satisfy.
- **`_call_ollama_streaming` / `_parse_json` helpers** → consolidated in `council/ollama_client.py` (extracted before deletion).

The `questions/` folder is removed entirely. `Model/main.py` loses the per-question menu and offers only the council entry. Existing `Model/output/q{1,2,3}_analysis.json` files are kept untouched — they are the baseline that the new `q{1,2,3}_council.json` is diffed against in the Ausarbeitung.

### Folder layout (after)

```
Model/
├── config.py                    # extended (see below)
├── main.py                      # menu now only routes into council
├── output/
│   ├── q1_analysis.json         # kept — single-agent baseline for comparison
│   ├── q2_analysis.json
│   ├── q3_analysis.json
│   └── council/                 # new — council outputs
│       ├── q1_council.json
│       ├── q1_transcript.json
│       └── ...
└── council/
    ├── __init__.py
    ├── README.md                # Architecture explainer + paper citations
    ├── runner.py                # Entry: `python -m Model.council` (interactive Q1/Q2/Q3)
    ├── orchestrator.py          # Round 1 → Round 2 → Manager → Fact-check loop
    ├── personas.py              # 3 persona system prompts + per-question schema contracts
    ├── agents.py                # CouncilAgent: model_name + persona → generate(...)
    ├── manager.py               # ManagerAgent: synthesize() + revise(report)
    ├── fact_checker.py          # extract_numbers() + build_source_index() + verify()
    ├── transcripts.py           # Pretty terminal output + JSON transcript writer
    ├── ollama_client.py         # Streaming Ollama call (moved from q*.py)
    └── context_builder.py       # moved from questions/context_builder.py
```

(`questions/` no longer exists.)

### Council members (different models for true diversity)

| Role         | Model         | Persona                | Why                                                                |
|--------------|---------------|------------------------|--------------------------------------------------------------------|
| Statistician | `qwen2.5:3b`  | Stats-focused          | Strong on math/numbers; emphasises p-values, AIC, significance     |
| Domain       | `llama3.2:3b` | Speedrun-domain expert | Good narrative reasoning; emphasises genre/game-specific patterns  |
| Skeptic      | `gemma2:2b`   | Devil's advocate       | Smaller but trained differently; flags weak claims, small-N issues |
| Manager      | `phi4-mini`   | Synthesiser + verifier | Strongest instruction-following; handles structured-output revision |

Total disk: ~9.5 GB (phi4-mini already installed; pulls ~5.5 GB new). VRAM is fine — Ollama evicts LRU on demand. `setup.ps1` will be extended to pull the new models.

### Orchestrator flow (per question)

```
1.  context = build_q{N}_context(...)               # reuse existing builder verbatim
2.  R1 = {}
    for agent in council:                           # sequential — Ollama swaps models
        print_header(agent)                         # e.g. "── [Statistician / qwen2.5:3b] Round 1 ──"
        R1[agent] = agent.generate(context)         # streamed to terminal
3.  R2 = {}
    for agent in council:
        print_header(agent + " — Round 2")
        R2[agent] = agent.generate(context, peer_outputs=R1)
4.  draft = manager.synthesize(context, R2)         # phi4-mini with all 3 r2 outputs
5.  for attempt in range(MAX_REVISIONS=2):
        report = fact_checker.verify(draft, source_data)
        if report.all_verified: break
        draft = manager.revise(draft, report)       # focused fix-it prompt
6.  save(draft → q{N}_council.json)
    save(transcript → q{N}_transcript.json)
    print_diff_summary(draft, q{N}_analysis.json)   # side-by-side comparison
```

### Round-2 user-prompt template (key debate mechanism)

```
{original_context}

---

Du hast in Runde 1 folgende Antwort gegeben:
{your_round_1_output}

Zwei Kollegen haben unabhängig diese Antworten gegeben:

== Kollege A (Statistiker) ==
{peer_a_output}

== Kollege B (Skeptiker) ==
{peer_b_output}

Aufgabe: Lies die Antworten der Kollegen kritisch. Wo widersprechen sie deiner?
Wo haben sie Recht? Aktualisiere deine Antwort entsprechend. Behalte nur Aussagen,
die du in den Quelldaten verifizieren kannst. Antworte erneut im selben JSON-Schema.
```

### Manager synthesis prompt (final aggregation)

```
{original_context}

---

Drei Analysten haben unabhängig folgende finale Antworten gegeben:
{r2_statistician}
{r2_domain}
{r2_skeptic}

Aufgabe: Synthetisiere die beste Gesamtantwort. Bevorzuge Aussagen, die von ≥2
Analysten gestützt werden. Verwerfe Behauptungen, deren Zahlen nicht mit den
Quelldaten übereinstimmen. Behalte das Original-JSON-Schema bei.
```

## Fact-checker (deterministic, Python-only)

`fact_checker.py` does no LLM calls. It:

1. **Builds source index** per question:
   - Every cell in `data/clean/q{N}_*.csv` (game, genre, numeric values)
   - Every leaf value in `data/analysis/q{N}_stats.json` (recursive walk)
   - Stored as `{value: [paths_where_it_appears]}` with rounding tolerance buckets (±0.5 %, ±1.0).
2. **Extracts numbers from manager draft**: regex over the JSON's string fields for percentages, decimals, integer-with-units, dates. Every `findings[*].text`, every numeric leaf in `genre_patterns`/`saturation_by_game`/`genre_survival`/`summary`.
3. **Verifies each extracted number**: lookup in source index with tolerance. Returns a `VerificationReport(verified=[], unverified=[...with quotes...], suspicious=[...numbers that match but in suspicious context...])`.
4. **On failure**: orchestrator passes the report to `manager.revise()` with the unverified quotes. Manager has 2 attempts; if still failing, write the draft anyway with a `fact_check_warnings` field listing the unresolved issues — never silently fail.

### Coverage caveat

Pure regex won't catch every semantic error (e.g., "Minecraft is Sandbox" is a category claim, not a number). The verifier handles **numeric drift** — the most common phi4-mini failure mode observed in `q1_analysis.json`. Categorical claims rely on the council itself filtering them out via debate.

## Terminal output

Every agent's output streams live to the terminal with a coloured header:

```
══════════════════════════════════════════════════════════════════
  [1/3] Statistician  qwen2.5:3b  · Round 1
──────────────────────────────────────────────────────────────────
{ "findings": [...
```

Headers use ANSI colours (cyan = round 1, yellow = round 2, magenta = manager, red = fact-check failure). After all rounds, a final block prints the verification summary and the diff-vs-single-agent.

## Output

```
Model/output/council/
├── q1_council.json            # final synthesised JSON (same schema as q1_analysis.json)
├── q1_transcript.json         # full debate: r1 outputs, r2 outputs, manager drafts, fact-check
├── q2_council.json
├── q2_transcript.json
├── q3_council.json
└── q3_transcript.json
```

`q*_council.json` is structurally identical to `q*_analysis.json` so a simple `diff` shows the improvement for the Ausarbeitung.

## Reuse map

- `questions/context_builder.py` → **moved** to `council/context_builder.py`, used as-is for all 3 questions
- System-prompt schemas in `q1.py`/`q2.py`/`q3.py` → **migrated** into `council/personas.py` as the schema contract each agent must produce; the persona text prepends a perspective preamble
- `_call_ollama_streaming` and `_parse_json` from `q*.py` → **migrated** to `council/ollama_client.py` (DRY) before the source files are deleted
- `Model/config.py` → **extended** with `COUNCIL_MODELS`, `MANAGER_MODEL`, `COUNCIL_OUTPUT_DIR`; existing constants untouched

## Critical files modified / created / deleted

| File                                       | Change                                                                       |
|--------------------------------------------|------------------------------------------------------------------------------|
| `Model/council/*` (11 files)               | **New** — council package (incl. moved `context_builder.py`)                 |
| `Model/questions/q1.py`, `q2.py`, `q3.py`  | **Deleted** — superseded by council                                          |
| `Model/questions/registry.py`              | **Deleted** — no longer needed                                               |
| `Model/questions/context_builder.py`       | **Moved** to `Model/council/context_builder.py`                              |
| `Model/questions/__init__.py`              | **Deleted** along with the folder                                            |
| `Model/config.py`                          | + `COUNCIL_MODELS`, `MANAGER_MODEL`, `COUNCIL_OUTPUT_DIR`                    |
| `Model/main.py`                            | Replace per-question menu with single council entry; drop `from questions.registry import ...` |
| `Model/output/q{1,2,3}_analysis.json`      | **Kept** — single-agent baseline for the Ausarbeitung diff                   |
| `setup.ps1`                                | Add `ollama pull qwen2.5:3b`, `ollama pull llama3.2:3b`, `ollama pull gemma2:2b` |
| `docs/council-architecture.md`             | **This file**                                                                |
| `requirements.txt`                         | No change — already has `requests`                                           |

## Implementation steps (in order)

1. **Save this plan to `docs/council-architecture.md`** (this file).
2. Pull the 3 new Ollama models (`qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`) and smoke-test each.
3. **Migrate, then delete** in this order (so the tree is never broken):
   1. Create `council/ollama_client.py` from the helpers in `q*.py`.
   2. Create `council/personas.py`; copy each `SYSTEM_PROMPT` from `q*.py` into a `Q{N}_SCHEMA_CONTRACT` constant; add the 3 persona preambles.
   3. Move `questions/context_builder.py` → `council/context_builder.py`. No callers exist outside `q*.py` which we are about to delete.
   4. Delete `questions/q1.py`, `q2.py`, `q3.py`, `registry.py`, `__init__.py`, and the empty folder.
   5. Update `Model/main.py`: drop `from questions.registry import QUESTION_REGISTRY` and the per-question menu; route directly into `council.runner.main()`.
4. Build `council/agents.py` — `CouncilAgent` class with `generate(context, peer_outputs=None)`; round-2 path injects peer outputs into the user prompt.
5. Build `council/fact_checker.py` — source-index builder + numeric extractor + verifier. Unit-test against `q1_analysis.json`'s Minecraft "100 %" hallucination before wiring it into the manager loop.
6. Build `council/manager.py` — `synthesize()` + `revise(report)` methods.
7. Build `council/transcripts.py` — coloured terminal print + JSON transcript writer.
8. Build `council/orchestrator.py` — round-1 → round-2 → manager → fact-check loop.
9. Build `council/runner.py` — interactive Q1/Q2/Q3 picker, wired from `Model/main.py`.
10. Run end-to-end on Q1; verify `q1_council.json` differs from `q1_analysis.json` and that the Minecraft "100 %" claim is gone.
11. Run on Q2 and Q3.
12. Append the diff summary to this file.
13. Drop a fleeting note about the result so `/save` consolidates it.

## Verification plan

After implementation:

- **Smoke test each model**: `curl http://localhost:11434/api/chat -d '{"model":"<name>","messages":[{"role":"user","content":"Hi"}]}'` for all 4 models. All must return non-empty.
- **Fact-checker unit test**: feed it the existing `q1_analysis.json` (which contains the Minecraft "100 %" hallucination); verifier must flag that claim as unverified. If it doesn't, the verifier is broken before we plug it into the manager.
- **End-to-end Q1**: `python main.py` → choose council → expect 7 LLM calls (3+3+1), 1–2 fact-check revisions. Total time budget ~5 min on the A2000.
- **Output diff**: `q1_council.json` vs `q1_analysis.json` — council version should have all 7 genres in `genre_patterns`, no "Minecraft 100 %" claim, and concrete numbers in every finding.
- **Q2 sanity check**: `saturation_by_game` must contain all 17 games. `best_model` values must match `q2_stats.json` ground truth.
- **Q3 sanity check**: `decade_stats` (not `decade_comparison`) referenced correctly; KM medians match `q3_stats.json`.

## Out of scope (explicit non-goals)

- No semantic LLM-as-judge fact-check (deterministic-only).
- No web RAG, no LLMLingua, no FAISS — pre-aggregated stats remain the attention layer.
- No async parallel model calls — Ollama serialises anyway, and small VRAM forces sequential loads.
- No persona auto-tuning — the 3 personas are hand-written and frozen for reproducibility in the Ausarbeitung.

## Run summary

(Filled in after the first end-to-end run — diff vs single-agent, fact-check pass rate, time-to-output.)
