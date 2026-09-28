"""Structured summary generation with provider fallbacks."""

from __future__ import annotations

import json
import re
from typing import Any


SUMMARY_SCHEMA_KEYS = {
    "action_items": [],
    "meeting_summary": [],
    "epiphanies": [],
    "main_points": "the meeting discussion and next steps",
    "projects_mentioned": [],
    "upcoming_events": [],
    "topics": [],
}


def _json_from_text(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def fallback_summary(transcript: str, participant_name: str) -> dict[str, Any]:
    sentences = re.split(r"(?<=[.!?])\s+", transcript.strip())
    useful = [s.strip() for s in sentences if len(s.strip()) > 30][:5]
    return {
        "action_items": [],
        "meeting_summary": [f"**Discussion** - {point}" for point in useful[:4]] or ["**Discussion** - Meeting transcript was captured and stored."],
        "epiphanies": [],
        "main_points": "the main topics from our conversation and the next practical steps",
        "projects_mentioned": [],
        "upcoming_events": [],
        "topics": [],
    }


def build_prompt(transcript: str, participant_name: str, fathom_summary: str = "", action_items: list | None = None) -> str:
    action_text = "\n".join(f"- {item.get('text', '')}" for item in action_items or []) or "(none provided)"
    return f"""Create a structured meeting summary from the full transcript.

Participant: {participant_name}

Fathom summary for reference only:
{fathom_summary}

Fathom action items:
{action_text}

Full transcript:
{transcript}

Rules:
- Generate original content from the transcript.
- Do not include timestamps, URLs, markdown links, or ### headings.
- Action items must use: **Category** - Description.
- MAIN_POINTS must complete the sentence "Today we covered ...".
- MAIN_POINTS must be concrete. Avoid generic phrases like strategic pivot, strategic shift, current business priorities, next steps from the call, opportunity pipeline, and technical requirements.

Return exact JSON:
{{
  "action_items": ["**Category** - Description"],
  "meeting_summary": ["**Topic** - Description"],
  "epiphanies": ["**Insight** - Description"],
  "main_points": "topic one and topic two",
  "projects_mentioned": [{{"name": "Project", "context": "Context"}}],
  "upcoming_events": [{{"date": "Date", "event": "Event", "project": "Project or null"}}],
  "topics": ["topic"]
}}
"""


def generate_summary(settings, transcript: str, participant_name: str, fathom_summary: str = "", action_items: list | None = None) -> dict[str, Any]:
    provider = settings.llm_provider
    prompt = build_prompt(transcript, participant_name, fathom_summary, action_items)
    try:
        if provider == "gemini" and settings.google_api_key:
            import google.generativeai as genai

            genai.configure(api_key=settings.google_api_key)
            model = genai.GenerativeModel(settings.gemini_summary_model)
            result = _json_from_text(model.generate_content(prompt).text)
        elif provider == "openai" and settings.openai_api_key:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            result = _json_from_text(response.choices[0].message.content or "")
        else:
            result = None
    except Exception:
        result = None

    if not result:
        return fallback_summary(transcript, participant_name)
    return {**SUMMARY_SCHEMA_KEYS, **result}
