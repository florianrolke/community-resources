"""
Lead Magnet Pipeline API Server.

Self-hosted FastAPI app that generates website redesigns, voice widgets,
and custom landing pages for prospects via HTTP POST.

Run locally:  uvicorn server:app --host 0.0.0.0 --port 8000
Docker:       docker build -t leadmagnet-pipeline . && docker run -p 8000:8000 --env-file .env leadmagnet-pipeline
Test:         curl -X POST http://localhost:8000/generate \
                -H "Content-Type: application/json" \
                -H "Authorization: Bearer YOUR_TOKEN" \
                -d '{"url": "https://example.com", "slug": "example"}'
"""

import os
import sys
import json
import time
import subprocess
import logging
import urllib.request
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("leadmagnet")

# ── Auth ──────────────────────────────────────────────────────────────

AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")


def verify_auth(authorization: Optional[str] = Header(None)):
    """Simple bearer token check. Skipped if API_AUTH_TOKEN is not set."""
    if not AUTH_TOKEN:
        return  # No auth configured — open access
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


# ── App ───────────────────────────────────────────────────────────────

APP_DIR = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run setup on startup."""
    setup_working_directory()
    yield

app = FastAPI(
    title="Lead Magnet Pipeline",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Models ────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    url: str
    slug: str
    use_cases: list[str] = ["redesign", "widget", "landing"]
    generator: str = "v0"


# ── Helpers ───────────────────────────────────────────────────────────

def slack_notify(message: str):
    """Fire-and-forget Slack notification."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        payload = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url, data=payload,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.warning(f"Slack notify failed: {e}")


def setup_working_directory():
    """Create .tmp subdirectories and configure git."""
    os.chdir(APP_DIR)

    for d in [
        ".tmp/screenshots", ".tmp/html", ".tmp/branding",
        ".tmp/redesigns", ".tmp/redesigns/history",
        ".tmp/analysis", ".tmp/facts", ".tmp/comparisons",
        ".tmp/qa", ".tmp/sites", ".tmp/deploy-repo",
        "widget-demo/output", "landing-page-demo/output",
    ]:
        os.makedirs(d, exist_ok=True)

    # Configure git for deploy_redesign.py
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        subprocess.run(["git", "config", "--global", "credential.helper", "cache --timeout=3600"], capture_output=True)
        subprocess.run(
            ["git", "credential", "approve"],
            input=f"protocol=https\nhost=github.com\nusername=x-access-token\npassword={github_token}\n\n",
            text=True,
            capture_output=True,
        )
        subprocess.run(["git", "config", "--global", "user.email", "you@example.com"], capture_output=True)
        subprocess.run(["git", "config", "--global", "user.name", "LeadMagnet Bot"], capture_output=True)

    logger.info(f"Working directory: {APP_DIR}")


def run_step(cmd: list, label: str, timeout: int = 300) -> dict:
    """Run a pipeline step via subprocess."""
    logger.info(f"Starting: {label}")
    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, cwd=APP_DIR,
        )
        elapsed = round(time.time() - start, 1)
        success = result.returncode == 0
        if not success:
            logger.error(f"FAILED {label}: {result.stderr[-500:]}")
        else:
            logger.info(f"OK {label} ({elapsed}s)")
        return {"success": success, "stdout": result.stdout[-2000:], "stderr": result.stderr[-500:], "elapsed": elapsed}
    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - start, 1)
        logger.error(f"TIMEOUT {label} after {timeout}s")
        return {"success": False, "stdout": "", "stderr": f"Timeout after {timeout}s", "elapsed": elapsed}
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        return {"success": False, "stdout": "", "stderr": str(e), "elapsed": elapsed}


# ── Pipeline ──────────────────────────────────────────────────────────

def run_pipeline(url: str, slug: str, use_cases: set, generator: str = "v0") -> dict:
    """Execute the full 3-UC pipeline for one prospect."""
    py = sys.executable
    results = {}
    urls = {}
    errors = []
    total_start = time.time()

    # Step 1: Capture
    r = run_step(
        [py, "execution/capture_website_screenshot.py", "--url", url, "--lead-id", slug],
        f"Capture {slug}", timeout=120,
    )
    results["capture"] = r
    if not r["success"]:
        errors.append(f"Capture failed: {r['stderr'][:200]}")
        return {"slug": slug, "url": url, "steps": _summarize(results), "urls": urls,
                "total_elapsed": round(time.time() - total_start, 1), "errors": errors, "status": "failed"}

    # UC1: Redesign
    if "redesign" in use_cases:
        r = run_step(
            [py, "execution/generate_redesign.py", "--slug", slug, "--generator", generator],
            f"UC1 Generate {slug}", timeout=240,
        )
        results["redesign_generate"] = r
        if r["success"]:
            html_file = f".tmp/redesigns/{slug}-redesign.html"
            r = run_step(
                [py, "execution/deploy_redesign.py", "--slug", slug, "--html-file", html_file, "--deploy-type", "redesign"],
                f"UC1 Deploy {slug}", timeout=120,
            )
            results["redesign_deploy"] = r
            if r["success"]:
                urls["redesign"] = f"https://{slug}.preview.florianrolke.com"
        else:
            errors.append(f"UC1 generate failed: {r['stderr'][:200]}")

    # UC2: Widget
    if "widget" in use_cases:
        run_step([py, "widget-demo/setup_retell_agent.py", "--slug", slug], f"UC2 Retell {slug}", timeout=60)
        r = run_step(
            [py, "widget-demo/build_widget_page.py", "--url", url, "--slug", slug],
            f"UC2 Widget {slug}", timeout=90,
        )
        results["widget_build"] = r
        if r["success"]:
            html_file = f"widget-demo/output/{slug}-chat/index.html"
            if os.path.exists(os.path.join(APP_DIR, html_file)):
                r = run_step(
                    [py, "execution/deploy_redesign.py", "--slug", slug, "--html-file", html_file, "--deploy-type", "widget"],
                    f"UC2 Deploy {slug}", timeout=120,
                )
                results["widget_deploy"] = r
                if r["success"]:
                    urls["widget"] = f"https://{slug}-chat.preview.florianrolke.com"

    # UC3: Landing Page
    if "landing" in use_cases:
        r = run_step(
            [py, "landing-page-demo/research_client.py", "--url", url, "--slug", slug],
            f"UC3 Research {slug}", timeout=120,
        )
        results["landing_research"] = r
        if r["success"]:
            r = run_step(
                [py, "landing-page-demo/generate_landing_page.py", "--slug", slug, "--generator", generator],
                f"UC3 Generate {slug}", timeout=240,
            )
            results["landing_generate"] = r
            if r["success"]:
                html_file = f"landing-page-demo/output/{slug}/index.html"
                if os.path.exists(os.path.join(APP_DIR, html_file)):
                    r = run_step(
                        [py, "execution/deploy_redesign.py", "--slug", slug, "--html-file", html_file, "--deploy-type", "landing"],
                        f"UC3 Deploy {slug}", timeout=120,
                    )
                    results["landing_deploy"] = r
                    if r["success"]:
                        urls["landing"] = f"https://{slug}.client.of.florianrolke.com"
            else:
                errors.append(f"UC3 generate failed: {r['stderr'][:200]}")
        else:
            errors.append(f"UC3 research failed: {r['stderr'][:200]}")

    # Collect errors
    for step_name, step_result in results.items():
        if not step_result.get("success") and step_name not in ["widget_retell"]:
            msg = f"{step_name}: {step_result.get('stderr', 'unknown')[:200]}"
            if msg not in errors:
                errors.append(msg)

    total_elapsed = round(time.time() - total_start, 1)
    status = "success" if urls else "partial" if any(r.get("success") for r in results.values()) else "failed"

    return {"slug": slug, "url": url, "steps": _summarize(results), "urls": urls,
            "total_elapsed": total_elapsed, "errors": errors, "status": status}


def _summarize(results: dict) -> dict:
    return {k: {"success": v["success"], "elapsed": v["elapsed"]} for k, v in results.items()}


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "leadmagnet-pipeline",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/generate")
def generate(req: GenerateRequest, authorization: Optional[str] = Header(None)):
    verify_auth(authorization)

    url = req.url
    slug = req.slug
    use_cases = set(req.use_cases)
    generator = req.generator

    if not url.startswith("http"):
        url = f"https://{url}"

    slack_notify(
        f":rocket: *Lead magnet pipeline started*\n"
        f"Slug: `{slug}`\nURL: {url}\n"
        f"Use cases: {', '.join(sorted(use_cases))}"
    )

    try:
        result = run_pipeline(url, slug, use_cases, generator)
    except Exception as e:
        logger.exception(f"Pipeline crashed for {slug}")
        slack_notify(f":x: Pipeline CRASHED for *{slug}*: {str(e)[:200]}")
        raise HTTPException(status_code=500, detail=str(e))

    # Slack completion
    url_lines = "\n".join(f"  {k}: {v}" for k, v in result["urls"].items())
    error_lines = "\n".join(f"  - {e}" for e in result["errors"][:5])
    emoji = ":white_check_mark:" if result["status"] == "success" else ":warning:"
    slack_msg = f"{emoji} *Pipeline {result['status']}* for `{slug}` ({result['total_elapsed']}s)\nURLs:\n{url_lines or '  (none)'}"
    if error_lines:
        slack_msg += f"\nErrors:\n{error_lines}"
    slack_notify(slack_msg)

    return result
