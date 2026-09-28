#!/usr/bin/env python3
"""Native LinkedIn publishing helper for approved Website social drafts.

This is the fallback path when Postiz is unavailable. It uses LinkedIn's
official OAuth + Share on LinkedIn flow:

- user grants `openid profile w_member_social`
- token is stored outside git
- approved drafts are published through LinkedIn's REST API

It deliberately does not use browser automation, cookies, or unofficial
endpoints.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import secrets
import sys
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv


SCRIPT_PATH = Path(__file__).resolve()
BLOG_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_TOKEN_PATH = BLOG_ROOT / ".tmp" / "linkedin-native-token.json"
DEFAULT_SCOPES = "openid profile w_member_social"
DEFAULT_API_VERSION = "202506"
MIN_API_VERSION = "202506"


@dataclass
class NativeLinkedInConfig:
    client_id_present: bool
    client_secret_present: bool
    redirect_uri: str
    token_path: str
    token_present: bool
    token_expires_at: str | None
    person_urn_present: bool
    api_version: str


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    load_dotenv(BLOG_ROOT / ".env", override=True)


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def client_id() -> str:
    return env("LINKEDIN_CLIENT_ID")


def client_secret() -> str:
    return env("LINKEDIN_CLIENT_SECRET")


def redirect_uri() -> str:
    return env("LINKEDIN_REDIRECT_URI", "https://linkedin-api.example.com/linkedin/callback")


def api_version() -> str:
    value = env("LINKEDIN_API_VERSION", DEFAULT_API_VERSION)
    if not re.fullmatch(r"\d{6}", value):
        return DEFAULT_API_VERSION
    if value < MIN_API_VERSION:
        return MIN_API_VERSION
    return value


def native_api_url() -> str:
    return env("LINKEDIN_NATIVE_API_URL", "https://linkedin-api.example.com").rstrip("/")


def token_path() -> Path:
    configured = env("LINKEDIN_NATIVE_TOKEN_PATH")
    return Path(configured) if configured else DEFAULT_TOKEN_PATH


def require_linkedin_app() -> None:
    if not client_id() or not client_secret():
        raise RuntimeError("LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set.")


def read_token(required: bool = True) -> dict[str, Any]:
    path = token_path()
    if not path.exists():
        if required:
            raise RuntimeError(
                "No LinkedIn native token exists yet. Run `auth-url` and exchange the callback code first."
            )
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_token(token: dict[str, Any]) -> dict[str, Any]:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = dict(token)
    if "expires_in" in token and "expires_at" not in token:
        token["expires_at"] = int(time.time()) + int(token["expires_in"])
    path.write_text(json.dumps(token, indent=2), encoding="utf-8")
    return token


def token_expires_at(token: dict[str, Any]) -> str | None:
    value = token.get("expires_at")
    if not value:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(value)))
    except Exception:
        return str(value)


def access_token() -> str:
    token = read_token(required=True)
    expires_at = int(token.get("expires_at") or 0)
    if expires_at and expires_at < int(time.time()) + 300:
        refreshed = refresh_access_token(token)
        token = refreshed or token
    value = token.get("access_token")
    if not value:
        raise RuntimeError("LinkedIn token file exists but has no access_token.")
    return str(value)


def person_urn() -> str:
    token = read_token(required=True)
    for key in ("person_urn", "author", "owner"):
        value = token.get(key)
        if isinstance(value, str) and value.startswith("urn:li:person:"):
            return value
    profile = fetch_userinfo(access_token())
    sub = profile.get("sub")
    if not sub:
        raise RuntimeError("LinkedIn /v2/userinfo did not return a subject id.")
    token["person_urn"] = f"urn:li:person:{sub}"
    write_token(token)
    return token["person_urn"]


def linkedin_headers(token: str | None = None, *, json_body: bool = True) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token or access_token()}",
        "LinkedIn-Version": api_version(),
        "X-Restli-Protocol-Version": "2.0.0",
        "Accept": "application/json",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def build_auth_url(state: str | None = None) -> str:
    require_linkedin_app()
    state = state or secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": client_id(),
        "redirect_uri": redirect_uri(),
        "state": state,
        "scope": env("LINKEDIN_SCOPES", DEFAULT_SCOPES),
    }
    return "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)


def exchange_code(code: str) -> dict[str, Any]:
    require_linkedin_app()
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri(),
            "client_id": client_id(),
            "client_secret": client_secret(),
        },
        timeout=30,
    )
    resp.raise_for_status()
    token = write_token(resp.json())
    profile = fetch_userinfo(token["access_token"])
    if profile.get("sub"):
        token["person_urn"] = f"urn:li:person:{profile['sub']}"
        token["profile"] = {
            key: profile.get(key)
            for key in ("sub", "name", "given_name", "family_name", "email")
            if profile.get(key)
        }
        token = write_token(token)
    return token


def refresh_access_token(token: dict[str, Any]) -> dict[str, Any] | None:
    refresh = token.get("refresh_token")
    if not refresh:
        return None
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id(),
            "client_secret": client_secret(),
        },
        timeout=30,
    )
    if not resp.ok:
        return None
    merged = dict(token)
    merged.update(resp.json())
    return write_token(merged)


def fetch_userinfo(token: str) -> dict[str, Any]:
    resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def read_draft(path: str) -> dict[str, Any]:
    draft = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(draft, dict):
        raise ValueError("Draft JSON must contain an object.")
    return draft


def draft_image_path(draft: dict[str, Any]) -> str:
    for key in ("image_path", "final_image", "after_image", "feature_image"):
        value = draft.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def image_bytes(path_or_url: str) -> tuple[bytes, str]:
    if is_url(path_or_url):
        resp = requests.get(path_or_url, timeout=60)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type") or "image/png"
        return resp.content, content_type
    path = Path(path_or_url)
    data = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return data, content_type


def initialize_image_upload(owner: str) -> dict[str, Any]:
    resp = requests.post(
        "https://api.linkedin.com/rest/images?action=initializeUpload",
        headers=linkedin_headers(),
        json={"initializeUploadRequest": {"owner": owner}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["value"]


def upload_image(path_or_url: str, owner: str) -> str:
    initialized = initialize_image_upload(owner)
    upload_url = initialized["uploadUrl"]
    image_urn = initialized["image"]
    data, content_type = image_bytes(path_or_url)
    resp = requests.put(upload_url, data=data, headers={"Content-Type": content_type}, timeout=90)
    resp.raise_for_status()
    return image_urn


def build_post_payload(copy: str, owner: str, image_urn: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "author": owner,
        "commentary": copy,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if image_urn:
        payload["content"] = {
            "media": {
                "id": image_urn,
            }
        }
    return payload


def publish(copy: str, image: str = "", dry_run: bool = False, skip_image: bool = False) -> dict[str, Any]:
    copy = (copy or "").strip()
    if not copy:
        raise ValueError("LinkedIn copy is empty.")
    if dry_run:
        token = read_token(required=False)
        owner = token.get("person_urn") or "urn:li:person:CONNECTED_MEMBER_ID"
    else:
        owner = person_urn()
    image_urn = None
    if image and not skip_image:
        image_urn = "DRY_RUN_IMAGE_URN" if dry_run else upload_image(image, owner)
    payload = build_post_payload(copy, owner, image_urn=image_urn)
    if dry_run:
        return {
            "status": "dry-run",
            "author": owner,
            "would_send": payload,
            "image": image or None,
        }
    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers=linkedin_headers(),
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        raise requests.HTTPError(f"LinkedIn post failed {resp.status_code}: {resp.text}", response=resp)
    return {
        "status": "published",
        "post_urn": resp.headers.get("x-restli-id") or resp.headers.get("X-Restli-Id"),
        "response": resp.text,
    }


def publish_draft(path: str, dry_run: bool = False, skip_image: bool = False) -> dict[str, Any]:
    draft = read_draft(path)
    copy = (draft.get("copy") or "").strip()
    image = draft_image_path(draft)
    result = publish(copy, image=image, dry_run=dry_run, skip_image=skip_image)
    return {
        **result,
        "draft_json": path,
        "draft_title": draft.get("title"),
        "draft_slug": draft.get("slug"),
    }


def config_status() -> NativeLinkedInConfig:
    token = read_token(required=False)
    return NativeLinkedInConfig(
        client_id_present=bool(client_id()),
        client_secret_present=bool(client_secret()),
        redirect_uri=redirect_uri(),
        token_path=str(token_path()),
        token_present=bool(token),
        token_expires_at=token_expires_at(token) if token else None,
        person_urn_present=bool(token.get("person_urn")) if token else False,
        api_version=api_version(),
    )


def command_status(_: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    return asdict(config_status())


def command_auth_url(args: argparse.Namespace) -> dict[str, str]:
    load_environment()
    return {"auth_url": build_auth_url(args.state)}


def command_exchange_code(args: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    token = exchange_code(args.code)
    return {
        "status": "connected",
        "token_path": str(token_path()),
        "expires_at": token_expires_at(token),
        "person_urn_present": bool(token.get("person_urn")),
    }


def command_userinfo(_: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    profile = fetch_userinfo(access_token())
    return {
        "status": "ok",
        "profile": {key: profile.get(key) for key in ("sub", "name", "given_name", "family_name") if profile.get(key)},
    }


def command_publish_text(args: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    return publish(args.text, image=args.image or "", dry_run=args.dry_run, skip_image=args.skip_image)


def command_publish_draft(args: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    return publish_draft(args.draft_json, dry_run=args.dry_run, skip_image=args.skip_image)


def api_key() -> str:
    return env("LINKEDIN_NATIVE_API_KEY")


def publish_remote(copy: str, image: str = "", dry_run: bool = False, skip_image: bool = False) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("LINKEDIN_NATIVE_API_KEY is missing.")
    payload: dict[str, Any] = {
        "copy": copy,
        "dry_run": dry_run,
        "skip_image": skip_image,
    }
    if image and not skip_image:
        if not is_url(image):
            return {
                "status": "blocked-local-image-native-hosted",
                "message": "Hosted native LinkedIn can only upload public image URLs. Use --skip-image or publish from a public image URL.",
                "image": image,
            }
        payload["image_url"] = image
    resp = requests.post(
        f"{native_api_url()}/api/publish",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not resp.ok:
        raise requests.HTTPError(f"Native LinkedIn service failed {resp.status_code}: {resp.text}", response=resp)
    return resp.json()


def publish_draft_remote(path: str, dry_run: bool = False, skip_image: bool = False) -> dict[str, Any]:
    draft = read_draft(path)
    result = publish_remote(
        (draft.get("copy") or "").strip(),
        image=draft_image_path(draft),
        dry_run=dry_run,
        skip_image=skip_image,
    )
    return {
        **result,
        "draft_json": path,
        "draft_title": draft.get("title"),
        "draft_slug": draft.get("slug"),
    }


def command_publish_draft_remote(args: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    return publish_draft_remote(args.draft_json, dry_run=args.dry_run, skip_image=args.skip_image)


class NativeLinkedInHandler(BaseHTTPRequestHandler):
    server_version = "FlorianLinkedInNative/1.0"

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def authorize_api(self) -> bool:
        expected = api_key()
        if not expected:
            return False
        supplied = self.headers.get("X-API-Key", "")
        bearer = self.headers.get("Authorization", "")
        if bearer.startswith("Bearer "):
            supplied = bearer.removeprefix("Bearer ").strip()
        return secrets.compare_digest(expected, supplied)

    def do_GET(self) -> None:  # noqa: N802
        load_environment()
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(200, {"status": "ok", "service": "linkedin-native"})
            return
        if parsed.path == "/auth/start":
            url = build_auth_url()
            self.send_response(302)
            self.send_header("Location", url)
            self.end_headers()
            return
        if parsed.path in {"/auth/callback", "/linkedin/callback"}:
            params = parse_qs(parsed.query)
            code = (params.get("code") or [""])[0]
            if not code:
                self.send_json(400, {"status": "error", "message": "Missing LinkedIn OAuth code."})
                return
            try:
                token = exchange_code(code)
                self.send_json(
                    200,
                    {
                        "status": "connected",
                        "message": "LinkedIn is connected. You can close this tab.",
                        "expires_at": token_expires_at(token),
                        "person_urn_present": bool(token.get("person_urn")),
                    },
                )
            except Exception as exc:
                self.send_json(500, {"status": "error", "message": str(exc)})
            return
        self.send_json(404, {"status": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        load_environment()
        parsed = urlparse(self.path)
        if parsed.path != "/api/publish":
            self.send_json(404, {"status": "not-found"})
            return
        if not self.authorize_api():
            self.send_json(401, {"status": "unauthorized"})
            return
        try:
            body = self.read_json()
            result = publish(
                body.get("copy", ""),
                image=body.get("image_url") or body.get("image") or "",
                dry_run=bool(body.get("dry_run")),
                skip_image=bool(body.get("skip_image")),
            )
            self.send_json(200, result)
        except Exception as exc:
            self.send_json(500, {"status": "error", "message": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def command_serve(args: argparse.Namespace) -> dict[str, Any]:
    load_environment()
    server = ThreadingHTTPServer((args.host, args.port), NativeLinkedInHandler)
    print(json.dumps({"status": "serving", "host": args.host, "port": args.port}, indent=2), flush=True)
    server.serve_forever()
    return {"status": "stopped"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Native LinkedIn API client")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Show native LinkedIn config without printing secrets")
    p_status.set_defaults(func=command_status)

    p_auth = sub.add_parser("auth-url", help="Print LinkedIn OAuth authorization URL")
    p_auth.add_argument("--state", default="")
    p_auth.set_defaults(func=command_auth_url)

    p_exchange = sub.add_parser("exchange-code", help="Exchange LinkedIn OAuth code for a stored token")
    p_exchange.add_argument("--code", required=True)
    p_exchange.set_defaults(func=command_exchange_code)

    p_user = sub.add_parser("userinfo", help="Verify the stored token against LinkedIn userinfo")
    p_user.set_defaults(func=command_userinfo)

    p_text = sub.add_parser("publish-text", help="Publish or dry-run a text/image LinkedIn post")
    p_text.add_argument("--text", required=True)
    p_text.add_argument("--image", default="")
    p_text.add_argument("--dry-run", action="store_true")
    p_text.add_argument("--skip-image", action="store_true")
    p_text.set_defaults(func=command_publish_text)

    p_draft = sub.add_parser("publish-draft", help="Publish or dry-run a local LinkedIn draft JSON")
    p_draft.add_argument("--draft-json", required=True)
    p_draft.add_argument("--dry-run", action="store_true")
    p_draft.add_argument("--skip-image", action="store_true")
    p_draft.set_defaults(func=command_publish_draft)

    p_draft_remote = sub.add_parser("publish-draft-remote", help="Publish/dry-run via hosted native LinkedIn service")
    p_draft_remote.add_argument("--draft-json", required=True)
    p_draft_remote.add_argument("--dry-run", action="store_true")
    p_draft_remote.add_argument("--skip-image", action="store_true")
    p_draft_remote.set_defaults(func=command_publish_draft_remote)

    p_serve = sub.add_parser("serve", help="Run the tiny OAuth/publish HTTP service")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=int(env("PORT", "8080") or "8080"))
    p_serve.set_defaults(func=command_serve)

    args = parser.parse_args()
    result = args.func(args)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
