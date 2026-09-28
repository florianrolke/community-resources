#!/usr/bin/env python3
"""
Ghost CMS Client - Content Publishing Integration (SEO + AEO Optimized)

Self-hosted on Coolify. Better than WordPress for AI Engine Optimization.

Coolify Deployment:
    1. Open https://app.coolify.io → your server → New Resource → One-Click → "Ghost"
    2. Set domain: your-ghost-domain.com
    3. Set env: url=https://your-ghost-domain.com
    4. Set env: database__client=sqlite3  (lighter than MySQL, sufficient for <1000 posts)
    5. Deploy and wait for health check
    6. Add CNAME in Cloudflare: blog → srv788893.hstgr.cloud (proxy OFF)
    7. Visit https://your-ghost-domain.com/ghost/ to set up admin account
    8. Go to Settings → Integrations → Add Custom Integration → copy Admin API Key
    9. Add to this folder's .env: GHOST_URL and GHOST_ADMIN_API_KEY

Why Ghost for AEO:
    - Clean HTML output (AI crawlers parse it better than WordPress)
    - Built-in JSON-LD structured data (no plugins needed)
    - Faster page loads (critical for AI indexing)
    - Markdown-native (cleaner semantic structure)
    - Built-in newsletter/membership

Usage:
    python execution/ghost_client.py list-posts
    python execution/ghost_client.py create "My Post Title" content.html --tags "AI,coaching"
    python execution/ghost_client.py update <post_id> --title "New Title"
    python execution/ghost_client.py upload image.jpg
    python execution/ghost_client.py create-tag "AI Coaching" --description "Posts about AI coaching"

API Docs: https://ghost.org/docs/admin-api/
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

GHOST_URL = os.getenv("GHOST_URL", "https://your-ghost-domain.com")
ADMIN_API_KEY = os.getenv("GHOST_ADMIN_API_KEY", "")


def _generate_token() -> str:
    """Generate a JWT token from the Ghost Admin API key."""
    import jwt  # PyJWT

    # Split the key into ID and SECRET
    key_parts = ADMIN_API_KEY.split(":")
    if len(key_parts) != 2:
        raise ValueError("GHOST_ADMIN_API_KEY must be in format 'id:secret'")

    kid, secret = key_parts

    iat = int(time.time())
    header = {"alg": "HS256", "kid": kid, "typ": "JWT"}
    payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}

    token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
    return token


def _headers():
    token = _generate_token()
    return {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept-Version": "v5.0",
    }


def _api(path: str) -> str:
    return f"{GHOST_URL}/ghost/api/admin/{path}"


def list_posts(limit: int = 15, status: str = "all") -> list:
    """List posts with optional status filter."""
    resp = requests.get(
        _api("posts/"),
        headers=_headers(),
        params={"limit": limit, "filter": f"status:{status}" if status != "all" else None},
        timeout=15,
    )
    resp.raise_for_status()
    posts = resp.json().get("posts", [])
    for p in posts:
        st = p.get("status", "?")
        title = p.get("title", "Untitled")
        slug = p.get("slug", "")
        print(f"  [{st}] {title} (/{slug})")
    print(f"\nTotal: {len(posts)} posts")
    return posts


def _read_optional_file(path: str = None) -> str:
    """Read an optional UTF-8 file."""
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _html_card_lexical(html: str) -> str:
    """Wrap raw HTML in a Ghost Lexical HTML card so classes/attributes survive."""
    return json.dumps({
        "root": {
            "children": [
                {
                    "type": "html",
                    "version": 1,
                    "html": html,
                    "visibility": {
                        "web": {
                            "nonMember": True,
                            "memberSegment": "status:free,status:-free",
                        },
                        "email": {
                            "memberSegment": "status:free,status:-free",
                        },
                    },
                },
                {
                    "children": [],
                    "direction": None,
                    "format": "",
                    "indent": 0,
                    "type": "paragraph",
                    "version": 1,
                },
            ],
            "direction": None,
            "format": "",
            "indent": 0,
            "type": "root",
            "version": 1,
        },
    }, ensure_ascii=False)


def _content_payload(title: str, html_content: str = None, html_file: str = None,
                     tags: list = None, featured: bool = False,
                     status: str = "draft", meta_title: str = None,
                     meta_description: str = None, custom_excerpt: str = None,
                     canonical_url: str = None, code_head: str = None,
                     code_head_file: str = None, code_foot: str = None,
                     code_foot_file: str = None, html_card: bool = False,
                     feature_image: str = None) -> dict:
    payload = {
        "title": title,
        "status": status,
        "featured": featured,
    }

    if html_file:
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
    elif html_content:
        content = html_content
    else:
        content = "<p>Draft post - content coming soon.</p>"

    if html_card:
        payload["lexical"] = _html_card_lexical(content)
    else:
        payload["html"] = content

    if tags:
        payload["tags"] = [{"name": t.strip()} for t in tags]

    if meta_title:
        payload["meta_title"] = meta_title
    if meta_description:
        payload["meta_description"] = meta_description
    if custom_excerpt:
        payload["custom_excerpt"] = custom_excerpt
    if canonical_url:
        payload["canonical_url"] = canonical_url
    if feature_image:
        payload["feature_image"] = feature_image

    head = code_head or _read_optional_file(code_head_file)
    foot = code_foot or _read_optional_file(code_foot_file)
    if head:
        payload["codeinjection_head"] = head
    if foot:
        payload["codeinjection_foot"] = foot

    return payload


def create_post(title: str, html_content: str = None, html_file: str = None,
                tags: list = None, featured: bool = False,
                status: str = "draft", meta_title: str = None,
                meta_description: str = None, custom_excerpt: str = None,
                canonical_url: str = None, code_head: str = None,
                code_head_file: str = None, code_foot: str = None,
                code_foot_file: str = None, html_card: bool = False,
                slug: str = None, feature_image: str = None) -> dict:
    """Create a new blog post."""
    post_data = _content_payload(
        title=title,
        html_content=html_content,
        html_file=html_file,
        tags=tags,
        featured=featured,
        status=status,
        meta_title=meta_title,
        meta_description=meta_description,
        custom_excerpt=custom_excerpt,
        canonical_url=canonical_url,
        code_head=code_head,
        code_head_file=code_head_file,
        code_foot=code_foot,
        code_foot_file=code_foot_file,
        html_card=html_card,
        feature_image=feature_image,
    )
    if slug:
        post_data["slug"] = slug
    params = None if html_card else {"source": "html"}

    resp = requests.post(
        _api("posts/"),
        headers=_headers(),
        params=params,
        json={"posts": [post_data]},
        timeout=30,
    )
    resp.raise_for_status()
    post = resp.json()["posts"][0]
    print(f"Post created: '{post['title']}' [{post['status']}]")
    print(f"  URL: {GHOST_URL}/{post['slug']}/")
    print(f"  ID: {post['id']}")
    return post


def create_page(title: str, html_content: str = None, html_file: str = None,
                status: str = "draft", meta_title: str = None,
                meta_description: str = None, custom_excerpt: str = None,
                canonical_url: str = None, code_head: str = None,
                code_head_file: str = None, code_foot: str = None,
                code_foot_file: str = None, html_card: bool = False,
                slug: str = None, feature_image: str = None) -> dict:
    """Create a new Ghost page."""
    page_data = _content_payload(
        title=title,
        html_content=html_content,
        html_file=html_file,
        status=status,
        meta_title=meta_title,
        meta_description=meta_description,
        custom_excerpt=custom_excerpt,
        canonical_url=canonical_url,
        code_head=code_head,
        code_head_file=code_head_file,
        code_foot=code_foot,
        code_foot_file=code_foot_file,
        html_card=html_card,
        feature_image=feature_image,
    )
    if slug:
        page_data["slug"] = slug
    params = None if html_card else {"source": "html"}

    resp = requests.post(
        _api("pages/"),
        headers=_headers(),
        params=params,
        json={"pages": [page_data]},
        timeout=30,
    )
    resp.raise_for_status()
    page = resp.json()["pages"][0]
    print(f"Page created: '{page['title']}' [{page['status']}]")
    print(f"  URL: {page.get('url', GHOST_URL + '/' + page['slug'] + '/')}")
    print(f"  ID: {page['id']}")
    return page


def update_post(post_id: str, title: str = None, html_content: str = None,
                html_file: str = None,
                status: str = None, tags: list = None,
                meta_title: str = None, meta_description: str = None,
                custom_excerpt: str = None, canonical_url: str = None,
                code_head: str = None, code_head_file: str = None,
                code_foot: str = None, code_foot_file: str = None,
                html_card: bool = False, feature_image: str = None) -> dict:
    """Update an existing post."""
    # First fetch the post to get updated_at (required for PUT)
    resp = requests.get(
        _api(f"posts/{post_id}/"),
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    current = resp.json()["posts"][0]

    update_data = {"updated_at": current["updated_at"]}

    if title:
        update_data["title"] = title
    content = None
    if html_file:
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
    elif html_content:
        content = html_content

    if content:
        if html_card:
            update_data["lexical"] = _html_card_lexical(content)
        else:
            update_data["html"] = content
    if status:
        update_data["status"] = status
    if tags:
        update_data["tags"] = [{"name": t.strip()} for t in tags]
    if meta_title:
        update_data["meta_title"] = meta_title
    if meta_description:
        update_data["meta_description"] = meta_description
    if custom_excerpt:
        update_data["custom_excerpt"] = custom_excerpt
    if canonical_url:
        update_data["canonical_url"] = canonical_url
    if feature_image:
        update_data["feature_image"] = feature_image

    head = code_head or _read_optional_file(code_head_file)
    foot = code_foot or _read_optional_file(code_foot_file)
    if head:
        update_data["codeinjection_head"] = head
    if foot:
        update_data["codeinjection_foot"] = foot

    resp = requests.put(
        _api(f"posts/{post_id}/"),
        headers=_headers(),
        params=None if html_card else {"source": "html"},
        json={"posts": [update_data]},
        timeout=30,
    )
    resp.raise_for_status()
    post = resp.json()["posts"][0]
    print(f"Post updated: '{post['title']}' [{post['status']}]")
    return post


def upload_image(image_path: str) -> str:
    """Upload an image and return its URL."""
    token = _generate_token()
    headers = {
        "Authorization": f"Ghost {token}",
        "Accept-Version": "v5.0",
    }

    with open(image_path, "rb") as f:
        files = {"file": (Path(image_path).name, f, "image/jpeg")}
        resp = requests.post(
            _api("images/upload/"),
            headers=headers,
            files=files,
            timeout=60,
        )

    resp.raise_for_status()
    url = resp.json()["images"][0]["url"]
    print(f"Image uploaded: {url}")
    return url


def create_tag(name: str, description: str = None, slug: str = None) -> dict:
    """Create a tag for organizing content."""
    tag_data = {"name": name}
    if description:
        tag_data["description"] = description
    if slug:
        tag_data["slug"] = slug

    resp = requests.post(
        _api("tags/"),
        headers=_headers(),
        json={"tags": [tag_data]},
        timeout=15,
    )
    resp.raise_for_status()
    tag = resp.json()["tags"][0]
    print(f"Tag created: '{tag['name']}' (slug: {tag['slug']})")
    return tag


def list_tags() -> list:
    """List all tags."""
    resp = requests.get(
        _api("tags/"),
        headers=_headers(),
        params={"limit": "all"},
        timeout=15,
    )
    resp.raise_for_status()
    tags = resp.json().get("tags", [])
    for t in tags:
        count = t.get("count", {}).get("posts", "?")
        print(f"  {t['name']} ({count} posts)")
    return tags


def main():
    parser = argparse.ArgumentParser(description="Ghost CMS - Content Publishing Client")
    sub = parser.add_subparsers(dest="command", required=True)

    # list-posts
    p_list = sub.add_parser("list-posts", help="List posts")
    p_list.add_argument("--limit", type=int, default=15)
    p_list.add_argument("--status", default="all", choices=["all", "published", "draft", "scheduled"])

    # create
    p_create = sub.add_parser("create", help="Create a new post")
    p_create.add_argument("title", help="Post title")
    p_create.add_argument("html_file", nargs="?", help="Path to HTML content file")
    p_create.add_argument("--html", help="Inline HTML content")
    p_create.add_argument("--tags", help="Comma-separated tags")
    p_create.add_argument("--featured", action="store_true")
    p_create.add_argument("--publish", action="store_true", help="Publish immediately")
    p_create.add_argument("--meta-title", help="SEO meta title")
    p_create.add_argument("--meta-description", help="SEO meta description")
    p_create.add_argument("--excerpt", help="Custom excerpt")
    p_create.add_argument("--canonical-url", help="Canonical URL")
    p_create.add_argument("--slug", help="URL slug")
    p_create.add_argument("--feature-image", help="Feature image URL")
    p_create.add_argument("--code-head-file", help="HTML file for post head code injection")
    p_create.add_argument("--code-foot-file", help="HTML file for post foot code injection")
    p_create.add_argument("--html-card", action="store_true", help="Store content as a Ghost HTML card to preserve classes and attributes")

    # create-page
    p_page = sub.add_parser("create-page", help="Create a new page")
    p_page.add_argument("title", help="Page title")
    p_page.add_argument("html_file", nargs="?", help="Path to HTML content file")
    p_page.add_argument("--html", help="Inline HTML content")
    p_page.add_argument("--publish", action="store_true", help="Publish immediately")
    p_page.add_argument("--meta-title", help="SEO meta title")
    p_page.add_argument("--meta-description", help="SEO meta description")
    p_page.add_argument("--excerpt", help="Custom excerpt")
    p_page.add_argument("--canonical-url", help="Canonical URL")
    p_page.add_argument("--slug", help="URL slug")
    p_page.add_argument("--feature-image", help="Feature image URL")
    p_page.add_argument("--code-head-file", help="HTML file for page head code injection")
    p_page.add_argument("--code-foot-file", help="HTML file for page foot code injection")
    p_page.add_argument("--html-card", action="store_true", help="Store content as a Ghost HTML card to preserve classes and attributes")

    # update
    p_update = sub.add_parser("update", help="Update a post")
    p_update.add_argument("post_id", help="Post ID")
    p_update.add_argument("--title", help="New title")
    p_update.add_argument("--html", help="New HTML content")
    p_update.add_argument("--html-file", help="Path to HTML content file")
    p_update.add_argument("--status", choices=["published", "draft", "scheduled"])
    p_update.add_argument("--tags", help="Comma-separated tags")
    p_update.add_argument("--meta-title", help="SEO meta title")
    p_update.add_argument("--meta-description", help="SEO meta description")
    p_update.add_argument("--excerpt", help="Custom excerpt")
    p_update.add_argument("--canonical-url", help="Canonical URL")
    p_update.add_argument("--feature-image", help="Feature image URL")
    p_update.add_argument("--code-head-file", help="HTML file for post head code injection")
    p_update.add_argument("--code-foot-file", help="HTML file for post foot code injection")
    p_update.add_argument("--html-card", action="store_true", help="Store content as a Ghost HTML card to preserve classes and attributes")

    # upload
    p_upload = sub.add_parser("upload", help="Upload an image")
    p_upload.add_argument("image", help="Path to image file")

    # create-tag
    p_tag = sub.add_parser("create-tag", help="Create a tag")
    p_tag.add_argument("name", help="Tag name")
    p_tag.add_argument("--description", help="Tag description")
    p_tag.add_argument("--slug", help="Tag slug")

    # list-tags
    sub.add_parser("list-tags", help="List all tags")

    args = parser.parse_args()

    if not ADMIN_API_KEY:
        print("Error: GHOST_ADMIN_API_KEY not found in .env", file=sys.stderr)
        print("Get it from: Ghost Admin → Settings → Integrations → Add Custom Integration")
        sys.exit(1)

    if args.command == "list-posts":
        result = list_posts(limit=args.limit, status=args.status)
    elif args.command == "create":
        tags = args.tags.split(",") if args.tags else None
        result = create_post(
            title=args.title,
            html_file=args.html_file,
            html_content=args.html,
            tags=tags,
            featured=args.featured,
            status="published" if args.publish else "draft",
            meta_title=args.meta_title,
            meta_description=args.meta_description,
            custom_excerpt=args.excerpt,
            canonical_url=args.canonical_url,
            code_head_file=args.code_head_file,
            code_foot_file=args.code_foot_file,
            html_card=args.html_card,
            slug=args.slug,
            feature_image=args.feature_image,
        )
    elif args.command == "create-page":
        result = create_page(
            title=args.title,
            html_file=args.html_file,
            html_content=args.html,
            status="published" if args.publish else "draft",
            meta_title=args.meta_title,
            meta_description=args.meta_description,
            custom_excerpt=args.excerpt,
            canonical_url=args.canonical_url,
            code_head_file=args.code_head_file,
            code_foot_file=args.code_foot_file,
            html_card=args.html_card,
            slug=args.slug,
            feature_image=args.feature_image,
        )
    elif args.command == "update":
        tags = args.tags.split(",") if args.tags else None
        result = update_post(
            args.post_id,
            title=args.title,
            html_content=args.html,
            html_file=args.html_file,
            status=args.status,
            tags=tags,
            meta_title=args.meta_title,
            meta_description=args.meta_description,
            custom_excerpt=args.excerpt,
            canonical_url=args.canonical_url,
            code_head_file=args.code_head_file,
            code_foot_file=args.code_foot_file,
            html_card=args.html_card,
            feature_image=args.feature_image,
        )
    elif args.command == "upload":
        result = upload_image(args.image)
    elif args.command == "create-tag":
        result = create_tag(args.name, description=args.description, slug=args.slug)
    elif args.command == "list-tags":
        result = list_tags()

    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


