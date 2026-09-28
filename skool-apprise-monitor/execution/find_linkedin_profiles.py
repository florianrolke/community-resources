#!/usr/bin/env python3
"""
Find LinkedIn profiles for scraped Skool members.

Waterfall chain: Tavily → Perplexity → Exa → Apollo
- Tavily: 6 keys (renewable monthly, 1000/mo each). Start with key 5 (1-4 exhausted).
- Perplexity: Pay-as-you-go sonar model.
- Exa: 6 keys (renewable, 1000/mo each). Neural search.
- Apollo: Finite credits. Email-to-LinkedIn lookup. Last resort.

Input:  .tmp/latest_scraped_members.json (from test_qualification_pipeline.py)
Output: .tmp/members_with_linkedin.json

Usage:
    python execution/find_linkedin_profiles.py                          # All members
    python execution/find_linkedin_profiles.py --limit 5                # First 5 only
    python execution/find_linkedin_profiles.py --resume                 # Resume from checkpoint
    python execution/find_linkedin_profiles.py --input path/to/file.json  # Custom input
    python execution/find_linkedin_profiles.py --skip-apollo            # Skip Apollo (save credits)
"""

import os
import sys
import json
import time
import re
import argparse
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"
DEFAULT_INPUT = TMP_DIR / "latest_scraped_members.json"
OUTPUT_FILE = TMP_DIR / "members_with_linkedin.json"
CHECKPOINT_FILE = TMP_DIR / "linkedin_finder_checkpoint.json"

# Rate limiting
DELAY_BETWEEN_CALLS = 2
CALLS_BEFORE_PAUSE = 10
PAUSE_DURATION = 15

# ─── API Keys ───────────────────────────────────────────────────────────────

PERPLEXITY_KEY = os.getenv('PERPLEXITY_API_KEY')

# Tavily: start with key 5 (1-4 exhausted per CLAUDE.md)
TAVILY_KEYS = [k for k in [
    os.getenv('TAVILY_API_KEY_5'),
    os.getenv('TAVILY_API_KEY_6'),
    os.getenv('TAVILY_API_KEY'),
    os.getenv('TAVILY_API_KEY_2'),
    os.getenv('TAVILY_API_KEY_3'),
    os.getenv('TAVILY_API_KEY_4'),
] if k]

EXA_KEYS = [k for k in [
    os.getenv('EXA_API_KEY'),
    os.getenv('EXA_API_KEY_2'),
    os.getenv('EXA_API_KEY_3'),
    os.getenv('EXA_API_KEY_4'),
    os.getenv('EXA_API_KEY_5'),
    os.getenv('EXA_API_KEY_6'),
] if k]

APOLLO_KEY = os.getenv('APOLLO_API_KEY')

# Key rotation state
current_tavily_idx = 0
current_exa_idx = 0
api_call_count = 0
exhausted_tavily = set()
exhausted_exa = set()


def get_tavily_key():
    global current_tavily_idx
    if not TAVILY_KEYS:
        return None
    # Try all keys, skip exhausted
    for _ in range(len(TAVILY_KEYS)):
        idx = current_tavily_idx % len(TAVILY_KEYS)
        current_tavily_idx += 1
        if idx not in exhausted_tavily:
            return TAVILY_KEYS[idx]
    return None  # All exhausted


def get_exa_key():
    global current_exa_idx
    if not EXA_KEYS:
        return None
    for _ in range(len(EXA_KEYS)):
        idx = current_exa_idx % len(EXA_KEYS)
        current_exa_idx += 1
        if idx not in exhausted_exa:
            return EXA_KEYS[idx]
    return None


def rate_limit_check():
    global api_call_count
    api_call_count += 1
    if api_call_count % CALLS_BEFORE_PAUSE == 0:
        print(f"\n  [Rate limit] Pausing {PAUSE_DURATION}s after {api_call_count} API calls...")
        time.sleep(PAUSE_DURATION)
        print(f"  [Rate limit] Resuming...\n")
    else:
        time.sleep(DELAY_BETWEEN_CALLS)


# ─── LinkedIn URL Validation ────────────────────────────────────────────────

LINKEDIN_PATTERN = re.compile(
    r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9\-_%]+)',
    re.IGNORECASE
)


def extract_linkedin_url(text: str) -> str | None:
    """Extract first valid LinkedIn /in/ URL from text. Normalizes to www.linkedin.com."""
    if not text:
        return None
    match = LINKEDIN_PATTERN.search(text)
    if match:
        slug = match.group(1).rstrip('/')
        # Skip generic/fake slugs
        if slug.lower() in ('example', 'username', 'yourname', 'profile', '', 'dir'):
            return None
        # Always normalize to www.linkedin.com/in/
        return f"https://www.linkedin.com/in/{slug}"
    return None


def validate_linkedin_for_person(url: str, name: str) -> bool:
    """Check that a LinkedIn URL likely belongs to this person.

    Requires last name match (or first name if only one name part).
    For multi-word names, at least 2 parts must match.
    """
    if not url or not name:
        return False
    slug = url.split('/in/')[-1].lower().rstrip('/')
    # Remove trailing numbers/hashes from slug for matching
    slug_clean = re.sub(r'-[0-9a-f]{6,}$', '', slug)

    name_parts = [p.lower() for p in name.split() if len(p) > 1]
    if not name_parts:
        return False

    matches = sum(1 for part in name_parts if part in slug_clean)

    if len(name_parts) == 1:
        # Single name: must match
        return matches >= 1
    elif len(name_parts) == 2:
        # First + Last: both should match, or at least last name
        last = name_parts[-1]
        first = name_parts[0]
        # Last name must always match
        if last not in slug_clean:
            return False
        # First name should also match (or first 3 chars)
        return first in slug_clean or first[:3] in slug_clean
    else:
        # 3+ parts (e.g., "Ronald Harris-White II"): at least 2 must match
        return matches >= 2


# ─── Tavily Search ──────────────────────────────────────────────────────────

def find_linkedin_tavily(name: str, company: str = "", location: str = "", email: str = "") -> str | None:
    """Search Tavily for LinkedIn profile. Returns URL or None."""
    key = get_tavily_key()
    if not key:
        return None

    # Build targeted query — don't use site: operator, use include_domains instead
    query_parts = [f'"{name}"']
    if company:
        query_parts.append(f'"{company}"')
    if location:
        city = location.split('(')[0].strip() if '(' in location else location
        if city:
            query_parts.append(city)

    query = " ".join(query_parts)

    try:
        response = requests.post(
            'https://api.tavily.com/search',
            json={
                'api_key': key,
                'query': query,
                'search_depth': 'basic',
                'max_results': 5,
                'include_answer': False,
                'include_domains': ['linkedin.com']
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"      Tavily: {len(results)} results")
            for r in results:
                url = r.get('url', '')
                title = r.get('title', '')[:80]
                print(f"        → {url[:80]} | {title}")
                li_url = extract_linkedin_url(url)
                if li_url and validate_linkedin_for_person(li_url, name):
                    return li_url
            # Check content of results for embedded LinkedIn URLs
            for r in results:
                content = r.get('content', '')
                li_url = extract_linkedin_url(content)
                if li_url and validate_linkedin_for_person(li_url, name):
                    return li_url
            return None

        elif response.status_code in (429, 432):
            idx = (current_tavily_idx - 1) % len(TAVILY_KEYS)
            exhausted_tavily.add(idx)
            print(f"    Tavily key {idx+1} exhausted ({response.status_code}), rotating...")
            # Retry with next key
            return find_linkedin_tavily(name, company, location, email)
        else:
            print(f"    Tavily error: {response.status_code}")
            return None
    except Exception as e:
        print(f"    Tavily exception: {e}")
        return None


# ─── Perplexity Search ──────────────────────────────────────────────────────

def find_linkedin_perplexity(name: str, company: str = "", location: str = "", bio: str = "") -> str | None:
    """Ask Perplexity sonar to find LinkedIn profile URL."""
    if not PERPLEXITY_KEY:
        return None

    context_parts = [f"Name: {name}"]
    if company:
        context_parts.append(f"Company: {company}")
    if location:
        context_parts.append(f"Location: {location}")
    if bio:
        context_parts.append(f"Bio: {bio[:100]}")

    context = "\n".join(context_parts)

    try:
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers={
                'Authorization': f'Bearer {PERPLEXITY_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'sonar',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert at finding people\'s LinkedIn profiles. Search the web thoroughly. Return the LinkedIn profile URL in the format https://www.linkedin.com/in/slug — or "NOT_FOUND" if you truly cannot find it. Return ONLY the URL or NOT_FOUND, nothing else.'
                    },
                    {
                        'role': 'user',
                        'content': f"Find the LinkedIn profile for this person. Search linkedin.com thoroughly:\n{context}\n\nRespond with ONLY the LinkedIn URL (https://www.linkedin.com/in/...) or NOT_FOUND."
                    }
                ],
                'max_tokens': 100,
                'temperature': 0.1
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"      Perplexity raw: {text[:200]}")
            if 'NOT_FOUND' in text.upper():
                return None
            li_url = extract_linkedin_url(text)
            if li_url:
                if validate_linkedin_for_person(li_url, name):
                    return li_url
                else:
                    # Perplexity is usually accurate — accept if it found a specific URL
                    # (not a directory/search page) even if name validation fails
                    if '/pub/dir/' not in li_url and '/directory/' not in li_url:
                        print(f"      Perplexity override (trusted): {li_url}")
                        return li_url
                    print(f"      Validation failed for {li_url} (name: {name})")
                    return None
            return None

        elif response.status_code == 429:
            print(f"    Perplexity rate limited, waiting 10s...")
            time.sleep(10)
            return None
        else:
            print(f"    Perplexity error: {response.status_code}")
            return None
    except Exception as e:
        print(f"    Perplexity exception: {e}")
        return None


# ─── Exa Search ─────────────────────────────────────────────────────────────

def find_linkedin_exa(name: str, company: str = "", bio: str = "") -> str | None:
    """Use Exa neural search to find LinkedIn profile."""
    key = get_exa_key()
    if not key:
        return None

    query = f"{name} LinkedIn profile"
    if company:
        query += f" {company}"

    try:
        response = requests.post(
            'https://api.exa.ai/search',
            headers={
                'x-api-key': key,
                'Content-Type': 'application/json'
            },
            json={
                'query': query,
                'numResults': 5,
                'type': 'neural',
                'useAutoprompt': True,
                'includeDomains': ['linkedin.com']
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            for r in results:
                url = r.get('url', '')
                li_url = extract_linkedin_url(url)
                if li_url and validate_linkedin_for_person(li_url, name):
                    return li_url
            return None

        elif response.status_code == 429:
            idx = (current_exa_idx - 1) % len(EXA_KEYS)
            exhausted_exa.add(idx)
            print(f"    Exa key {idx+1} exhausted, rotating...")
            return find_linkedin_exa(name, company, bio)
        else:
            print(f"    Exa error: {response.status_code}")
            return None
    except Exception as e:
        print(f"    Exa exception: {e}")
        return None


# ─── Apollo Lookup ──────────────────────────────────────────────────────────

def find_linkedin_apollo(name: str, email: str = "", company: str = "") -> str | None:
    """Use Apollo people search to find LinkedIn URL. Last resort (finite credits)."""
    if not APOLLO_KEY:
        return None

    # Apollo people/match endpoint — matches by email (most reliable)
    if email:
        try:
            response = requests.post(
                'https://api.apollo.io/v1/people/match',
                headers={
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache'
                },
                json={
                    'api_key': APOLLO_KEY,
                    'email': email
                },
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                person = data.get('person', {})
                li_url = person.get('linkedin_url', '')
                if li_url:
                    return li_url
        except Exception as e:
            print(f"    Apollo exception: {e}")

    # Fallback: Apollo people/search by name + company
    if name:
        try:
            search_params = {
                'api_key': APOLLO_KEY,
                'q_person_name': name,
                'per_page': 3
            }
            if company:
                search_params['q_organization_name'] = company

            response = requests.post(
                'https://api.apollo.io/v1/mixed_people/search',
                headers={'Content-Type': 'application/json'},
                json=search_params,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                people = data.get('people', [])
                for p in people:
                    li_url = p.get('linkedin_url', '')
                    if li_url and validate_linkedin_for_person(li_url, name):
                        return li_url
        except Exception as e:
            print(f"    Apollo search exception: {e}")

    return None


# ─── Main Pipeline ──────────────────────────────────────────────────────────

def find_linkedin_for_member(member: dict, skip_apollo: bool = False) -> dict:
    """Run waterfall chain to find LinkedIn for one member. Returns updated member dict."""
    name = member.get('name', '')
    email = member.get('email', '')
    location = member.get('location', '')
    bio = member.get('bio', '')
    website = member.get('website', '')

    # Already has LinkedIn from Skool profile
    existing = member.get('linkedin', '')
    if existing and 'linkedin.com/in/' in existing.lower():
        return {**member, 'linkedin_source': 'skool_profile'}

    # Try to infer company from bio or website
    company = ""
    if website:
        # Extract domain as company hint
        domain = website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
        company = domain.split('.')[0] if domain else ""

    linkedin_url = None
    source = None

    # 1. Tavily (renewable, 6 keys)
    print(f"    [Tavily] Searching...")
    rate_limit_check()
    linkedin_url = find_linkedin_tavily(name, company, location, email)
    if linkedin_url:
        source = "tavily"
    else:
        # 2. Perplexity (pay-as-you-go)
        print(f"    [Perplexity] Searching...")
        rate_limit_check()
        linkedin_url = find_linkedin_perplexity(name, company, location, bio)
        if linkedin_url:
            source = "perplexity"
        else:
            # 3. Exa (renewable, 6 keys)
            print(f"    [Exa] Searching...")
            rate_limit_check()
            linkedin_url = find_linkedin_exa(name, company, bio)
            if linkedin_url:
                source = "exa"
            elif not skip_apollo and (email or company):
                # 4. Apollo (finite — last resort)
                print(f"    [Apollo] Searching...")
                rate_limit_check()
                linkedin_url = find_linkedin_apollo(name, email, company)
                if linkedin_url:
                    source = "apollo"

    result = {**member}
    if linkedin_url:
        result['linkedin'] = linkedin_url
        result['linkedin_source'] = source
        print(f"    ✓ Found via {source}: {linkedin_url}")
    else:
        result['linkedin_source'] = 'not_found'
        print(f"    ✗ Not found")

    return result


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_checkpoint(results: list, last_index: int):
    checkpoint = {
        'last_index': last_index,
        'count': len(results),
        'saved_at': datetime.now().isoformat(),
        'results': results
    }
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Find LinkedIn profiles for Skool members")
    parser.add_argument('--input', type=str, default=str(DEFAULT_INPUT), help='Input JSON file')
    parser.add_argument('--limit', type=int, default=0, help='Limit to first N members (0=all)')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--skip-apollo', action='store_true', help='Skip Apollo (save finite credits)')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        members = json.load(f)

    if args.limit > 0:
        members = members[:args.limit]

    # Resume from checkpoint
    start_idx = 0
    results = []
    if args.resume:
        cp = load_checkpoint()
        if cp:
            start_idx = cp['last_index'] + 1
            results = cp['results']
            print(f"Resuming from member #{start_idx + 1} ({len(results)} already processed)")

    # Skip members that already have LinkedIn from Skool
    already_have = sum(1 for m in members if m.get('linkedin', '').strip())
    need_lookup = sum(1 for m in members[start_idx:] if not m.get('linkedin', '').strip())

    print(f"""
{'='*60}
LINKEDIN PROFILE FINDER
{'='*60}
  Input:          {input_path.name}
  Total members:  {len(members)}
  Already have:   {already_have} (from Skool profiles)
  Need lookup:    {need_lookup}
  Chain:          Tavily → Perplexity → Exa{' → Apollo' if not args.skip_apollo else ' (Apollo skipped)'}
  Tavily keys:    {len(TAVILY_KEYS)} available
  Exa keys:       {len(EXA_KEYS)} available
  Apollo:         {'configured' if APOLLO_KEY else 'not configured'}
{'='*60}
""")

    found_count = 0
    skool_count = 0

    for i in range(start_idx, len(members)):
        m = members[i]
        name = m.get('name', m.get('handle', ''))
        existing_li = m.get('linkedin', '').strip()

        print(f"\n[{i+1}/{len(members)}] {name}")

        if existing_li and 'linkedin.com' in existing_li.lower():
            print(f"    ✓ Already has LinkedIn (Skool profile): {existing_li}")
            results.append({**m, 'linkedin_source': 'skool_profile'})
            skool_count += 1
            found_count += 1
        else:
            result = find_linkedin_for_member(m, skip_apollo=args.skip_apollo)
            results.append(result)
            if result.get('linkedin_source') not in ('not_found', None):
                found_count += 1

        # Checkpoint every 10
        if (i + 1) % 10 == 0:
            save_checkpoint(results, i)
            print(f"\n  [Checkpoint] Saved at member #{i+1}")

    # Save final output
    TMP_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Clean up checkpoint
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

    # Summary
    sources = {}
    for r in results:
        src = r.get('linkedin_source', 'not_found')
        sources[src] = sources.get(src, 0) + 1

    print(f"""
{'='*60}
RESULTS SUMMARY
{'='*60}
  Total processed: {len(results)}
  LinkedIn found:  {found_count} ({found_count*100//max(len(results),1)}%)
  Not found:       {len(results) - found_count}

  By source:
    Skool profile:  {sources.get('skool_profile', 0)}
    Tavily:         {sources.get('tavily', 0)}
    Perplexity:     {sources.get('perplexity', 0)}
    Exa:            {sources.get('exa', 0)}
    Apollo:         {sources.get('apollo', 0)}

  Output: {OUTPUT_FILE}
{'='*60}
""")


if __name__ == '__main__':
    main()
