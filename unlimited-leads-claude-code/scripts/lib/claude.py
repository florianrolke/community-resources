"""
One place where this repo talks to Claude.

The n8n version had the model, the prompt, and the "give me JSON" plumbing
spread across five different nodes. Here it's one function you can read.

Structured output note
----------------------
n8n used a "Structured Output Parser" node, which asks the model for JSON and
hopes. `output_config.format` is the real thing: the API constrains generation
to your JSON Schema, so you get valid JSON or an error — never a half-parsed
string. That's the whole determinism argument in one parameter.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from scripts.lib.env import require

# Claude Opus 5 is the default: best quality, and these calls are small.
# Every script takes --model, so swap it if you want to trade quality for cost.
# See docs/COSTS.md for the per-lead numbers.
DEFAULT_MODEL = "claude-opus-5"

_client = None


def get_client():
    """One shared Anthropic client."""
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(
            api_key=require(
                "ANTHROPIC_API_KEY",
                hint="Get one at https://console.anthropic.com",
            )
        )
    return _client


def structured(
    system: str,
    user: str,
    schema: dict,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    effort: str = "low",
) -> dict:
    """
    Ask Claude a question and get back a dict matching `schema`. Guaranteed.

    effort="low" is right for the short extraction and copywriting calls in this
    repo — they don't need deep reasoning, and low effort keeps them fast and
    cheap. Raise it for genuinely hard judgment calls.
    """
    client = get_client()

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": schema},
        },
        messages=[{"role": "user", "content": user}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(
            "Claude declined this request. Check what you're sending — usually "
            "a scraped page contained something that tripped a safety filter."
        )

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        raise RuntimeError(f"Empty response from Claude (stop_reason={response.stop_reason})")

    return json.loads(text)


def usage_cost(response, model: str = DEFAULT_MODEL) -> float:
    """Rough dollar cost of one response, so scripts can print a running total."""
    # Opus 5 pricing: $5 per million input, $25 per million output.
    rates = {
        "claude-opus-5": (5.0, 25.0),
        "claude-sonnet-5": (3.0, 15.0),
        "claude-haiku-4-5": (1.0, 5.0),
    }
    rate_in, rate_out = rates.get(model, (5.0, 25.0))
    u = response.usage
    return (u.input_tokens * rate_in + u.output_tokens * rate_out) / 1_000_000


def load_prompt(name: str) -> tuple[str, str]:
    """
    Read a prompt file from prompts/ and split it into (system, user_template).

    The prompts are Jack's, ported verbatim from the n8n nodes. Keeping them as
    markdown files instead of burying them in Python means you can edit the
    copywriting without touching code — which is the point.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "prompts" / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")

    text = path.read_text(encoding="utf-8")

    def _section(header: str) -> str:
        if header not in text:
            return ""
        after = text.split(header, 1)[1]
        # Content sits in the first fenced block after the header.
        if "```" not in after:
            return ""
        body = after.split("```", 2)
        return body[1].strip() if len(body) > 1 else ""

    return _section("## System prompt"), _section("## User message template")
