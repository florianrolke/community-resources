#!/usr/bin/env python3
"""
Create a Retell AI chat agent for a prospect's business.

Reads business facts from the facts lock, creates an LLM config and agent
via the Retell REST API, and saves the config for the widget builder.

Usage:
    python widget-demo/setup_retell_agent.py --slug delta-vega
    python widget-demo/setup_retell_agent.py --slug delta-vega --voice 11labs-Adrian
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

RETELL_API_URL = "https://api.retellai.com"
CONFIG_DIR = Path(__file__).parent
OUTPUT_CONFIG = CONFIG_DIR / "retell-config.json"


def load_facts(slug):
    """Load business facts from the facts lock file."""
    facts_path = Path(f'.tmp/facts/{slug}-facts.json')
    if not facts_path.exists():
        print(f"  Warning: No facts file at {facts_path}. Using generic prompt.")
        return None
    with open(facts_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_agent_prompt(slug, facts):
    """Build an LLM system prompt from business facts."""
    if not facts:
        return (
            f"You are a helpful assistant for {slug}. "
            "Be professional and concise. If you don't know something, "
            "say so and offer to connect them with the team."
        )

    company = facts.get('company_name', slug.replace('-', ' ').title())
    about = facts.get('about_text', '')
    nav = facts.get('navigation', [])
    ctas = facts.get('original_ctas', [])
    content = facts.get('all_content', [])

    services = [n for n in nav if n.upper() not in ('HOME', 'ABOUT', 'CONTACT', 'MENU')]

    prompt_parts = [
        f"You are a helpful assistant for {company}.",
        "",
    ]

    if about:
        prompt_parts.append(f"About the company: {about}")
        prompt_parts.append("")

    if services:
        prompt_parts.append(f"Services offered: {', '.join(services)}.")

    if ctas:
        prompt_parts.append(f"Key actions visitors can take: {', '.join(ctas)}.")

    # Look for contact email in content
    for block in content:
        if '@' in block and '.' in block:
            prompt_parts.append(f"Contact information from the site: {block[:200]}")
            break

    prompt_parts.extend([
        "",
        "Guidelines:",
        "- Be professional, warm, and concise.",
        "- Answer questions about the company's services based on the information above.",
        "- If asked something you don't know, say: \"I'd recommend reaching out directly for that detail.\"",
        "- Keep responses under 3 sentences unless the user asks for more detail.",
        "- Do NOT invent facts about the company. Only use what's provided above.",
    ])

    return '\n'.join(prompt_parts)


def create_retell_llm(api_key, prompt):
    """Create a Retell LLM configuration. Returns llm_id."""
    print("  Creating Retell LLM config...")
    resp = requests.post(
        f"{RETELL_API_URL}/create-retell-llm",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "general_prompt": prompt,
            "model": "gpt-4o-mini",
            "start_speaker": "agent",
        },
        timeout=30,
    )

    if resp.status_code != 201:
        raise RuntimeError(
            f"Failed to create Retell LLM (HTTP {resp.status_code}): {resp.text[:500]}"
        )

    data = resp.json()
    llm_id = data.get('llm_id')
    print(f"  LLM created: {llm_id}")
    return llm_id


def create_retell_agent(api_key, llm_id, agent_name, voice_id):
    """Create a Retell chat agent. Returns agent_id."""
    print(f"  Creating Retell agent '{agent_name}' with voice '{voice_id}'...")
    resp = requests.post(
        f"{RETELL_API_URL}/create-agent",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "response_engine": {
                "type": "retell-llm",
                "llm_id": llm_id,
            },
            "voice_id": voice_id,
            "agent_name": agent_name,
        },
        timeout=30,
    )

    if resp.status_code != 201:
        raise RuntimeError(
            f"Failed to create Retell agent (HTTP {resp.status_code}): {resp.text[:500]}"
        )

    data = resp.json()
    agent_id = data.get('agent_id')
    print(f"  Agent created: {agent_id}")
    return agent_id


def main():
    parser = argparse.ArgumentParser(description='Create a Retell AI agent for a prospect')
    parser.add_argument('--slug', required=True, help='Site identifier (e.g., delta-vega)')
    parser.add_argument('--voice', default='11labs-Adrian',
                        help='Retell voice ID (default: 11labs-Adrian)')
    args = parser.parse_args()

    api_key = os.getenv('RETELL_API_KEY')
    if not api_key:
        print("Error: RETELL_API_KEY not found in .env")
        sys.exit(1)

    print(f"\n=== Setting up Retell agent for: {args.slug} ===\n")

    # Load facts
    facts = load_facts(args.slug)

    # Build prompt
    prompt = build_agent_prompt(args.slug, facts)
    print(f"  System prompt ({len(prompt)} chars):")
    for line in prompt.split('\n')[:5]:
        print(f"    {line}")
    print(f"    ...")

    # Create LLM
    llm_id = create_retell_llm(api_key, prompt)

    # Create agent
    company = 'Delta Vega' if 'delta-vega' in args.slug else args.slug.replace('-', ' ').title()
    agent_name = f"{company} Assistant"
    agent_id = create_retell_agent(api_key, llm_id, agent_name, args.voice)

    # Save config
    config = {
        'slug': args.slug,
        'agent_id': agent_id,
        'llm_id': llm_id,
        'agent_name': agent_name,
        'voice_id': args.voice,
    }

    # Save per-slug config
    slug_config_path = CONFIG_DIR / f"retell-config-{args.slug}.json"
    with open(slug_config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    print(f"\n  Config saved: {slug_config_path}")

    # Also update/create the main config file
    all_configs = {}
    if OUTPUT_CONFIG.exists():
        with open(OUTPUT_CONFIG, 'r', encoding='utf-8') as f:
            all_configs = json.load(f)
    all_configs[args.slug] = config
    with open(OUTPUT_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(all_configs, f, indent=2)

    print(f"\n=== Done! ===")
    print(f"  Agent ID: {agent_id}")
    print(f"  Next: python widget-demo/build_widget_page.py --url https://{args.slug.replace('-', '')}.com --slug {args.slug}")

    # Check for public key
    public_key = os.getenv('RETELL_PUBLIC_KEY')
    if not public_key:
        print(f"\n  NOTE: You still need RETELL_PUBLIC_KEY in .env for the widget embed.")
        print(f"  Get it from: Retell Dashboard → Keys → Add Key → Public Key")
        print(f"  Set the allowed domain to: preview.florianrolke.com")


if __name__ == '__main__':
    main()
