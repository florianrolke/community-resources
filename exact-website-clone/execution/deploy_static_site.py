#!/usr/bin/env python3
"""
Deploy a static HTML file to a custom subdomain via GitHub + Coolify + Cloudflare DNS.

The will-coates-redesigns GitHub repo serves all *.florianrolke.com subdomains.
Nginx routing: {slug}.florianrolke.com → sites/{slug}/index.html

Usage:
    python execution/deploy_static_site.py \
        --html clients/jonathan/columbia.html \
        --slug columbia.jfschachter \
        --domain columbia.jfschachter.florianrolke.com

Required env vars (loaded from Will Coates .env):
    GITHUB_TOKEN, COOLIFY_API_TOKEN, COOLIFY_API_URL, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID
"""

import os
import sys
import shutil
import subprocess
import time
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load Will Coates .env first (has working Coolify token), then local .env (has GitHub PAT)
# Local .env values override Will Coates values where both exist
from dotenv import load_dotenv
WC_ENV = Path(__file__).parent.parent.parent / "Will Coates Website Project LeadMagnet" / ".env"
LOCAL_ENV = Path(__file__).parent.parent / ".env"
if WC_ENV.exists():
    load_dotenv(WC_ENV)
    print(f"Loaded Will Coates env (Coolify token)")
if LOCAL_ENV.exists():
    load_dotenv(LOCAL_ENV, override=True)
    print(f"Loaded local env (GitHub token override)")

import requests

GITHUB_REPO = "Florian1995-ai/will-coates-redesigns"
DEPLOY_REPO_DIR = Path(".tmp/deploy-repo")
COOLIFY_APP_UUID = "gs802658ie6n9exhn4ici1dm"
COOLIFY_SERVER = "2.24.108.202"


def ensure_repo_cloned():
    repo_path = DEPLOY_REPO_DIR.resolve()
    if (repo_path / ".git").exists():
        print("Pulling latest from GitHub...")
        result = subprocess.run(["git", "pull", "--ff-only"], cwd=repo_path, capture_output=True, text=True)
        print(f"  {result.stdout.strip() or 'up to date'}")
        return repo_path

    print("Cloning deploy repo...")
    github_token = os.getenv("GITHUB_TOKEN")
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", f"https://{github_token}@github.com/{GITHUB_REPO}.git", str(repo_path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr}")
    print("  Cloned successfully.")
    return repo_path


def push_html_to_repo(slug: str, html_file: str, repo_path: Path):
    site_dir = repo_path / "sites" / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    dest = site_dir / "index.html"
    shutil.copy2(html_file, dest)
    print(f"Copied {html_file} → sites/{slug}/index.html")

    subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", f"Deploy static site: {slug}"],
        cwd=repo_path, capture_output=True, text=True
    )
    if "nothing to commit" in result.stdout:
        print("  No changes (file already up to date in repo)")
        return False

    push = subprocess.run(["git", "push"], cwd=repo_path, capture_output=True, text=True)
    if push.returncode != 0:
        raise RuntimeError(f"Git push failed: {push.stderr}")
    print(f"  Pushed to GitHub: {GITHUB_REPO}")
    return True


def register_domain_in_coolify(domain: str):
    token = os.getenv("COOLIFY_API_TOKEN")
    api_url = os.getenv("COOLIFY_API_URL", "https://app.coolify.io")

    r = requests.get(
        f"{api_url}/api/v1/applications/{COOLIFY_APP_UUID}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    current_fqdn = r.json().get("fqdn", "")
    current_domains = [d.strip() for d in current_fqdn.split(",") if d.strip()]

    https_domain = f"https://{domain}"
    if https_domain in current_domains:
        print(f"  Domain already registered in Coolify: {domain}")
        return

    current_domains.append(https_domain)
    new_fqdn = ",".join(current_domains)

    r = requests.patch(
        f"{api_url}/api/v1/applications/{COOLIFY_APP_UUID}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"domains": new_fqdn},
        timeout=15,
    )
    r.raise_for_status()
    print(f"  Registered in Coolify FQDN: {domain}")


def trigger_coolify_redeploy():
    token = os.getenv("COOLIFY_API_TOKEN")
    api_url = os.getenv("COOLIFY_API_URL", "https://app.coolify.io")

    r = requests.post(
        f"{api_url}/api/v1/applications/{COOLIFY_APP_UUID}/restart",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code == 200:
        print("  Coolify redeploy triggered (SSL cert will provision in ~1-2 min)")
    else:
        print(f"  Warning: Coolify restart returned {r.status_code}: {r.text[:100]}")


def create_cloudflare_dns(subdomain: str):
    """Add an A record: subdomain.florianrolke.com → 2.24.108.202"""
    token = os.getenv("CLOUDFLARE_API_TOKEN")
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"

    # Check if record already exists
    r = requests.get(base, headers=headers, params={"name": f"{subdomain}.florianrolke.com", "type": "A"}, timeout=15)
    existing = r.json().get("result", [])
    if existing:
        print(f"  DNS record already exists: {subdomain}.florianrolke.com → {existing[0]['content']}")
        return

    r = requests.post(base, headers=headers, json={
        "type": "A",
        "name": subdomain,
        "content": COOLIFY_SERVER,
        "ttl": 1,
        "proxied": False,
    }, timeout=15)

    if r.json().get("success"):
        print(f"  Created DNS A record: {subdomain}.florianrolke.com → {COOLIFY_SERVER}")
    else:
        print(f"  DNS warning: {r.text[:200]}")


def wait_for_live(domain: str, max_wait: int = 180):
    import urllib.request, ssl
    url = f"https://{domain}"
    print(f"  Waiting for {url} to go live", end="", flush=True)
    start = time.time()
    while time.time() - start < max_wait:
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "deploy-check/1.0")
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            elapsed = int(time.time() - start)
            print(f" LIVE ({elapsed}s)")
            return True
        except Exception:
            print(".", end="", flush=True)
            time.sleep(10)
    print(f" timeout ({max_wait}s) — may come up shortly as SSL provisions")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, help="Path to HTML file")
    parser.add_argument("--slug", required=True, help="Nginx slug (e.g. columbia.jfschachter)")
    parser.add_argument("--domain", required=True, help="Full domain (e.g. columbia.jfschachter.florianrolke.com)")
    parser.add_argument("--no-wait", action="store_true", help="Skip SSL wait")
    args = parser.parse_args()

    if not Path(args.html).exists():
        print(f"ERROR: HTML file not found: {args.html}")
        sys.exit(1)

    print(f"\n=== Deploying {args.domain} ===\n")

    # 1. Clone/pull repo
    repo_path = ensure_repo_cloned()

    # 2. Push HTML
    pushed = push_html_to_repo(args.slug, args.html, repo_path)

    # 3. Register domain in Coolify
    print("\nRegistering domain in Coolify...")
    register_domain_in_coolify(args.domain)

    # 4. Trigger redeploy (always, even if no new file — ensures domain routes)
    print("\nTriggering Coolify redeploy...")
    trigger_coolify_redeploy()

    # 5. Add DNS record
    print("\nCreating Cloudflare DNS record...")
    create_cloudflare_dns(args.slug)

    # 6. Wait for live
    if not args.no_wait:
        print()
        wait_for_live(args.domain)

    print(f"\n✓ Done: https://{args.domain}")


if __name__ == "__main__":
    main()
