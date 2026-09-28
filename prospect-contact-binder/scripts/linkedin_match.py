#!/usr/bin/env python3
"""
Decide whether a LinkedIn search result is really the person you asked for.

Why this file exists
--------------------
The obvious way to check a match is to read the URL: does
`linkedin.com/in/adam-morgan` contain "adam" and "morgan"? It is cheap, it
needs no extra API call, and it is wrong in both directions.

    Searching "Adam Morgan" at Twilio:
      linkedin.com/in/adam-morgan-28227a420   slug says adam + morgan  -> ACCEPTED, wrong person
      linkedin.com/in/admo3                   slug says neither        -> REJECTED, right person
                                              (profile reads "VP of Brand at Twilio")

Both failures come from the same mistake: the slug is a vanity handle the
person picked, not a fact about their employment. Half of senior people have
initials, a nickname, or a number in theirs.

So this module ignores the URL and reads the profile instead. Exa can return
the profile text alongside the search result; the text says where they
actually work. That is the thing worth checking.

    name must appear in the profile   -> is this that person
    company must appear in the profile -> at the company you meant

Both, or it is not a match.

Where the slug does still help
------------------------------
A LinkedIn post URL embeds its author's handle:

    linkedin.com/posts/admo3_because-project-hail-mary-...
                       ^^^^^ the author

So a post that confirms "Adam Morgan, VP of Brand at Twilio" hands you the
canonical profile URL for free — which is exactly how you find the people
whose handles you could never have guessed.
"""

from __future__ import annotations

import re

PROFILE_RE = re.compile(r"linkedin\.com/in/([A-Za-z0-9\-_%]+)", re.I)
POST_RE = re.compile(r"linkedin\.com/posts/([A-Za-z0-9\-_%]+?)_", re.I)

# Stripped from a person's name before matching. "Cara McNulty, DPA" is
# Cara McNulty; nobody's surname is "DPA".
CREDENTIALS_RE = re.compile(
    r"\b(PhD|MD|MBA|MPH|MSW|LCSW|RN|DO|PsyD|FAAP|DPA|JD|CPA|MS|MA|BCBA|CFA|CAIA|"
    r"PMP|CMP|LPC|DSW|FACEP|FAMIA|DLFAPA|CPRS|EdD|MHSP|LAC|ENP|Esq|II|III|Jr|Sr)\b\.?",
    re.I,
)

# Stripped from a company before matching, so "Twilio" matches "Twilio Inc."
COMPANY_NOISE_RE = re.compile(
    r"\b(inc|llc|ltd|corp|corporation|co|company|holdings|group|the|and|of|"
    r"gmbh|plc|lp|llp|pllc|pc)\b\.?",
    re.I,
)

# Words too common to identify an employer on their own. "Health" appearing in
# a behavioural-health person's profile proves nothing.
GENERIC_TOKENS = {
    "health", "healthcare", "care", "medical", "clinic", "hospital", "services",
    "service", "solutions", "systems", "technologies", "technology", "tech",
    "global", "international", "national", "american", "us", "usa", "digital",
    "partners", "associates", "ventures", "capital", "foundation", "institute",
    "center", "centre", "council", "association", "network", "labs", "lab",
    "consulting", "media", "agency", "studio", "behavioral", "behavioural",
    "mental", "wellness", "therapy", "management", "advisors", "advisory",
}

# Roster junk that is not a person. Searching these can only produce a false
# match against someone who happens to share the words.
NOT_A_PERSON_RE = re.compile(
    r"^(who we are|about( us)?|our team|team|leadership( interview)?|contact( us)?|"
    r"careers|investor relations|people archive|y combinator|linkedin|instagram|"
    r"facebook|twitter|x|company|provider toolkit|capital deployment|startup intros|"
    r"leaders social|grey matter|between two chairs)$",
    re.I,
)

ORG_TAIL_RE = re.compile(
    r"\b(inc|llc|ltd|corp|group|agency|partners|ventures|capital|foundation|"
    r"institute|council|association|solutions|systems|technologies|media|labs|"
    r"board|journal|blog|toolkit)\b\.?$",
    re.I,
)


def clean_name(name: str) -> str:
    """Drop credentials and punctuation so the real given/family names remain."""
    text = CREDENTIALS_RE.sub(" ", name or "")
    text = re.sub(r"[.,]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_parts(name: str) -> tuple[str, str]:
    """Return (first, last) lowercased and letter-only. ('', '') if unusable."""
    parts = [p for p in clean_name(name).split() if len(p) > 1]
    if len(parts) < 2:
        return "", ""
    first = re.sub(r"[^a-z]", "", parts[0].lower())
    last = re.sub(r"[^a-z]", "", parts[-1].lower())
    return (first, last) if len(first) >= 2 and len(last) >= 2 else ("", "")


def looks_like_person(name: str) -> bool:
    """Cheap guard so a search is never spent on 'Investor Relations'."""
    cleaned = clean_name(name)
    if not cleaned or NOT_A_PERSON_RE.match(cleaned) or ORG_TAIL_RE.search(cleaned):
        return False
    first, last = name_parts(cleaned)
    return bool(first and last)


def company_terms(company: str) -> list[str]:
    """
    The tokens that would actually identify this employer in a profile.

    Generic words are dropped: matching "Vibrant Emotional Health" on the word
    "health" would confirm half of behavioural health as the same company. If
    everything is generic, fall back to the whole normalised string.
    """
    text = COMPANY_NOISE_RE.sub(" ", company or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if len(t) > 2]
    distinctive = [t for t in tokens if t not in GENERIC_TOKENS]
    if distinctive:
        return distinctive
    joined = " ".join(tokens).strip()
    return [joined] if joined else []


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())


def author_of_post(title: str) -> str:
    """
    The author of a LinkedIn post, as Exa titles them.

    Exa renders a post title as "<post text> | <Author>", so the author is
    whatever follows the final pipe. This matters enormously: a post *about*
    your person, published by their employer, embeds the EMPLOYER's handle in
    the URL, not theirs.

        .../posts/boulder_before-joining-our-team-andy-kelly-spent-...
            title: "Before joining our team, Andy Kelly spent... | Boulder Care"
            author: "Boulder Care"  -> the handle is the company's, not Andy's

    Taking the handle without checking the author is how you end up with
    linkedin.com/in/boulder as someone's personal profile.
    """
    if "|" not in (title or ""):
        return ""
    return title.rsplit("|", 1)[-1].strip()


def _names_present(first: str, last: str, haystack: str) -> bool:
    return bool(first) and bool(last) and first in haystack and last in haystack


def evaluate(person: str, company: str, url: str, title: str = "", text: str = "") -> tuple[str, str, str]:
    """
    Judge one search result.

    Returns (profile_url, confidence, reason); profile_url is "" to discard.

      confirmed — this person is named as the profile's owner (or the post's
                  author) AND the employer appears in the content
      probable  — owner/author confirmed, but no company was supplied to check

    Two different shapes of result, judged differently:

      /in/<slug>    the title IS the profile owner's name, so the name must
                    match the title. The employer is checked against the body.
      /posts/<slug> the slug is the AUTHOR's handle. It is only this person's
                    profile if the post's author is this person — otherwise
                    you harvest the handle of whoever wrote about them.
    """
    first, last = name_parts(person)
    if not first or not last:
        return "", "", "unusable-name"

    body = _norm(f"{title} {text}")
    if not body.strip():
        return "", "", "no-content-to-verify"

    profile_hit = PROFILE_RE.search(url or "")
    post_hit = POST_RE.search(url or "")

    if profile_hit:
        canonical = f"https://www.linkedin.com/in/{profile_hit.group(1).rstrip('/')}"
        # The owner's name is the title of their profile page.
        owner = _norm(title) if title else body
        if not _names_present(first, last, owner):
            return "", "", "profile-title-is-a-different-person"
    elif post_hit:
        author = author_of_post(title)
        if not author:
            return "", "", "post-with-no-identifiable-author"
        if not _names_present(first, last, _norm(author)):
            return "", "", "post-written-by-someone-else"
        canonical = f"https://www.linkedin.com/in/{post_hit.group(1).rstrip('/')}"
    else:
        return "", "", "not-a-profile-url"

    terms = company_terms(company)
    if not terms:
        # No company supplied — an identity match is all there is to check.
        return canonical, "probable", "person-confirmed-no-company-given"

    if all(t in body for t in terms):
        return canonical, "confirmed", "person-and-employer-confirmed-in-profile"
    if any(t in body for t in terms):
        return canonical, "confirmed", "person-and-employer-partially-confirmed"

    return "", "", "employer-not-in-profile"


def best_match(person: str, company: str, results: list[dict]) -> tuple[str, str, str]:
    """
    Pick the best result from a search.

    Prefers a confirmed match over a probable one, and among equals prefers
    the one that came from an actual profile page rather than a post.
    Returns (url, confidence, reason); ("", "", reason) when nothing qualifies.
    """
    confirmed: list[tuple[str, str, str, bool]] = []
    probable: list[tuple[str, str, str, bool]] = []
    last_reason = "no-results"

    for item in results:
        url = item.get("url", "") or ""
        matched, confidence, reason = evaluate(
            person, company, url, item.get("title", ""), item.get("text", "")
        )
        last_reason = reason
        if not matched:
            continue
        is_profile = "/in/" in url.lower()
        bucket = confirmed if confidence == "confirmed" else probable
        bucket.append((matched, confidence, reason, is_profile))

    for bucket in (confirmed, probable):
        if bucket:
            bucket.sort(key=lambda t: not t[3])  # real profile pages first
            url, confidence, reason, _ = bucket[0]
            return url, confidence, reason

    return "", "", last_reason
