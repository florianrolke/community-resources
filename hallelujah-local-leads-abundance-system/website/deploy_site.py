#!/usr/bin/env python3
"""
Deploy a redesigned website to a live preview URL.

Supports two deployment methods:
  1. GitHub Pages — push to a deploy repo, auto-serves via GitHub Pages
  2. Local preview — starts a simple HTTP server for local testing

Usage:
    # Local preview server
    python website/deploy_site.py --slug example-corp --html .tmp/redesigns/example.html --method local

    # Deploy to GitHub repo
    python website/deploy_site.py --slug example-corp --html .tmp/redesigns/example.html --method github

    # Deploy with custom repo
    python website/deploy_site.py --slug example-corp --html .tmp/redesigns/example.html --method github --repo "user/redesigns"
"""

import os
import sys
import re
import shutil
import subprocess
import argparse
import http.server
import threading
from pathlib import Path

# Windows UTF-8 fix
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()


def slugify(text):
    """Convert text to filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def deploy_github(slug, html_path, repo=None):
    """Deploy to GitHub Pages by pushing to a deploy repo.

    Returns dict with url, repo, commit.
    """
    repo = repo or os.getenv('DEPLOY_GITHUB_REPO')
    if not repo:
        raise ValueError(
            "No deploy repo specified. Use --repo or set DEPLOY_GITHUB_REPO in .env\n"
            "  Example: DEPLOY_GITHUB_REPO=your-username/redesigns"
        )

    # Parse repo owner/name
    if '/' not in repo:
        raise ValueError(f"Repo must be in 'owner/name' format, got: {repo}")
    owner, name = repo.split('/', 1)

    # Clone or pull the deploy repo
    deploy_dir = os.path.join('.tmp', 'deploy-repo', name)

    if os.path.exists(os.path.join(deploy_dir, '.git')):
        print(f"  Pulling existing deploy repo: {deploy_dir}")
        subprocess.run(['git', 'pull', '--rebase'], cwd=deploy_dir,
                       capture_output=True, timeout=30)
    else:
        print(f"  Cloning deploy repo: {repo}")
        os.makedirs(os.path.dirname(deploy_dir), exist_ok=True)

        # Use GitHub CLI / configured git credentials. Never put tokens in URLs.
        clone_url = f"https://github.com/{repo}.git"

        result = subprocess.run(
            ['git', 'clone', '--depth', '1', clone_url, deploy_dir],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            # Repo might not exist — create it via gh
            print(f"  Clone failed, creating repo: {repo}")
            subprocess.run(
                ['gh', 'repo', 'create', repo, '--public', '--clone', '--confirm'],
                cwd=os.path.dirname(deploy_dir),
                capture_output=True, timeout=30
            )

    # Create slug directory and copy HTML
    site_dir = os.path.join(deploy_dir, slugify(slug))
    os.makedirs(site_dir, exist_ok=True)

    # Copy HTML as index.html
    shutil.copy2(html_path, os.path.join(site_dir, 'index.html'))
    print(f"  Copied: {html_path} → {site_dir}/index.html")

    # Git add, commit, push
    subprocess.run(['git', 'add', '.'], cwd=deploy_dir, capture_output=True)

    commit_msg = f"Deploy {slug} redesign"
    result = subprocess.run(
        ['git', 'commit', '-m', commit_msg],
        cwd=deploy_dir, capture_output=True, text=True
    )

    if 'nothing to commit' in (result.stdout + result.stderr):
        print("  No changes to commit (already deployed)")
    else:
        print(f"  Committed: {commit_msg}")

        push_result = subprocess.run(
            ['git', 'push'],
            cwd=deploy_dir, capture_output=True, text=True, timeout=60
        )
        if push_result.returncode == 0:
            print("  Pushed to GitHub")
        else:
            print(f"  Push failed: {push_result.stderr[:200]}")
            return {'url': None, 'error': push_result.stderr}

    # Build GitHub Pages URL
    url = f"https://{owner}.github.io/{name}/{slugify(slug)}/"

    return {
        'url': url,
        'repo': repo,
        'slug': slugify(slug),
    }


def deploy_local(slug, html_path, port=8080):
    """Start a local HTTP server to preview the redesign.

    Returns dict with url.
    """
    # Create temp serve directory
    serve_dir = os.path.join('.tmp', 'preview', slugify(slug))
    os.makedirs(serve_dir, exist_ok=True)

    # Copy HTML as index.html
    shutil.copy2(html_path, os.path.join(serve_dir, 'index.html'))

    url = f"http://localhost:{port}"
    print(f"\n  Serving: {serve_dir}")
    print(f"  Preview: {url}")
    print(f"  Press Ctrl+C to stop\n")

    # Start server
    os.chdir(serve_dir)
    handler = http.server.SimpleHTTPRequestHandler

    try:
        with http.server.HTTPServer(('', port), handler) as server:
            server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")

    return {'url': url, 'slug': slugify(slug)}


def deploy(slug, html_path, method='local', repo=None, port=8080):
    """Deploy redesign using specified method.

    Returns dict with url.
    """
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    file_size = os.path.getsize(html_path)
    print(f"  Deploying: {html_path} ({file_size:,} bytes)")

    if method == 'github':
        return deploy_github(slug, html_path, repo)
    elif method == 'local':
        return deploy_local(slug, html_path, port)
    else:
        raise ValueError(f"Unknown deploy method: {method}")


def main():
    parser = argparse.ArgumentParser(description='Deploy a redesigned website')
    parser.add_argument('--slug', required=True, help='Project slug')
    parser.add_argument('--html', required=True, help='Path to HTML file')
    parser.add_argument('--method', choices=['github', 'local'], default='local',
                        help='Deployment method (default: local)')
    parser.add_argument('--repo', help='GitHub repo for deployment (owner/name)')
    parser.add_argument('--port', type=int, default=8080, help='Local server port')

    args = parser.parse_args()

    print(f"Deploying: {args.slug} via {args.method}")
    result = deploy(
        slug=args.slug,
        html_path=args.html,
        method=args.method,
        repo=args.repo,
        port=args.port,
    )

    if result.get('url'):
        print(f"\nLive at: {result['url']}")


if __name__ == '__main__':
    main()
