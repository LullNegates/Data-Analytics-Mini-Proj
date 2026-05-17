"""Council orchestrator: round 1 → round 2 → manager → fact-check loop.

The orchestrator is question-agnostic. It receives:
  - a question id ("q1", "q2", "q3")
  - a pre-built ``context`` string (from ``context_builder.build_q{N}_context``)
  - the source-data paths used for fact-checking

and produces:
  - the final synthesised JSON (saved to ``council_output_dir/q{N}_council.json``)
  - a full transcript of every round (saved to ``q{N}_transcript.json``)

Token streams from each Ollama call hit the terminal live, prefixed by a
coloured header from ``transcripts``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import requests

from council import transcripts as tr
from council.agents import CouncilAgent
from council.context_builder import (build_q1_context, build_q2_context,
                                     build_q3_context)
from council.fact_checker import (VerificationReport, build_index_for_question,
                                  check_q2_structural_breaks, verify)
from council.manager import ManagerAgent
from council.ollama_client import parse_json_response

CONTEXT_BUILDERS = {
    "q1": build_q1_context,
    "q2": build_q2_context,
    "q3": build_q3_context,
}

QUESTION_TITLES = {
    "q1": "Prozentuale Zeitreduktion je Spielkategorie",
    "q2": "Sättigungsanalyse — Verlangsamt sich die Verbesserungsrate?",
    "q3": "WR-Lebensdauer — Kaplan-Meier Überlebensanalyse",
}


def run_council(
    *,
    question:           str,
    council_models:     list[tuple[str, str]],
    manager_model:      str,
    data_dir:           Path,
    analysis_dir:       Path,
    dataset_md:         Path,
    output_dir:         Path,           # single-agent output dir (for diff baseline)
    council_output_dir: Path,
    ollama_url:         str,
    keep_alive:         int,
    num_ctx:            int,
    max_revisions:      int,
) -> None:
    if question not in CONTEXT_BUILDERS:
        raise ValueError(f"unknown question: {question}")

    context, tok_estimate = CONTEXT_BUILDERS[question](data_dir, analysis_dir, dataset_md)

    tr.banner(f"Council · {question.upper()} · {QUESTION_TITLES[question]}", width=72)
    tr.info(f"Kontext: ~{tok_estimate:,} Tokens (num_ctx={num_ctx})")
    tr.info(f"Council: {', '.join(f'{p}/{m}' for p, m in council_models)}")
    tr.info(f"Manager: {manager_model}")

    # Build the council
    agents = [
        CouncilAgent(
            persona_id=persona_id,
            model=model,
            ollama_url=ollama_url,
            keep_alive=keep_alive,
            num_ctx=num_ctx,
        )
        for persona_id, model in council_models
    ]
    manager = ManagerAgent(
        model=manager_model,
        ollama_url=ollama_url,
        keep_alive=keep_alive,
        num_ctx=num_ctx,
    )

    # ── Round 1 ──────────────────────────────────────────────────────────────
    r1_raw: dict[str, str] = {}
    for i, agent in enumerate(agents, 1):
        tr.round_header(1, i, len(agents), agent.label, agent.model)
        try:
            r1_raw[agent.persona_id] = agent.generate(question, context)
        except requests.ConnectionError:
            tr.warn("Ollama nicht erreichbar — abbruch.")
            return
        except requests.HTTPError as exc:
            tr.warn(f"Ollama HTTP-Fehler: {exc}")
            return

    # ── Round 2 ──────────────────────────────────────────────────────────────
    r2_raw: dict[str, str] = {}
    for i, agent in enumerate(agents, 1):
        tr.round_header(2, i, len(agents), agent.label, agent.model)
        peers = {pid: text for pid, text in r1_raw.items() if pid != agent.persona_id}
        try:
            r2_raw[agent.persona_id] = agent.generate(
                question,
                context,
                peer_outputs=peers,
                own_round1=r1_raw[agent.persona_id],
            )
        except requests.HTTPError as exc:
            tr.warn(f"Ollama HTTP-Fehler: {exc}")
            return

    # ── Manager synthesis + fact-check loop ─────────────────────────────────
    tr.manager_header(manager.model, attempt=0)
    draft_raw = manager.synthesize(question, context, r2_raw)

    source_index = build_index_for_question(question, data_dir, analysis_dir)

    revisions: list[dict] = []
    final_report: VerificationReport | None = None
    final_draft_raw = draft_raw

    for attempt in range(max_revisions + 1):
        try:
            draft = parse_json_response(final_draft_raw)
        except json.JSONDecodeError as exc:
            tr.warn(f"Manager output is not valid JSON ({exc}) — keeping raw.")
            draft = {"_raw_response": final_draft_raw, "_parse_error": str(exc)}
            final_report = None
            break

        report = verify(draft, source_index)
        if question == "q2":
            sb_errors = check_q2_structural_breaks(draft, analysis_dir / "q2_stats.json")
            report.categorical_errors.extend(sb_errors)
        final_report = report

        if report.all_verified:
            tr.fact_check_header(True, report.summary_line())
            break

        tr.fact_check_header(False, report.summary_line())
        if attempt >= max_revisions:
            tr.warn(
                f"Max revisions ({max_revisions}) erreicht — speichere mit "
                f"fact_check_warnings."
            )
            break

        # Ask the manager to revise
        tr.manager_header(manager.model, attempt=attempt + 1)
        prev_raw = final_draft_raw
        final_draft_raw = manager.revise(question, context, prev_raw, report)
        revisions.append({
            "attempt":      attempt + 1,
            "input_report": report.revision_brief(),
            "raw_response": final_draft_raw,
        })

    # ── Save final result + transcript ───────────────────────────────────────
    output_payload: dict = {
        "question":       question,
        "title":          QUESTION_TITLES[question],
        "method":         "council-of-agents",
        "council":        [{"persona": p, "model": m} for p, m in council_models],
        "manager_model":  manager_model,
        "generated_at":   datetime.now().isoformat(timespec="seconds"),
        "token_estimate": tok_estimate,
    }

    if isinstance(draft, dict) and "_parse_error" not in draft:
        output_payload.update(draft)
        if final_report and not final_report.all_verified:
            output_payload["fact_check_warnings"] = [
                {"path": c.path, "value": c.raw, "snippet": c.snippet}
                for c in final_report.unverified
            ]
    else:
        output_payload["raw_response"] = final_draft_raw
        output_payload["parse_error"] = draft.get("_parse_error") if isinstance(draft, dict) else None

    council_output_dir.mkdir(parents=True, exist_ok=True)
    out_path = council_output_dir / f"{question}_council.json"
    out_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tr.info(f"Gespeichert → {out_path}")

    # Transcript: every raw response, the fact-check report, every revision.
    transcript_path = council_output_dir / f"{question}_transcript.json"
    tr.write_transcript(transcript_path, {
        "question":       question,
        "council":        [{"persona": p, "model": m} for p, m in council_models],
        "manager_model":  manager_model,
        "round1":         r1_raw,
        "round2":         r2_raw,
        "manager_initial": draft_raw,
        "revisions":      revisions,
        "fact_check":     {
            "verified_count":   len(final_report.verified)   if final_report else 0,
            "unverified_count": len(final_report.unverified) if final_report else 0,
            "unverified": [
                {"path": c.path, "value": c.raw, "snippet": c.snippet}
                for c in (final_report.unverified if final_report else [])
            ],
        },
    })
    tr.info(f"Transkript → {transcript_path}")

    # Diff vs single-agent baseline
    baseline_path = output_dir / f"{question}_analysis.json"
    if isinstance(draft, dict) and "_parse_error" not in draft:
        tr.print_diff_summary(draft, baseline_path)
