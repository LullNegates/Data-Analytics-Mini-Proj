"""Streaming Ollama chat client — extracted from the deleted questions/q*.py runners.

Single entry point: ``call_ollama_streaming``. Prints tokens to stdout as they
arrive (so the council orchestrator gets a live view of every agent's output)
and returns the full concatenated response.
"""

import json
import sys
from typing import Optional

import requests


_DIM   = "\033[2m"  if sys.stdout.isatty() else ""
_RESET = "\033[0m"  if sys.stdout.isatty() else ""
_ITALIC = "\033[3m" if sys.stdout.isatty() else ""


def call_ollama_streaming(
    url: str,
    model: str,
    system: str,
    user: str,
    keep_alive: int,
    num_ctx: int,
    *,
    temperature: float = 0.15,
    num_predict: int = 3000,
    prefix: str = "",
    timeout: int = 600,
    disable_thinking: bool = True,
) -> str:
    """Call Ollama's /api/chat in streaming mode.

    Args:
        prefix: optional string printed before each emitted token.
        disable_thinking: when False, thinking-mode models (qwen3, deepseek-r1)
            stream their CoT reasoning via ``message.thinking`` before emitting
            the final answer in ``message.content``.

            Behaviour per flag value:
            - True  (default): ``think=False`` sent to Ollama. Model skips CoT
              entirely. ``message.content`` holds the full response. Safe for
              all models including non-thinking ones.
            - False: thinking enabled. ``message.thinking`` tokens are printed
              to the terminal in dim/italic style so the reasoning trace is
              visible, but they are NOT included in the returned string. Only
              ``message.content`` (the final answer) is returned. Use this for
              the Manager so its synthesis reasoning is auditable.

    Returns:
        The final answer text (``message.content`` only). Thinking traces are
        printed to stdout but never returned.

    Raises:
        requests.ConnectionError: Ollama is not running.
        requests.HTTPError: Ollama returned a non-2xx status.
    """
    options: dict = {
        "temperature": temperature,
        "num_predict": num_predict,
        "num_ctx":     num_ctx,
    }
    if disable_thinking:
        options["think"] = False

    payload = {
        "model":      model,
        "messages":   [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream":     True,
        "keep_alive": keep_alive,
        "options":    options,
    }

    resp = requests.post(url, json=payload, stream=True, timeout=timeout)
    resp.raise_for_status()

    content_chunks: list[str] = []
    in_thinking = False
    content_line_start = True

    for raw in resp.iter_lines():
        if not raw:
            continue
        chunk = json.loads(raw)
        msg = chunk.get("message", {})

        # ── Thinking trace (qwen3, deepseek-r1 etc.) ─────────────────────────
        thinking_token = msg.get("thinking", "")
        if thinking_token:
            if not in_thinking:
                # Print a dim label the first time thinking starts
                sys.stdout.write(f"{_DIM}{_ITALIC}  [thinking]\n{_RESET}")
                sys.stdout.flush()
                in_thinking = True
            sys.stdout.write(f"{_DIM}{_ITALIC}{thinking_token}{_RESET}")
            sys.stdout.flush()

        # ── Actual response content ───────────────────────────────────────────
        content_token = msg.get("content", "")
        if content_token:
            if in_thinking:
                # Thinking just ended — print a separator before the answer
                sys.stdout.write(f"\n{_RESET}")
                sys.stdout.flush()
                in_thinking = False
            if prefix and content_line_start:
                sys.stdout.write(prefix)
                content_line_start = False
            sys.stdout.write(content_token)
            sys.stdout.flush()
            content_chunks.append(content_token)
            if "\n" in content_token:
                content_line_start = True

        if chunk.get("done"):
            break

    sys.stdout.write("\n")
    sys.stdout.flush()
    return "".join(content_chunks)


def _strip_fences(raw: str) -> str:
    """Remove Markdown code fences and stray backticks the model adds."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip().rstrip("`").strip()


def parse_json_response(raw: str) -> dict:
    """Parse the model's JSON response, repairing common truncation errors.

    Strategy:
      1. Strip Markdown fences.
      2. Try strict ``json.loads`` — fastest and most reliable path.
      3. On failure, try ``json_repair`` which handles missing closing braces,
         missing closing quotes, trailing commas, and missing ``}`` before ``]``
         (the pattern seen when the model hits its ``num_predict`` cap mid-object).

    Raises ``json.JSONDecodeError`` only if both strict and repair attempts fail.
    """
    text = _strip_fences(raw)

    # Fast path
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Repair path
    try:
        from json_repair import repair_json  # type: ignore[import]
        repaired = repair_json(text, return_objects=False, ensure_ascii=False)
        result = json.loads(repaired)
        if isinstance(result, dict):
            return result
        # repair_json can return a list or scalar for badly broken input
        raise json.JSONDecodeError("repaired result is not a dict", text, 0)
    except ImportError:
        pass  # json-repair not installed — fall through to re-raise
    except Exception:
        pass

    # Re-raise original error
    return json.loads(text)  # will raise JSONDecodeError


def smoke_test(url: str, model: str, *, timeout: int = 60) -> Optional[str]:
    """Send a one-token prompt to verify a model is reachable and loaded.

    Returns the response text on success, ``None`` on connection failure.
    """
    try:
        resp = requests.post(
            url,
            json={
                "model":    model,
                "messages": [{"role": "user", "content": "Antworte mit 'ok'."}],
                "stream":   False,
                "options":  {"num_predict": 8, "temperature": 0.0},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")
    except (requests.ConnectionError, requests.HTTPError):
        return None
