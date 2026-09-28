"""Participant and contact resolution helpers."""

from __future__ import annotations

import re
from typing import Any

from .fathom import speaker_names


HOST_MARKERS = {"host", "recording bot"}


def contact_email(entry: Any) -> str:
    if isinstance(entry, dict):
        return (entry.get("email") or "").strip()
    return str(entry or "").strip()


def load_contacts_map(raw: dict[str, Any] | None) -> dict[str, Any]:
    return raw or {}


def normalize_display_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return name
    if "@" in name:
        name = name.split("@", 1)[0]
    parts = [part for part in re.split(r"\s+", name) if part]
    return " ".join(part[:1].upper() + part[1:] for part in parts)


def canonical_by_email(email: str, contacts: dict[str, Any]) -> str:
    if not email:
        return ""
    target = email.strip().lower()
    matches = [name for name, entry in contacts.items() if contact_email(entry).lower() == target]
    if not matches:
        return ""
    full_names = [name for name in matches if " " in name and name[:1].isupper()]
    if full_names:
        return max(full_names, key=len)
    any_full = [name for name in matches if " " in name]
    if any_full:
        return normalize_display_name(max(any_full, key=len))
    proper = [name for name in matches if name[:1].isupper() and not any(ch.isdigit() for ch in name)]
    if proper:
        return max(proper, key=len)
    return normalize_display_name(max(matches, key=len))


def lookup_contact_email(name: str, contacts: dict[str, Any]) -> str:
    clean = re.sub(r"[@#]", "", name or "").strip()
    if not clean:
        return ""
    if clean in contacts:
        return contact_email(contacts[clean])
    lower = clean.lower()
    parts = lower.split()
    for cname, entry in contacts.items():
        if cname.lower() == lower:
            return contact_email(entry)
    if len(parts) == 1:
        for cname, entry in contacts.items():
            cparts = cname.lower().split()
            if cparts and cparts[0] == parts[0]:
                return contact_email(entry)
    for cname, entry in contacts.items():
        if cname.lower().startswith(lower):
            return contact_email(entry)
    return ""


def resolve_participant(payload: dict, contacts: dict[str, Any], host_email: str = "", host_name: str = "") -> dict[str, str]:
    host_email = (host_email or "").lower()
    host_name = (host_name or "").lower()
    recorded_by = payload.get("recorded_by") or {}
    recorder_email = (recorded_by.get("email") or host_email).lower()

    name = ""
    email = ""
    invitees = payload.get("calendar_invitees") or []
    speakers = speaker_names(payload)

    for invitee in invitees:
        candidate_email = (invitee.get("email") or "").strip()
        candidate_name = (invitee.get("name") or "").strip()
        if candidate_email.lower() in {host_email, recorder_email}:
            continue
        if candidate_name or candidate_email:
            name = candidate_name
            email = candidate_email
            break

    if not name:
        for invitee in invitees:
            matched = (invitee.get("matched_speaker_display_name") or "").strip()
            candidate_email = (invitee.get("email") or "").strip()
            if matched and matched in speakers and candidate_email.lower() not in {host_email, recorder_email}:
                name = matched
                email = candidate_email
                break

    if not name:
        for speaker in sorted(speakers):
            lower = speaker.lower()
            is_host = bool(host_name and host_name in lower)
            if not is_host and lower not in HOST_MARKERS and speaker != "Unknown":
                name = speaker
                break

    if name and not email:
        email = lookup_contact_email(name, contacts)

    canonical = canonical_by_email(email, contacts)
    if canonical:
        name = canonical
    elif name:
        name = normalize_display_name(name)

    return {
        "name": name or "Meeting Participant",
        "email": email,
        "first_name": normalize_display_name((name or "Meeting Participant").split()[0]),
    }
