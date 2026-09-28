"""
skool_message_drafter_v2.py — Personalized Message Drafter

Generates a short, personalized DM draft for qualified new/churn-risk members.
Uses Claude claude-haiku-4-5 (cost-efficient) with:
  1. Enrichment context (who they serve, what they offer, industry)
  2. Up to 2 relevant community posts (from Supabase vector search)
  3. Join/churn-risk context
  4. Tone template from tenant config

Sends the draft via email to Florian (draft_email_to_florian mode).

Usage:
  python execution/skool_message_drafter_v2.py --member .tmp/test_member.json --tenant aiautomationsbyjack --dry-run
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
EXECUTION_DIR = Path(__file__).parent

sys.path.insert(0, str(EXECUTION_DIR))


def search_relevant_posts(member: dict, table: str, max_results: int = 2) -> list:
    """
    Find community posts semantically relevant to this member's profile.
    Uses Supabase pgvector search (same approach as querying existing leads).

    Returns list of post dicts [{title, content, authorName, postUrl}]
    """
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        import openai
        from supabase import create_client

        client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY"),
        )
        oai = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Embed member bio + enrichment summary
        bio = member.get("bio", "")
        enrichment = member.get("enrichment", {})
        services = ", ".join(enrichment.get("services", []))
        text_to_embed = f"{bio} {services}"[:1000]

        if not text_to_embed.strip():
            return []

        resp = oai.embeddings.create(
            model="text-embedding-3-small",
            input=text_to_embed,
        )
        embedding = resp.data[0].embedding

        results = client.rpc(
            "match_posts",
            {"query_embedding": embedding, "match_count": max_results, "table_name": table},
        ).execute()

        if results.data:
            return [
                {
                    "title": r.get("title", ""),
                    "content": (r.get("content", "") or "")[:300],
                    "authorName": r.get("authorName", ""),
                    "postUrl": r.get("postUrl", ""),
                }
                for r in results.data
            ]
    except Exception as e:
        print(f"  Post search error: {e}")

    return []


def draft_message(member: dict, signal_type: str, relevant_posts: list, config: dict) -> str:
    """
    Generate personalized DM draft using Claude haiku.

    Args:
        member: Enriched + scored member dict
        signal_type: "new_qualified_member" or "churn_qualified_member"
        relevant_posts: List of relevant post dicts from community
        config: Tenant config

    Returns:
        Draft DM text (3-4 sentences)
    """
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        name = member.get("name", "").split()[0] if member.get("name") else "there"
        bio = member.get("bio", "")
        enrichment = member.get("enrichment", {})
        community = member.get("community", config["community_slug"])

        services = ", ".join(enrichment.get("services", [])[:3])
        industries = ", ".join(enrichment.get("industries", [])[:2])
        company = enrichment.get("company_name", "")
        linkedin = member.get("linkedin", "")

        is_churn = signal_type == "churn_qualified_member"
        days_absent = member.get("days_absent", 0) if is_churn else 0

        if is_churn:
            context_note = f"This member joined but hasn't been active for {days_absent} days — at churn risk."
        else:
            context_note = "This member just joined the community."

        posts_context = ""
        if relevant_posts:
            posts_context = "\n\nRelevant community posts (use 1 if natural):\n" + "\n".join(
                f"- '{p['title']}' by {p['authorName']}: {p['content'][:150]}"
                for p in relevant_posts
            )

        tone_template = config.get("messaging", {}).get(
            "tone_template",
            "Direct, warm, curious — never salesy. 3-4 sentences. No emojis."
        )

        prompt = f"""You are Florian, writing a personalized Skool DM to a community member.

Tone guidelines: {tone_template}

Member context:
- Name: {name}
- Bio: {bio}
- Company: {company}
- Services: {services}
- Industry: {industries}
- LinkedIn: {linkedin}
- Context: {context_note}
{posts_context}

Write ONLY the DM text. No subject line. No formatting. Just the message itself.
3-4 sentences max. Reference 1 specific detail from their profile. End with a genuine question."""

        # Use OpenRouter (openai-compatible) — no need for anthropic package
        import openai
        oai = openai.OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )
        model = config.get("messaging", {}).get("model", "anthropic/claude-haiku-4.5")

        response = oai.chat.completions.create(
            model=model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"  Draft error: {e}")
        name = member.get("name", "").split()[0] if member.get("name") else "there"
        return f"Hey {name}, saw you in the community — would love to connect. What are you working on right now?"


def send_draft_email(member: dict, draft: str, signal_type: str, config: dict, dry_run: bool = False):
    """Email the draft to Florian for review."""
    name = member.get("name", member.get("handle", "?"))
    community = config.get("community_slug", "")
    fin_tier = member.get("financial_tier", "?")
    icp_tier = member.get("icp_tier", "?")

    action = "CHURN RISK" if "churn" in signal_type else "NEW MEMBER"
    subject = f"[DRAFT] Message to {name} [{action} | F:{fin_tier}/ICP:{icp_tier}] — {community}"

    profile_url = member.get("profileUrl", "")
    linkedin = member.get("linkedin", "")

    html_body = f"""
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2>📝 Message Draft: {name}</h2>

<p><b>Profile:</b> <a href="{profile_url}">{profile_url}</a><br>
{'<b>LinkedIn:</b> <a href="' + linkedin + '">' + linkedin + '</a><br>' if linkedin else ''}
<b>Financial Tier:</b> {fin_tier} ({member.get('financial_score', '?')}/100)<br>
<b>ICP Tier:</b> {icp_tier} ({member.get('icp_score', '?')}/100)<br>
</p>

<hr>
<h3>Suggested DM (copy-paste ready)</h3>
<div style="background: #f0f7ff; padding: 16px; border-radius: 6px; border-left: 4px solid #3498db; white-space: pre-wrap; font-size: 15px;">{draft}</div>
<hr>

<h3>Bio</h3>
<p style="background: #f8f9fa; padding: 10px; border-radius: 4px;">{member.get('bio', '')[:300]}</p>

<p style="color: #888; font-size: 12px;">Skool Intelligence v2 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
</body></html>
"""
    text_body = f"Message Draft for {name}\n\n{draft}\n\nProfile: {profile_url}"

    florian_config = config.get("alerts", {}).get("florian", {})
    to_email = florian_config.get("email", "you@example.com")

    if dry_run:
        print(f"  [DRY RUN] Draft email to {to_email}")
        print(f"  --- DRAFT ---\n{draft}\n  ---")
        return

    try:
        from email_notifier import send_html_email
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        result = send_html_email(to_email, subject, html_body, text_body)
        if result.get("status") == "sent":
            print(f"  Draft emailed to {to_email}")
        else:
            print(f"  Draft email failed: {result.get('reason')}")
    except Exception as e:
        print(f"  Draft email error: {e}")


def draft_and_send(member: dict, signal_type: str, config: dict, dry_run: bool = False) -> str:
    """
    Full flow: find relevant posts → draft message → email to Florian.
    Returns the draft text (also attached to member dict as _message_draft).
    """
    mode = config.get("messaging", {}).get("mode", "off")
    if mode == "off":
        return ""

    include_posts = config.get("messaging", {}).get("include_post_matches", True)
    max_posts = config.get("messaging", {}).get("max_post_matches", 2)
    table = config.get("vectorization", {}).get("supabase_table", "skool_posts_jack")

    relevant_posts = []
    if include_posts:
        relevant_posts = search_relevant_posts(member, table, max_results=max_posts)
        if relevant_posts:
            print(f"  Found {len(relevant_posts)} relevant posts for context")

    draft = draft_message(member, signal_type, relevant_posts, config)
    member["_message_draft"] = draft

    if mode in ("draft_email_to_florian", "draft"):
        send_draft_email(member, draft, signal_type, config, dry_run=dry_run)

    return draft


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Message Drafter v2")
    parser.add_argument("--member", required=True, help="Path to enriched+scored member JSON")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--signal", default="new_qualified_member")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

    tenant_dir = EXECUTION_DIR / "tenants" / args.tenant
    with open(tenant_dir / "config.json", "r") as f:
        config = json.load(f)

    with open(args.member, "r") as f:
        member = json.load(f)

    draft = draft_and_send(member, args.signal, config, dry_run=args.dry_run)
    print(f"\n--- DRAFT ---\n{draft}\n---")


if __name__ == "__main__":
    main()
