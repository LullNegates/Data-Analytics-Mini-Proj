"""CouncilAgent — one persona × one Ollama model.

Round 1 (`peer_outputs=None`): independent generation from the question context.
Round 2 (`peer_outputs={persona_id: text, ...}`): the agent sees its own round-1
answer plus the other two agents' answers and is asked to revise critically.
This is the debate step from Du et al. 2023 (arXiv:2305.14325).
"""

from dataclasses import dataclass
from typing import Optional

from council.ollama_client import call_ollama_streaming
from council.personas import PERSONAS, build_system_prompt

PERSONA_LABEL: dict[str, str] = {
    "statistician": "Statistiker",
    "domain":       "Domänenexperte",
    "skeptic":      "Skeptiker",
}


@dataclass(frozen=True)
class CouncilAgent:
    """One member of the council, identified by persona + model.

    The same class handles round 1 and round 2 — the only difference is whether
    ``peer_outputs`` is supplied to ``generate``.
    """
    persona_id: str
    model:      str
    ollama_url: str
    keep_alive: int
    num_ctx:    int

    def __post_init__(self) -> None:
        if self.persona_id not in PERSONAS:
            raise ValueError(f"unknown persona: {self.persona_id}")

    @property
    def label(self) -> str:
        return PERSONA_LABEL[self.persona_id]

    def system_prompt(self, question: str) -> str:
        return build_system_prompt(question, self.persona_id)

    def generate(
        self,
        question: str,
        context: str,
        peer_outputs: Optional[dict[str, str]] = None,
        own_round1: Optional[str] = None,
        *,
        temperature: float = 0.2,
        num_predict: int = 8000,
    ) -> str:
        """Run one round of inference.

        Args:
            question: "q1", "q2", or "q3".
            context: pre-built question context (from build_q{N}_context).
            peer_outputs: round-2 only. Map of persona_id → that peer's round-1
                or round-2 text. Must NOT include this agent's own output.
            own_round1: round-2 only. This agent's round-1 text, used as the
                "previously you said..." anchor.
            temperature: passed through to Ollama.
            num_predict: max output tokens.

        Returns:
            Raw response text. JSON parsing is the orchestrator's responsibility
            (so the transcript captures the raw text even if it's malformed).
        """
        if peer_outputs is None:
            user_prompt = self._round1_user_prompt(context)
        else:
            if own_round1 is None:
                raise ValueError("round 2 requires own_round1")
            user_prompt = self._round2_user_prompt(context, own_round1, peer_outputs)

        return call_ollama_streaming(
            url        = self.ollama_url,
            model      = self.model,
            system     = self.system_prompt(question),
            user       = user_prompt,
            keep_alive = self.keep_alive,
            num_ctx    = self.num_ctx,
            temperature= temperature,
            num_predict= num_predict,
        )

    # ── Prompt assembly ──────────────────────────────────────────────────────

    @staticmethod
    def _round1_user_prompt(context: str) -> str:
        return (
            f"{context}\n\n"
            "---\n\n"
            "Erstelle das JSON gemäß dem in der Systemnachricht vorgegebenen Schema. "
            "Berücksichtige deine Rolle. Gib NUR das JSON-Objekt aus."
        )

    def _round2_user_prompt(
        self, context: str, own_round1: str, peer_outputs: dict[str, str]
    ) -> str:
        peer_blocks = []
        for pid, text in peer_outputs.items():
            if pid == self.persona_id:
                continue  # never include self
            peer_blocks.append(f"== Kollege ({PERSONA_LABEL[pid]}) ==\n{text.strip()}")
        peers_section = "\n\n".join(peer_blocks)

        return (
            f"{context}\n\n"
            "---\n\n"
            "Du hast in Runde 1 folgende Antwort gegeben:\n"
            f"{own_round1.strip()}\n\n"
            "Zwei Kollegen haben unabhängig diese Antworten gegeben:\n\n"
            f"{peers_section}\n\n"
            "---\n\n"
            "Aufgabe: Lies die Antworten der Kollegen kritisch. Wo widersprechen sie deiner? "
            "Wo haben sie Recht? Aktualisiere deine Antwort entsprechend. Behalte nur Aussagen, "
            "die du in den Quelldaten verifizieren kannst — verwerfe Spekulation. "
            "Antworte erneut im selben JSON-Schema. Gib NUR das JSON aus."
        )
