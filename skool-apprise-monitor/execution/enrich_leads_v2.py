#!/usr/bin/env python3
"""
Lead Enrichment v2 - Multi-Source Layered Approach

Sources (in priority order):
1. Perplexity - Best for deep research, good at synthesizing info ($24 credits)
2. Tavily - Good search, 1000 free/month, includes AI answer
3. Exa AI - Neural/semantic search, great for finding specific people

Strategy:
- Use Perplexity first (best quality)
- If low confidence, try Exa AI (semantic search)
- If still low, try Tavily (keyword search)
- For leads WITH LinkedIn URLs, we get much better results

Usage:
    python execution/enrich_leads_v2.py --input .tmp/leads.json --output .tmp/enriched.json
    python execution/enrich_leads_v2.py --test  # First 3 leads
    python execution/enrich_leads_v2.py --batch 50  # Process 50 leads
    python execution/enrich_leads_v2.py --start 100 --batch 50  # Resume from lead 100
"""

import os
import sys
import json
import argparse
import time
import re
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

# =============================================================================
# CLIENT INITIALIZATION
# =============================================================================

def create_perplexity_client():
    """Create Perplexity client using OpenAI SDK."""
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    except ImportError:
        os.system("pip install openai")
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")


def create_tavily_client():
    """Create Tavily client (1,000 free searches/month)."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    try:
        from tavily import TavilyClient
        return TavilyClient(api_key=api_key)
    except ImportError:
        os.system("pip install tavily-python")
        from tavily import TavilyClient
        return TavilyClient(api_key=api_key)


def create_exa_client():
    """Create Exa AI client for semantic search."""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return None
    try:
        from exa_py import Exa
        return Exa(api_key=api_key)
    except ImportError:
        os.system("pip install exa-py")
        from exa_py import Exa
        return Exa(api_key=api_key)


# =============================================================================
# ENRICHMENT FUNCTIONS
# =============================================================================

def enrich_with_perplexity(client, name, linkedin_url=None, website=None, notes=None):
    """
    Use Perplexity for deep research. Best quality results.
    """
    if not client:
        return None

    # Build rich context
    context_parts = []
    if linkedin_url:
        context_parts.append(f"LinkedIn: {linkedin_url}")
    if website:
        context_parts.append(f"Website: {website}")
    if notes:
        context_parts.append(f"Context: {notes}")

    context = "\n".join(context_parts) if context_parts else "No additional context"

    prompt = f"""Research this person and extract business intelligence:

Name: {name}
{context}

Return ONLY valid JSON (no markdown, no explanation):
{{
    "full_name": "their full name",
    "location": {{
        "city": "city or null",
        "country": "country or null",
        "timezone": "timezone or null"
    }},
    "current_role": "job title",
    "company_name": "company name",
    "company_description": "what their company does (1-2 sentences)",
    "services": ["service 1", "service 2"],
    "industries": ["industry 1", "industry 2"],
    "pricing": "pricing info or 'Not public'",
    "calendar_link": "booking URL or null",
    "website": "personal/business website or null",
    "email": "email if found or null",
    "phone": "phone if found or null",
    "linkedin_url": "linkedin URL or null",
    "recent_activity": "recent posts, news, or mentions",
    "confidence": "high/medium/low"
}}"""

    try:
        response = client.chat.completions.create(
            model="sonar",
            messages=[
                {"role": "system", "content": "Extract business intelligence. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1500
        )

        content = response.choices[0].message.content

        # Clean up response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        result["source"] = "perplexity"
        return result

    except json.JSONDecodeError as e:
        return {"raw_response": content, "parse_error": str(e), "confidence": "low", "source": "perplexity"}
    except Exception as e:
        print(f"    Perplexity error: {e}")
        return None


def enrich_with_exa(client, name, linkedin_url=None, website=None):
    """
    Use Exa AI for semantic search. Great for finding specific people.
    """
    if not client:
        return None

    # Build search query
    if linkedin_url:
        # Search for content about this LinkedIn profile
        query = f"{name} {linkedin_url.split('/')[-1].replace('-', ' ')}"
    else:
        query = f"{name} founder CEO services"

    try:
        # Use Exa's search with contents
        results = client.search_and_contents(
            query=query,
            type="neural",
            num_results=5,
            text={"max_characters": 1000}
        )

        # Extract info from results
        services = []
        industries = []
        location = {"city": None, "country": None, "timezone": None}
        company_info = None
        websites_found = []

        for result in results.results:
            text = (result.text or "").lower()
            url = result.url or ""
            title = result.title or ""

            websites_found.append(url)

            # Extract services
            service_keywords = ["automation", "ai agent", "consulting", "marketing", "development",
                              "design", "coaching", "training", "lead generation", "voice ai",
                              "chatbot", "workflow", "integration"]
            for kw in service_keywords:
                if kw in text and kw not in services:
                    services.append(kw)

            # Try to extract location
            loc_patterns = [r'based in ([A-Za-z\s,]+)', r'located in ([A-Za-z\s,]+)', r'from ([A-Za-z\s,]+)']
            for pattern in loc_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match and not location["city"]:
                    loc = match.group(1).strip()[:50]
                    location["city"] = loc

            # Extract company info from title/text
            if not company_info and name.lower() in text:
                company_info = title[:100] if title else None

        return {
            "services": list(set(services))[:10],
            "industries": list(set(industries))[:5],
            "location": location,
            "company_name": company_info,
            "websites_found": websites_found[:3],
            "source": "exa",
            "confidence": "medium" if services or location["city"] else "low"
        }

    except Exception as e:
        print(f"    Exa error: {e}")
        return None


def enrich_with_tavily(client, name, linkedin_url=None, website=None):
    """
    Use Tavily for keyword search with AI answer synthesis.
    """
    if not client:
        return None

    # Build search query
    query_parts = [f'"{name}"']
    if linkedin_url:
        username = linkedin_url.split("/in/")[-1].rstrip("/")
        query_parts.append(username)
    if website:
        domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        query_parts.append(f"site:{domain}")
    query_parts.append("services OR pricing OR founder OR CEO")

    query = " ".join(query_parts)

    try:
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True
        )

        ai_answer = response.get("answer", "")

        # Extract data from results
        services = []
        pricing_mentions = []
        contact_info = []
        urls_found = []
        location = {"city": None, "country": None, "timezone": None}

        for result in response.get("results", []):
            content = result.get("content", "").lower()
            url = result.get("url", "")
            urls_found.append(url)

            # Services
            service_keywords = ["automation", "ai agent", "consulting", "marketing", "development",
                              "design", "coaching", "training", "lead generation", "voice ai"]
            for kw in service_keywords:
                if kw in content and kw not in services:
                    services.append(kw)

            # Pricing
            prices = re.findall(r'\$[\d,]+(?:\s*/\s*(?:mo|month|hr|hour))?', content)
            pricing_mentions.extend(prices)

            # Contact info (Chase's schema hack)
            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
            phones = re.findall(r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{3,4}[-\s\.]?[0-9]{3,4}', content)
            contact_info.extend(emails + phones)

        # Extract location from AI answer
        if ai_answer:
            for pattern in [r'based in ([A-Za-z\s,]+)', r'located in ([A-Za-z\s,]+)', r'from ([A-Za-z\s,]+)']:
                match = re.search(pattern, ai_answer, re.IGNORECASE)
                if match:
                    location["city"] = match.group(1).strip()[:50]
                    break

        return {
            "services": list(set(services))[:10],
            "pricing": list(set(pricing_mentions))[:5],
            "contact_info": list(set(contact_info))[:3],
            "location": location,
            "ai_summary": ai_answer[:500] if ai_answer else None,
            "sources": urls_found[:3],
            "source": "tavily",
            "confidence": "high" if ai_answer and (services or location["city"]) else "medium" if ai_answer else "low"
        }

    except Exception as e:
        print(f"    Tavily error: {e}")
        return None


# =============================================================================
# MAIN ENRICHMENT LOGIC
# =============================================================================

def merge_enrichments(results):
    """Merge results from multiple sources, preferring higher confidence data."""
    merged = {
        "location": {"city": None, "country": None, "timezone": None},
        "services": [],
        "industries": [],
        "pricing": None,
        "calendar_link": None,
        "company_name": None,
        "company_description": None,
        "website": None,
        "email": None,
        "phone": None,
        "linkedin_url": None,
        "recent_activity": None,
        "sources_used": [],
        "confidence": "low"
    }

    confidence_order = {"high": 3, "medium": 2, "low": 1}

    for result in results:
        if not result:
            continue

        source = result.get("source", "unknown")
        merged["sources_used"].append(source)

        # Update confidence
        result_conf = result.get("confidence", "low")
        if confidence_order.get(result_conf, 0) > confidence_order.get(merged["confidence"], 0):
            merged["confidence"] = result_conf

        # Merge location
        if result.get("location"):
            loc = result["location"]
            if loc.get("city") and not merged["location"]["city"]:
                merged["location"] = loc

        # Merge lists
        merged["services"].extend(result.get("services", []))
        merged["industries"].extend(result.get("industries", []))

        # Merge single values (first non-null wins)
        for key in ["company_name", "company_description", "website", "calendar_link",
                    "email", "phone", "linkedin_url", "recent_activity", "pricing",
                    "full_name", "current_role"]:
            if result.get(key) and not merged.get(key):
                merged[key] = result[key]

        # Contact info from Tavily
        if result.get("contact_info"):
            for info in result["contact_info"]:
                if "@" in info and not merged["email"]:
                    merged["email"] = info
                elif not merged["phone"] and any(c.isdigit() for c in info):
                    merged["phone"] = info

    # Deduplicate lists
    merged["services"] = list(set(merged["services"]))[:15]
    merged["industries"] = list(set(merged["industries"]))[:10]

    return merged


def enrich_single_lead(clients, lead):
    """
    Enrich a single lead using all available sources.
    """
    perplexity, tavily, exa = clients

    # Extract lead info
    name = lead.get("name") or f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
    linkedin_url = lead.get("linkedin_url")
    websites = lead.get("websites", lead.get("known_websites", []))
    website = websites[0] if websites else None
    notes = lead.get("notes", "")

    print(f"  {name}...", end="", flush=True)

    results = []

    # 1. Try Perplexity first (best quality)
    if perplexity:
        result = enrich_with_perplexity(perplexity, name, linkedin_url, website, notes)
        if result:
            results.append(result)
            if result.get("confidence") == "high":
                print(f" [Perplexity: high]")
                # High confidence from Perplexity is enough
                merged = merge_enrichments(results)
                return create_lead_result(lead, name, linkedin_url, websites, notes, merged)

    # 2. Try Exa AI (semantic search)
    if exa:
        result = enrich_with_exa(exa, name, linkedin_url, website)
        if result:
            results.append(result)

    # 3. Try Tavily (keyword search + AI answer)
    if tavily:
        result = enrich_with_tavily(tavily, name, linkedin_url, website)
        if result:
            results.append(result)

    # Merge all results
    merged = merge_enrichments(results)

    confidence = merged.get("confidence", "low")
    sources = ", ".join(merged.get("sources_used", []))
    print(f" [{sources}: {confidence}]")

    return create_lead_result(lead, name, linkedin_url, websites, notes, merged)


def create_lead_result(lead, name, linkedin_url, websites, notes, enrichment):
    """Create the final lead result object."""
    return {
        "name": name,
        "linkedin_url": linkedin_url or enrichment.get("linkedin_url"),
        "skool_url": lead.get("skool_url"),
        "websites": websites,
        "original_notes": notes,
        "enrichment": enrichment,
        "enriched_at": datetime.now().isoformat()
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Multi-source lead enrichment")
    parser.add_argument("--input", "-i", default=".tmp/mike_leads_raw.json",
                        help="Input JSON file with leads")
    parser.add_argument("--output", "-o", default=".tmp/enriched_v2.json",
                        help="Output JSON file")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: process first 3 leads")
    parser.add_argument("--batch", type=int, default=None,
                        help="Process N leads (for batch runs)")
    parser.add_argument("--start", type=int, default=0,
                        help="Start from lead index (for resuming)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay between leads (seconds)")

    args = parser.parse_args()

    # Initialize clients
    print("Initializing API clients...")
    perplexity = create_perplexity_client()
    tavily = create_tavily_client()
    exa = create_exa_client()

    clients = (perplexity, tavily, exa)

    print(f"  Perplexity: {'Ready' if perplexity else 'Not configured'}")
    print(f"  Tavily: {'Ready' if tavily else 'Not configured'}")
    print(f"  Exa AI: {'Ready' if exa else 'Not configured'}")

    if not any(clients):
        print("Error: No API clients available!")
        sys.exit(1)

    # Load leads
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            leads = data
        elif "leads" in data:
            leads = data["leads"]
        else:
            leads = [data]

        print(f"\nLoaded {len(leads)} leads from {args.input}")
    except FileNotFoundError:
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Apply filters
    if args.test:
        leads = leads[:3]
        print("TEST MODE: Processing first 3 leads")
    elif args.batch:
        end = args.start + args.batch
        leads = leads[args.start:end]
        print(f"BATCH MODE: Processing leads {args.start} to {end}")
    elif args.start > 0:
        leads = leads[args.start:]
        print(f"Resuming from lead {args.start}")

    # Process leads
    print(f"\n{'='*60}")
    print(f"Enriching {len(leads)} leads")
    print(f"{'='*60}\n")

    enriched_leads = []

    for i, lead in enumerate(leads):
        print(f"[{i+1}/{len(leads)}]", end="")

        try:
            result = enrich_single_lead(clients, lead)
            enriched_leads.append(result)
        except Exception as e:
            print(f" ERROR: {e}")
            enriched_leads.append({
                "name": lead.get("name", "Unknown"),
                "error": str(e),
                "enriched_at": datetime.now().isoformat()
            })

        # Rate limiting
        if i < len(leads) - 1:
            time.sleep(args.delay)

    # Save results
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    # Calculate summary
    summary = {
        "high_confidence": sum(1 for l in enriched_leads if l.get("enrichment", {}).get("confidence") == "high"),
        "medium_confidence": sum(1 for l in enriched_leads if l.get("enrichment", {}).get("confidence") == "medium"),
        "low_confidence": sum(1 for l in enriched_leads if l.get("enrichment", {}).get("confidence") == "low"),
        "errors": sum(1 for l in enriched_leads if l.get("error"))
    }

    output_data = {
        "generated_at": datetime.now().isoformat(),
        "source_file": args.input,
        "total_processed": len(enriched_leads),
        "leads": enriched_leads,
        "summary": summary
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Enrichment Complete!")
    print(f"{'='*60}")
    print(f"Saved to: {args.output}")
    print(f"\nSummary:")
    print(f"  High confidence: {summary['high_confidence']}")
    print(f"  Medium confidence: {summary['medium_confidence']}")
    print(f"  Low confidence: {summary['low_confidence']}")
    print(f"  Errors: {summary['errors']}")


if __name__ == "__main__":
    main()
