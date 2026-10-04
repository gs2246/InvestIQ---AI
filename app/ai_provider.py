"""The one place the app talks to an AI model. Swap providers by changing this file only.

Currently Google Gemini (free tier) through Google's official `google-genai` SDK,
model alias `gemini-flash-lite-latest`.

Mirrors app/db.py: an is_configured() check, and a clear failure (AIUnavailableError)
instead of a crash. With no GEMINI_API_KEY every other page and endpoint works; only
the chat says "AI is not configured".
"""
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

log = logging.getLogger("investiq.ai")

MODEL = "gemini-flash-lite-latest"
TEMPERATURE = 0.2           # low: explain the given facts, do not get creative
MAX_OUTPUT_TOKENS = 700
TIMEOUT_MS = 30_000

NOT_CONFIGURED_MESSAGE = (
    "AI is not configured, so the chat is unavailable. Everything else on the page works. "
    "To enable it, add a free Gemini key as GEMINI_API_KEY in the .env file and restart the app."
)
FAILED_MESSAGE = "The AI service did not answer just now. Please try again in a minute."


class AIUnavailableError(Exception):
    """No key configured, or the provider failed. The message is safe to show to the user."""


def api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def is_configured() -> bool:
    return bool(api_key())


def to_plain_prose(text: str) -> str:
    """Safety net for the 'no markdown' rule: strip emphasis marks, headings, code
    ticks and bullet markers if the model slips. The system prompt asks for plain prose."""
    text = re.sub(r"(\*\*|__|`+)", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*•]\s+", "", text)
    text = re.sub(r"(?<!\w)\*(?!\s)([^*\n]+)(?<!\s)\*(?!\w)", r"\1", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class GeminiProvider:
    def __init__(self, key: str):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))

    def generate(self, system_prompt: str, turns: list[dict]) -> str:
        """turns: [{"role": "user" | "ai", "text": str}, ...] ending with the user's question."""
        types = self._types
        contents = [
            types.Content(role="user" if t["role"] == "user" else "model", parts=[types.Part(text=t["text"])])
            for t in turns
        ]
        response = self._client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                # no tools are given to the model, so switch tool calling off explicitly
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return response.text or ""


def ask(system_prompt: str, turns: list[dict]) -> str:
    """The model's reply as plain prose, or AIUnavailableError (never a raw exception)."""
    if not is_configured():
        raise AIUnavailableError(NOT_CONFIGURED_MESSAGE)
    try:
        reply = GeminiProvider(api_key()).generate(system_prompt, turns)
    except Exception as exc:  # network, quota, bad key, provider outage: all the same to the user
        log.warning("AI provider failed: %s: %s", exc.__class__.__name__, str(exc)[:200])
        raise AIUnavailableError(FAILED_MESSAGE) from exc
    reply = to_plain_prose(reply)
    if not reply:
        raise AIUnavailableError(FAILED_MESSAGE)
    return reply
