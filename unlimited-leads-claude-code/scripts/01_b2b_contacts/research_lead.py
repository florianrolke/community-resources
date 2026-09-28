#!/usr/bin/env python3
"""
Research each lead and return 5 facts, each with a source.

This is the n8n `AI Agent1` node and its three tool connections (Tavily search,
website fetch, LinkedIn scrape), rebuilt as one tool-use loop. The system prompt
is Jack's, word for word — see prompts/research_agent.md.

The point of this step is to find a trigger event: something that recently
happened at the company, so your opening line can be specific instead of
"I came across your website". Everything downstream depends on it. A lead with
no facts gets flagged rather than given a generic opener.

Two things this has that the canvas version didn't:

  - A hard cap on tool calls per lead (--max-tool-calls, default 8). An n8n
    agent can loop until your Tavily quota is gone. This one can't.
  - Checkpointing. Stop it at lead 400 of 1,000 and --resume picks up at 401
    instead of paying for the first 400 again.

Usage:
    python -X utf8 scripts/01_b2b_contacts/research_lead.py \\
        --input output/leads.json --output output/researched.json --limit 10

Cost: roughly $0.01-0.03 per lead, plus Tavily (free tier: 1,000/month).
"""

import os
import sys
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from scripts.lib.env import load_env, get, require
from scripts.lib.windows_compat import fix_encoding
from scripts.lib.output import read_any, write_json, write_csv
from scripts.lib.claude import get_client, load_prompt, DEFAULT_MODEL
from scripts.lib.checkpoint import CheckpointManager

fix_encoding()
load_env()

# The `Output` node's schema from the n8n workflow: five facts, five sources.
SCHEMA = {
    "type": "object",
    "properties": {
        **{f"fact{i}": {"type": "string"} for i in range(1, 6)},
        **{f"explanation{i}": {"type": "string"} for i in range(1, 6)},
    },
    "required": [f"fact{i}" for i in range(1, 6)] + [f"explanation{i}" for i in range(1, 6)],
    "additionalProperties": False,
}

TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for recent news about a person or company. Use this first — "
            "it's how you find funding rounds, launches, hires, awards, and expansions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fetch_website",
        "description": (
            "Fetch and read a web page. Use it on the company's site — the blog, news, "
            "or press page is usually where recent announcements live."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Full URL including https://"}},
            "required": ["url"],
            "additionalProperties": False,
        },
    },
]


def tavily_search(query: str, max_results: int = 5) -> str:
    """Search via Tavily. Rotates across TAVILY_API_KEY, _2, _3... when one is exhausted."""
    import requests

    keys = [k for k in
            [get("TAVILY_API_KEY")] + [get(f"TAVILY_API_KEY_{i}") for i in range(2, 11)]
            if k]
    if not keys:
        return "No Tavily API key configured. Add TAVILY_API_KEY to .env (free at tavily.com)."

    for key in keys:
        try:
            r = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "include_answer": True,
                },
                timeout=30,
            )
            if r.status_code in (401, 429):
                continue  # key exhausted or invalid — try the next one
            r.raise_for_status()
            data = r.json()

            lines = []
            if data.get("answer"):
                lines.append(f"Summary: {data['answer']}\n")
            for item in data.get("results", []):
                lines.append(f"- {item.get('title','')}\n  {item.get('url','')}\n  {item.get('content','')[:400]}")
            return "\n".join(lines) or "No results found."
        except Exception as e:
            last = str(e)
            continue
    return f"All Tavily keys failed or are exhausted. Last error: {last if 'last' in dir() else 'rate limited'}"


def fetch_website(url: str, max_chars: int = 8000) -> str:
    """Fetch a page and return readable text."""
    import httpx
    import html2text

    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        with httpx.Client(follow_redirects=True, timeout=20,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; lead-research/1.0)"}) as c:
            r = c.get(url)
            r.raise_for_status()
        h = html2text.HTML2Text()
        h.ignore_images = True
        h.ignore_links = True
        return h.handle(r.text)[:max_chars]
    except Exception as e:
        # A dead site is normal — roughly one business in seven blocks scrapers.
        return f"Could not fetch {url}: {e}"


def research_one(lead: dict, model: str = DEFAULT_MODEL, max_tool_calls: int = 8) -> dict:
    """Run the research agent for one lead. Returns the lead plus fact1..5 / explanation1..5."""
    client = get_client()
    system, _ = load_prompt("research_agent")

    company = lead.get("company") or lead.get("business_name") or ""
    person = lead.get("name") or f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()
    website = lead.get("company_website") or lead.get("website") or ""

    user = "\n".join(filter(None, [
        f"Company name: {company}" if company else "",
        f"Prospect name: {person}" if person else "",
        f"Job title: {lead.get('job_title','')}" if lead.get("job_title") else "",
        f"Company website: {website}" if website else "",
        f"LinkedIn: {lead.get('linkedin','')}" if lead.get("linkedin") else "",
        f"Location: {lead.get('location','')}" if lead.get("location") else "",
        "",
        "Research this prospect and return exactly five facts, each with its source.",
    ]))

    messages = [{"role": "user", "content": user}]
    calls = 0

    while calls < max_tool_calls:
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            calls += 1
            if block.name == "web_search":
                out = tavily_search(block.input.get("query", ""))
            elif block.name == "fetch_website":
                out = fetch_website(block.input.get("url", ""))
            else:
                out = f"Unknown tool: {block.name}"
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        messages.append({"role": "user", "content": results})

    # Final pass: make it commit to the five-facts schema.
    messages.append({
        "role": "user",
        "content": "Now give me the five facts and their sources in the required format.",
    })
    final = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=messages,
    )

    if final.stop_reason == "refusal":
        return {**lead, "_research_error": "refused", "needs_research": True}

    text = next((b.text for b in final.content if b.type == "text"), "{}")
    facts = json.loads(text)

    found = sum(1 for i in range(1, 6) if (facts.get(f"fact{i}") or "").strip())
    return {
        **lead,
        **facts,
        "facts_found": found,
        # The outreach step reads this. No facts means no honest opener.
        "needs_research": found == 0,
        "_tool_calls": calls,
    }


def main():
    parser = argparse.ArgumentParser(description="Research leads and extract 5 facts each (System 1, step 2)")
    parser.add_argument("--input", required=True, help="Input leads JSON or CSV")
    parser.add_argument("--output", help="Output JSON (default: <input>_researched.json)")
    parser.add_argument("--out-csv", dest="out_csv", help="Also write a CSV here")
    parser.add_argument("--limit", type=int, help="Only process the first N leads")
    parser.add_argument("--workers", type=int, default=3, help="Parallel leads (default: 3)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-tool-calls", dest="max_tool_calls", type=int, default=8,
                        help="Cap tool calls per lead so a stuck lead can't drain your quota (default: 8)")
    parser.add_argument("--resume", action="store_true", help="Continue from the last checkpoint")
    args = parser.parse_args()

    leads = read_any(args.input)
    if args.limit:
        leads = leads[:args.limit]

    out_path = args.output or args.input.rsplit(".", 1)[0] + "_researched.json"

    def lead_key(l: dict) -> str:
        return l.get("linkedin") or l.get("name") or l.get("company") or json.dumps(l, sort_keys=True)[:80]

    ckpt_name = f"research_{os.path.basename(args.input).rsplit('.', 1)[0]}"
    if not args.resume:
        # Fresh run: drop any checkpoint from a previous run of this input.
        stale = Path(".tmp") / f"checkpoint_{ckpt_name}.json"
        if stale.exists():
            stale.unlink()
    ckpt = CheckpointManager(ckpt_name)

    todo = [l for l in leads if not ckpt.is_done(lead_key(l))]
    already = len(leads) - len(todo)
    if already:
        print(f"Resuming: {already} already done, {len(todo)} to go")
    print(f"Researching {len(todo)} leads with {args.workers} workers...")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(research_one, l, args.model, args.max_tool_calls): l for l in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            lead = futures[fut]
            label = (lead.get("company") or lead.get("name") or "?")[:38]
            try:
                r = fut.result()
                flag = "" if not r.get("needs_research") else "  [no facts found]"
                print(f"  [{i}/{len(todo)}] {label} — {r.get('facts_found',0)} facts{flag}")
            except Exception as e:
                print(f"  [{i}/{len(todo)}] {label} — FAILED: {e}")
                r = {**lead, "_research_error": str(e), "needs_research": True}
            ckpt.save_result(lead_key(lead), r)

    ckpt.finalize()
    results = list(ckpt.results.values())
    write_json(results, out_path)
    print(f"\nSaved to {out_path}")
    if args.out_csv:
        write_csv(results, args.out_csv)
        print(f"CSV saved to {args.out_csv}")

    usable = sum(1 for r in results if not r.get("needs_research"))
    print(f"{usable}/{len(results)} leads have facts and are ready for outreach.")
    print("\nNext: write the outreach ->")
    print(f"  python -X utf8 scripts/04_outreach/write_outreach.py --input {out_path}")


if __name__ == "__main__":
    main()
