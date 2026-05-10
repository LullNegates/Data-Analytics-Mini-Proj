# Council of Agents

Multi-agent debate + deterministic fact-check for Q1/Q2/Q3 inference.
Replaces the single-phi4-mini runners that previously lived in `Model/questions/`.

Full design rationale: `docs/council-architecture.md`. This file is the operator's reference.

---

## How it runs

```
python Model/main.py            # interactive Q1 / Q2 / Q3 picker
python Model/main.py q1         # run one question directly
python Model/main.py all        # run all three sequentially
```

For each question:

1. **Round 1** — three council members generate independently from the pre-aggregated context:
   - Statistician (`phi4-mini`) — p-values, AIC, genre means, distribution shape; highest math scores in the lineup
   - Domain expert (`llama3.2:3b`) — speedrun-mechanic explanations, genre-level context; best commonsense (HellaSwag 77.2 %)
   - Skeptic (`gemma3:4b`) — small-N flags, confounders, data-quality challenges; 4× stronger than the original gemma2:2b

2. **Round 2** — each member reads the other two's Round 1 outputs and revises critically (Du et al. 2023 protocol).

3. **Manager** (`qwen3:4b`, thinking ON) — synthesises the three Round 2 outputs into a single JSON.
   The manager's chain-of-thought reasoning streams to the terminal in dim text so you can see exactly which claims it trusted and why. Only the final JSON answer is saved; the thinking trace is not included in the output file.

4. **Fact-check** — deterministic Python verifier (no LLM). Every number in the manager's draft is looked up in an index built from `Dataset/data/clean/q{N}_*.csv` + `Dataset/data/analysis/q{N}_stats.json` with rounding tolerance. Unverified numbers trigger a targeted revision request to the manager (max 2 attempts). If still unresolved, the output is saved with a `fact_check_warnings` field.

5. **Output** — final JSON to `Model/output/council/q{N}_council.json` (same schema as the legacy `q{N}_analysis.json` for direct diffing); full debate transcript to `q{N}_transcript.json`.

---

## Model lineup

| Role | Model | Company | Key benchmarks | Why this role |
|---|---|---|---|---|
| **Manager** | `qwen3:4b` | Alibaba | MMLU ~70 %, thinking mode | Reasoning model — visible CoT resolves inter-agent conflicts; `num_predict = 16 000` |
| **Statistician** | `phi4-mini` | Microsoft | GSM8K 88.6 %, MATH 64.0 %, BBH 70.4 % | Highest math scores in the lineup; no thinking overhead — clean JSON every time |
| **Domain Expert** | `llama3.2:3b` | Meta | HellaSwag 77.2 % | Best commonsense / world-knowledge in tier for contextual interpretation |
| **Skeptic** | `gemma3:4b` | Google | GSM8K ~55 % (vs gemma2:2b's 23.9 %) | Flags small-N, confounders, data-quality issues; needs enough math to be credible |

Four different companies = four different base architectures. Per the Mixture-of-Agents paper, diversity between base models produces real disagreement in Round 2, not stylistic variation.

**Manager swap rationale** — The manager's job is *judgment under conflict*: "The Statistician said right-skewed, the Domain expert said left-skewed — which is correct?" A reasoning model can work through that explicitly. phi4-mini (previous manager) has no thinking mode, making its synthesis a silent black box. qwen3:4b's thinking trace is now visible on terminal during the synthesis step, which is also useful to show during the Präsentation.

**Statistician swap rationale** — phi4-mini has the highest raw math scores (GSM8K 88.6 %, MATH 64.0 %, BBH 70.4 %), and no thinking overhead means it never exhausts its token budget on CoT before writing the JSON response — a bug that plagued qwen3 when it was the Statistician in earlier runs.

---

## Files

| File | Role |
|---|---|
| `runner.py` | Interactive picker; entry point called from `Model/main.py` |
| `orchestrator.py` | Round 1 → Round 2 → Manager → Fact-check loop |
| `agents.py` | `CouncilAgent` — one persona × one Ollama model; `num_predict = 8 000` |
| `manager.py` | `ManagerAgent.synthesize()` + `revise(report)`; `num_predict = 16 000`, thinking ON |
| `personas.py` | Three persona preambles + per-question JSON schema contracts |
| `fact_checker.py` | Deterministic numeric verifier — no LLM calls |
| `ollama_client.py` | Streaming Ollama client; prints `message.thinking` tokens dimmed, returns `message.content` only |
| `context_builder.py` | Per-question context assembly (moved from the deleted `questions/`) |
| `transcripts.py` | Coloured terminal output + JSON transcript writer |

---

## Q1 output comparison

Three runs on the same Q1 data, verified claim-by-claim against `q1_reduction.csv` and `q1_stats.json`.

### Run setup

| Version | Statistician | Domain | Skeptic | Manager | Date |
|---|---|---|---|---|---|
| Single-agent | — | — | — | phi4-mini | 2026-05-07 02:18 |
| Council v1 | qwen2.5:3b | llama3.2:3b | gemma2:2b | phi4-mini | 2026-05-07 03:36 |
| Council v2 | qwen3:4b *(buggy — thinking exhausted tokens)* | llama3.2:3b | gemma3:4b | phi4-mini | 2026-05-07 04:09 |
| Council v3 | qwen3:4b *(think=False fixed)* | llama3.2:3b | gemma3:4b | phi4-mini | 2026-05-07 14:25 |
| **Council v4 (current)** | **phi4-mini** | **llama3.2:3b** | **gemma3:4b** | **qwen3:4b** *(think=True)* | **2026-05-07 16:21** |

### Ground truth

| Fact | Value |
|---|---|
| Minecraft pct reduction | **99.49 %** (was 100.00 % from a 0.001 s bogus WR row — fixed in `Dataset/clean.py`) |
| Lowest annual rate — game | **Super Mario Bros. 0.40 %** |
| Lowest annual rate — genre | **RPG 1.95 %** |
| Highest annual rate — genre | **Action-Adventure 10.56 %** (Zelda OoT 15.85 %, Hollow Knight 12.77 %) |
| Kruskal-Wallis p (annual rate) | **0.284** — not significant |

### Claim-by-claim verdict

| Dimension | Single-agent | Council v1 | Council v3 | **Council v4** |
|---|---|---|---|---|
| **Findings count** | 6 | 7 | 16 | **4 (genre-level)** |
| **Genre coverage** | 4 / 7 | 4 / 7 | ✅ 7 / 7 | ✅ **7 / 7** |
| **Minecraft pct (99.49 %)** | ❌ 100 % (broken data) | ✅ 99.49 % | ✅ 99.49 %, annual 8.93 % | ✅ **99.49 %, 8.93 %** |
| **Lowest annual game (SMB 0.40 %)** | ❌ not stated | ✅ SMB 0.401 % | ⚠️ F7 names SM64 (wrong); F11 corrects | ❌ not stated |
| **Lowest annual genre (RPG 1.95 %)** | ✅ 1.9507 % | ❌ missing | ✅ genre pattern | ✅ **1.95 % in genre pattern** |
| **Highest annual genre (Action-Adv 10.56 %)** | ❌ not found | ❌ not found | ❌ pattern present, not named | ✅ **F4: explicit, 10.56 %** |
| **Kruskal-Wallis p = 0.284** | ✅ | ❌ missing | ✅ cited | ✅ **cited in summary** |
| **Talos Principle 12.79 %** | ❌ | ❌ | ✅ with small-N caveat | ❌ aggregated into Puzzle avg |
| **Game-level specifics (FF7, Quake…)** | ❌ | ❌ | ✅ F5–F11 correct values | ❌ genre-level only |
| **Duplicate findings** | 0 | 4 (F4 = F5 = F6 = F7) | 0 | **0** |
| **Filler / weak findings** | 1 | 0 | 1 | **0** |
| **Off-topic metrics** | 2 | 0 | 1 | **0** |
| **Factual errors** | 1 major | 0 | 1 minor | **0** |
| **Statistician output** | full | full | ✅ full | ✅ **full (5 448 chars)** |
| **Fact-check result** | n/a | n/a | ~13 / 16 | ✅ **18 / 18, 0 revisions** |

### Summary

| | Single-agent | Council v1 | Council v3 | **Council v4** |
|---|---|---|---|---|
| Accuracy | 2 / 6 | 3 / 7 | ~13 / 16 | ✅ **4 / 4 (100 %)** |
| Structure quality | Good | Poor (4 dupes) | Good | ✅ **Perfect** |
| On-topic focus | Poor | Good | Good | ✅ **Good** |
| Genre coverage | 4 / 7 | 4 / 7 | ✅ 7 / 7 | ✅ **7 / 7** |
| Fact-check | n/a | n/a | ~13 / 16 | ✅ **18 / 18, 0 revisions** |

---

## Why genre-level analysis is the right focus

The research questions for this project are framed at the genre level — "do certain genres improve faster than others?" — not at the level of individual games. Council v3 produced 16 findings by citing per-game values (FF7 2.86 %, Quake 1.76 %, Super Metroid 3.07 %, etc.), but those individual data points are already visible in the raw CSV. Repeating them as LLM findings adds no interpretive value and inflates the output with noise that obscures the actual conclusions.

Genre-level aggregates are what the Ausarbeitung needs:

- **Generalisation over individual games.** A single game's annual rate is heavily influenced by its community size, age, and whether a game-breaking glitch was found. Genre means smooth out those one-off effects and reveal structural patterns — e.g. Action-Adventure's 10.56 % average is driven by two independent games (Zelda OoT and Hollow Knight), making it a more robust claim than any single game value.
- **Directly answers the research question.** Q1 asks which *category* improves fastest, not which specific game. Genre-level findings map directly to the stated hypothesis.
- **Statistical validity.** The Kruskal-Wallis test (p = 0.284) was run across genres, not across individual games. Any claim about genre differences must reference the genre aggregates to be consistent with the statistical test.
- **Presentation clarity.** In a 20-minute Präsentation, seven genre findings are digestible. Sixteen per-game findings are not.

Council v4's concise output (4 findings, 7 genre patterns) is therefore the intended design, not a regression from v3's verbosity.

---

## Coverage caveats

The fact-checker catches **numeric drift** only — fabricated values, wrong percentages, mistyped counts. It does **not** catch categorical errors ("Minecraft is RPG") or interpretive errors ("X causes Y"). Those are filtered by the council debate itself.

The Minecraft data-quality fix (bogus 0.001 s WR row → `pct_reduction=100 %`) is patched in `Dataset/clean.py:sanitize_wr_progressions`. Re-run `python Dataset/clean.py` then `python Dataset/analysis/run.py` (from PowerShell, needs the `.venv`) after pulling fresh data from the API.

---

## Cost

Per question: 3 council × 2 rounds + 1 manager + up to 2 revisions = **6–8 Ollama calls**.
Expect **5–8 minutes per question** on an RTX A2000 8 GB — slightly longer than before because the manager (qwen3:4b with thinking) takes more time than the old phi4-mini manager.

---

## References

- Du et al., *Improving Factuality and Reasoning in Language Models through Multiagent Debate*, arXiv:2305.14325 (ICML 2024)
- Wang et al., *Mixture-of-Agents Enhances Large Language Model Capabilities*, arXiv:2406.04692
