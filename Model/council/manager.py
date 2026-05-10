"""ManagerAgent — synthesises the council's three round-2 outputs into a final
JSON answer and revises it on fact-check failure.

The manager runs ``MANAGER_MODEL`` (phi4-mini by default), the strongest local
instruction-follower. It receives the schema contract via the system prompt
(same as council members) so its output is structurally compatible with the
existing q*_analysis.json files.
"""

from dataclasses import dataclass

from council.fact_checker import VerificationReport
from council.ollama_client import call_ollama_streaming
from council.personas import build_manager_system_prompt


@dataclass(frozen=True)
class ManagerAgent:
    model:      str
    ollama_url: str
    keep_alive: int
    num_ctx:    int

    @property
    def label(self) -> str:
        return "Manager"

    def synthesize(
        self,
        question: str,
        context: str,
        round2_outputs: dict[str, str],
        *,
        temperature: float = 0.1,
        num_predict: int = 16000,
    ) -> str:
        user_prompt = self._synthesis_prompt(context, round2_outputs)
        return call_ollama_streaming(
            url              = self.ollama_url,
            model            = self.model,
            system           = build_manager_system_prompt(question),
            user             = user_prompt,
            keep_alive       = self.keep_alive,
            num_ctx          = self.num_ctx,
            temperature      = temperature,
            num_predict      = num_predict,
            disable_thinking = False,   # show reasoning trace on terminal
        )

    def revise(
        self,
        question: str,
        context: str,
        previous_draft: str,
        report: VerificationReport,
        *,
        temperature: float = 0.05,
        num_predict: int = 16000,
    ) -> str:
        user_prompt = self._revision_prompt(context, previous_draft, report)
        return call_ollama_streaming(
            url              = self.ollama_url,
            model            = self.model,
            system           = build_manager_system_prompt(question),
            user             = user_prompt,
            keep_alive       = self.keep_alive,
            num_ctx          = self.num_ctx,
            temperature      = temperature,
            num_predict      = num_predict,
            disable_thinking = False,   # show reasoning trace on terminal
        )

    # ── Prompt assembly ──────────────────────────────────────────────────────

    @staticmethod
    def _synthesis_prompt(context: str, round2_outputs: dict[str, str]) -> str:
        labels = {
            "statistician": "Statistiker",
            "domain":       "Domänenexperte",
            "skeptic":      "Skeptiker",
        }
        blocks = []
        for pid, text in round2_outputs.items():
            blocks.append(f"== {labels.get(pid, pid)} (Runde 2) ==\n{text.strip()}")
        analysts = "\n\n".join(blocks)

        return (
            f"{context}\n\n"
            "---\n\n"
            "Drei unabhängige Analysten haben dir ihre finalen Antworten vorgelegt:\n\n"
            f"{analysts}\n\n"
            "---\n\n"
            "Aufgabe: Synthetisiere die beste Gesamtantwort. Bevorzuge Aussagen, die "
            "von mindestens zwei Analysten gestützt werden. Bei Widersprüchen "
            "entscheide auf Basis der Quelldaten. Verwerfe Behauptungen, deren Zahlen "
            "nicht in den Quelldaten stehen. Behalte das vorgegebene JSON-Schema EXAKT "
            "bei. Gib NUR das JSON aus.\n\n"
            "WICHTIG: Schliesse ALLE Arrays und Objekte vollstaendig ab. "
            "Kuerze die Liste NICHT — genre_patterns braucht alle 7 Genres, "
            "saturation_by_game alle 17 Spiele. Gib erst dann das schliessende } aus, "
            "wenn alle Felder vollstaendig geschrieben sind."
        )

    @staticmethod
    def _revision_prompt(
        context: str, previous_draft: str, report: VerificationReport
    ) -> str:
        return (
            f"{context}\n\n"
            "---\n\n"
            "Du hast bereits folgenden Entwurf vorgelegt:\n"
            f"{previous_draft.strip()}\n\n"
            "Eine deterministische Faktenprüfung hat folgende Probleme gefunden:\n"
            f"{report.revision_brief()}\n\n"
            "Aufgabe: Korrigiere genau diese Stellen. Ersetze die unbelegten Zahlen "
            "durch korrekte Werte aus den Quelldaten oder entferne die betroffene "
            "Aussage. Lass alles andere unveraendert. Schliesse ALLE Arrays und Objekte "
            "vollstaendig ab. Gib NUR das aktualisierte JSON aus."
        )
