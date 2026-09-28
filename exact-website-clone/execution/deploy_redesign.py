#!/usr/bin/env python3
"""
Deploy a redesigned website to the preview subdomain.

Takes Stitch-exported HTML/CSS from .tmp/sites/{slug}/ and deploys it
to {slug}.preview.{domain} via GitHub + Coolify auto-deploy.

Usage:
    # Deploy a single site
    python execution/deploy_redesign.py --slug "delta-vega" --source ".tmp/sites/delta-vega"

    # Deploy from a local HTML file
    python execution/deploy_redesign.py --slug "delta-vega" --html-file ".tmp/html/delta-vega.html"

    # Batch deploy from Google Sheet (status=redesign_done)
    python execution/deploy_redesign.py --sheet-url "SHEET_URL"

    # Add Cloudflare wildcard DNS (one-time setup)
    python execution/deploy_redesign.py --setup-dns
"""

import os
import sys
import json
import re
import shutil
import argparse
import subprocess
import time
from pathlib import Path
from dotenv import load_dotenv

# Windows Unicode fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Config
GITHUB_REPO = "Florian1995-ai/will-coates-redesigns"
DEPLOY_REPO_DIR = ".tmp/deploy-repo"
PREVIEW_DOMAIN = os.getenv("PREVIEW_DOMAIN", "preview.florianrolke.com")
COOLIFY_SERVER = "2.24.108.202"


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60]


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------

def ensure_repo_cloned():
    """Ensure the deploy repo is cloned locally."""
    repo_path = os.path.abspath(DEPLOY_REPO_DIR)

    if os.path.exists(os.path.join(repo_path, ".git")):
        # Pull latest
        subprocess.run(["git", "pull", "--ff-only"], cwd=repo_path,
                       capture_output=True, text=True)
        return repo_path

    # Clone fresh
    os.makedirs(os.path.dirname(repo_path), exist_ok=True)

    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        # Token-based clone (Modal / CI environments)
        result = subprocess.run(
            ["git", "clone", f"https://{github_token}@github.com/{GITHUB_REPO}.git", repo_path],
            capture_output=True, text=True
        )
    else:
        # gh CLI clone (local dev)
        result = subprocess.run(
            ["gh", "repo", "clone", GITHUB_REPO, repo_path],
            capture_output=True, text=True
        )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone repo: {result.stderr}")

    return repo_path


COOLIFY_APP_UUID = "gs802658ie6n9exhn4ici1dm"
LANDING_DOMAIN = "client.of.florianrolke.com"


def _register_domain_in_coolify(domain: str):
    """Add a domain to the Coolify app FQDN so Traefik generates SSL cert + routing."""
    import requests as req

    token = os.getenv("COOLIFY_API_TOKEN")
    api_url = os.getenv("COOLIFY_API_URL", "https://app.coolify.io")

    if not token:
        print(f"  Warning: COOLIFY_API_TOKEN not set, skipping domain registration")
        return

    try:
        # Get current FQDN list
        r = req.get(
            f"{api_url}/api/v1/applications/{COOLIFY_APP_UUID}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        current_fqdn = r.json().get('fqdn', '')
        current_domains = [d.strip() for d in current_fqdn.split(',') if d.strip()]

        https_domain = f"https://{domain}"
        if https_domain in current_domains:
            return  # Already registered

        # Add new domain
        current_domains.append(https_domain)
        new_fqdn = ','.join(current_domains)

        r = req.patch(
            f"{api_url}/api/v1/applications/{COOLIFY_APP_UUID}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"domains": new_fqdn},
            timeout=15,
        )
        r.raise_for_status()
        print(f"  Registered domain in Coolify: {domain} (SSL will auto-provision)")
    except Exception as e:
        print(f"  Warning: Domain registration failed: {e}")


def _trigger_coolify_redeploy():
    """Trigger a Coolify redeploy after pushing to GitHub."""
    import requests as req

    token = os.getenv("COOLIFY_API_TOKEN")
    api_url = os.getenv("COOLIFY_API_URL", "https://app.coolify.io")

    if not token:
        print("  Warning: COOLIFY_API_TOKEN not set, skipping auto-redeploy")
        return

    try:
        r = req.post(
            f"{api_url}/api/v1/applications/{COOLIFY_APP_UUID}/restart",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"  Coolify redeploy triggered")
        else:
            print(f"  Warning: Coolify redeploy returned {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"  Warning: Coolify redeploy failed: {e}")


def _wait_for_ssl(domain: str, max_wait: int = 180, interval: int = 10):
    """
    Poll the deployed URL until SSL is valid and returns HTTP 200.

    Waits up to max_wait seconds, checking every interval seconds.
    This prevents returning URLs that show SSL errors to the user.
    """
    import urllib.request
    import ssl

    url = f"https://{domain}"
    print(f"  Waiting for SSL certificate on {domain}...", end="", flush=True)

    start = time.time()
    last_error = None

    while time.time() - start < max_wait:
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "deploy-ssl-check/1.0")
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            if resp.status < 500:
                elapsed = int(time.time() - start)
                print(f" ready ({elapsed}s)")
                return True
        except ssl.SSLCertVerificationError as e:
            last_error = f"SSL not ready: {e}"
        except ssl.SSLError as e:
            last_error = f"SSL error: {e}"
        except urllib.error.URLError as e:
            last_error = f"URL error: {e.reason}"
        except Exception as e:
            last_error = f"Error: {e}"

        print(".", end="", flush=True)
        time.sleep(interval)

    elapsed = int(time.time() - start)
    print(f" timeout after {elapsed}s")
    print(f"  Warning: SSL not ready after {max_wait}s ({last_error})")
    print(f"  The URL may work shortly — Traefik is still provisioning the cert.")
    return False


def deploy_site_files(slug: str, source_dir: str, deploy_type: str = "redesign") -> str:
    """
    Copy site files to the deploy repo and push to GitHub.

    Args:
        slug: Site identifier (used as subdomain and folder name)
        source_dir: Directory containing the site files (index.html, etc.)
        deploy_type: "redesign" (sites/ dir, preview domain),
                     "landing" (landing/ dir, client.of domain),
                     "widget" (sites/ dir with -chat suffix, preview domain)

    Returns:
        Live URL
    """
    repo_path = ensure_repo_cloned()

    # Determine target directory and domain based on deploy type
    if deploy_type == "landing":
        dest_dir = os.path.join(repo_path, "landing", slug)
        domain = f"{slug}.{LANDING_DOMAIN}"
    elif deploy_type == "widget":
        dest_dir = os.path.join(repo_path, "sites", f"{slug}-chat")
        domain = f"{slug}-chat.{PREVIEW_DOMAIN}"
    else:  # redesign (default)
        dest_dir = os.path.join(repo_path, "sites", slug)
        domain = f"{slug}.{PREVIEW_DOMAIN}"

    # Copy site files
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    shutil.copytree(source_dir, dest_dir)

    # Git add, commit, push
    subprocess.run(["git", "add", "-A"], cwd=repo_path, capture_output=True)

    commit_msg = f"Deploy {deploy_type}: {slug}"
    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=repo_path, capture_output=True, text=True
    )

    if "nothing to commit" in result.stdout:
        print(f"  No changes for {slug} (already deployed)")
    else:
        push_result = subprocess.run(
            ["git", "push"],
            cwd=repo_path, capture_output=True, text=True
        )
        if push_result.returncode != 0:
            raise RuntimeError(f"Git push failed: {push_result.stderr}")
        print(f"  Pushed to GitHub: {slug}")

        # Register domain in Coolify FQDN (ensures SSL cert is provisioned)
        _register_domain_in_coolify(domain)

        # Trigger Coolify redeploy (auto-deploy may be slow, so trigger explicitly)
        _trigger_coolify_redeploy()

        # Wait for SSL cert to be provisioned before returning URL
        _wait_for_ssl(domain)

    live_url = f"https://{domain}"
    return live_url


def deploy_single_html(slug: str, html_file: str, deploy_type: str = "redesign") -> str:
    """
    Deploy a single HTML file as a site.

    Creates a site folder with just the HTML file as index.html.
    """
    # Create temp site directory
    site_dir = os.path.join(".tmp", "sites", slug)
    os.makedirs(site_dir, exist_ok=True)

    # Copy HTML file as index.html
    shutil.copy2(html_file, os.path.join(site_dir, "index.html"))

    return deploy_site_files(slug, site_dir, deploy_type=deploy_type)


# ---------------------------------------------------------------------------
# Cloudflare DNS
# ---------------------------------------------------------------------------

def setup_wildcard_dns():
    """
    Create a wildcard DNS record in Cloudflare.

    *.preview.florianrolke.com → 2.24.108.202

    This only CREATES records, never deletes. Safe by design.
    """
    import requests

    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID")

    if not api_token or not zone_id:
        print("ERROR: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID must be set in .env")
        print("  1. Go to dash.cloudflare.com → Profile → API Tokens → Create Token")
        print("  2. Use 'Edit zone DNS' template, scope to florianrolke.com")
        print("  3. Get Zone ID from florianrolke.com Overview page (right sidebar)")
        return False

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    # Check if wildcard record already exists
    check_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    params = {"type": "A", "name": f"*.preview.florianrolke.com"}
    response = requests.get(check_url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        print(f"ERROR: Cloudflare API error: {response.status_code} {response.text[:200]}")
        return False

    existing = response.json().get("result", [])
    if existing:
        print(f"  Wildcard DNS already exists: *.preview.florianrolke.com → {existing[0]['content']}")
        return True

    # CREATE the wildcard DNS (never delete - safe by design)
    create_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    record_data = {
        "type": "A",
        "name": f"*.preview",
        "content": COOLIFY_SERVER,
        "proxied": False,  # DNS only (gray cloud) - let Coolify handle SSL
        "ttl": 1,  # Auto TTL
    }

    response = requests.post(create_url, headers=headers, json=record_data, timeout=30)

    if response.status_code == 200 and response.json().get("success"):
        record = response.json()["result"]
        print(f"  Created wildcard DNS: *.preview.florianrolke.com → {COOLIFY_SERVER}")
        print(f"  Record ID: {record['id']}")
        return True
    else:
        print(f"ERROR: Failed to create DNS record: {response.text[:300]}")
        return False


# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------

def get_google_credentials():
    """Get OAuth2 credentials for Google Sheets API."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = None

    if os.path.exists('token.json'):
        try:
            with open('token.json', 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data, scopes)
        except Exception as e:
            print(f"Error loading token: {e}", file=sys.stderr)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, scopes)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())

    return creds


def batch_deploy_from_sheet(sheet_url, worksheet_name=None):
    """Deploy all sites with status=redesign_done from Google Sheet."""
    import gspread

    creds = get_google_credentials()
    client = gspread.authorize(creds)

    sheet_id = sheet_url.split('/d/')[1].split('/')[0] if '/d/' in sheet_url else sheet_url
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    records = worksheet.get_all_records()
    headers = worksheet.row_values(1)
    to_deploy = [(i, r) for i, r in enumerate(records)
                 if str(r.get('status', '')).strip().lower() == 'redesign_done']

    if not to_deploy:
        print("No leads with status='redesign_done' found.")
        return

    print(f"Deploying {len(to_deploy)} sites...")

    for idx, (record_idx, lead) in enumerate(to_deploy):
        company = lead.get('company', lead.get('Company', f'lead_{record_idx}'))
        slug = slugify(company)
        site_dir = os.path.join(".tmp", "sites", slug)

        if not os.path.exists(site_dir):
            # Try to use HTML from capture
            html_path = os.path.join(".tmp", "html", f"{slug}.html")
            if os.path.exists(html_path):
                os.makedirs(site_dir, exist_ok=True)
                shutil.copy2(html_path, os.path.join(site_dir, "index.html"))
            else:
                print(f"  [{idx+1}/{len(to_deploy)}] SKIP {company} - no site files")
                continue

        print(f"  [{idx+1}/{len(to_deploy)}] Deploying {company}...")
        try:
            preview_url = deploy_site_files(slug, site_dir)
            print(f"    URL: {preview_url}")

            # Update sheet
            sheet_row = record_idx + 2  # +2: header + 0-based
            for col_name, value in [("status", "deployed"), ("preview_url", preview_url)]:
                if col_name in headers:
                    col_idx = headers.index(col_name) + 1
                    worksheet.update_cell(sheet_row, col_idx, str(value))

        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\nDone. Deployed {len(to_deploy)} sites to {PREVIEW_DOMAIN}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Deploy redesigned websites to preview subdomains")
    parser.add_argument("--slug", help="Site slug (used as subdomain)")
    parser.add_argument("--source", help="Directory containing site files")
    parser.add_argument("--html-file", help="Single HTML file to deploy as site")
    parser.add_argument("--deploy-type", default="redesign",
                        choices=["redesign", "landing", "widget"],
                        help="Type of deployment: redesign (preview), landing (client.of), widget (preview with -chat)")
    parser.add_argument("--sheet-url", help="Google Sheet URL for batch deployment")
    parser.add_argument("--worksheet", help="Worksheet name (default: first sheet)")
    parser.add_argument("--setup-dns", action="store_true", help="Create wildcard DNS in Cloudflare (one-time)")

    args = parser.parse_args()

    if args.setup_dns:
        success = setup_wildcard_dns()
        return 0 if success else 1

    if args.slug and args.source:
        url = deploy_site_files(args.slug, args.source, deploy_type=args.deploy_type)
        print(f"Deployed: {url}")
        return 0

    if args.slug and args.html_file:
        url = deploy_single_html(args.slug, args.html_file, deploy_type=args.deploy_type)
        print(f"Deployed: {url}")
        return 0

    if args.sheet_url:
        batch_deploy_from_sheet(args.sheet_url, args.worksheet)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
