#!/usr/bin/env python3
"""
Tiny phone-friendly upload page for Agent Zero assets.

Runs inside the Agent Zero container and writes uploaded files to the mounted
assets volume, so files immediately appear under /app/work_dir/assets.
"""

from __future__ import annotations

import cgi
import html
import json
import mimetypes
import os
import shutil
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


UPLOAD_DIR = Path(os.getenv("AGENTZERO_UPLOAD_DIR", "/app/work_dir/assets/agentzero_uploads/shorts_test"))
OUTPUT_ROOT = Path(os.getenv("AGENTZERO_OUTPUT_DIR", "/app/work_dir/assets/agentzero_outputs"))
PIPELINE_DIR = Path(os.getenv("AGENTZERO_PIPELINE_DIR", "/app/work_dir/assets/agentzero_pipeline"))
PIPELINE_CONFIG = Path(os.getenv("AGENTZERO_PIPELINE_CONFIG", str(PIPELINE_DIR / "pipeline_config.json")))
RENDER_STATUS_FILE = OUTPUT_ROOT / "render_status.json"
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
PARTIAL_SUFFIXES = {".part", ".tmp", ".download", ".crdownload"}
render_process: subprocess.Popen | None = None


def safe_filename(filename: str) -> str:
    original = Path(filename or "upload.mov").name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        suffix = ".mov"

    stem = Path(original).stem or "upload"
    clean_stem = "".join(ch if ch.isalnum() else "-" for ch in stem).strip("-") or "upload"
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{clean_stem[:64]}{suffix}"


def safe_upload_id(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value or "").strip("-_")
    return clean[:96] or datetime.utcnow().strftime("%Y%m%d%H%M%S")


def upload_chunk_root(upload_id: str) -> Path:
    return UPLOAD_DIR / ".partial" / safe_upload_id(upload_id)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_upload_reference(filename: str) -> Path:
    requested = Path(unquote(filename or "")).name
    if not requested:
        raise ValueError("Missing upload filename")
    if Path(requested).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported upload extension")
    target = (UPLOAD_DIR / requested).resolve()
    root = UPLOAD_DIR.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Invalid upload filename") from None
    if not target.is_file():
        raise FileNotFoundError(requested)
    return target


def list_uploads() -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(UPLOAD_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)[:20]:
        if not path.is_file():
            continue
        if path.name.startswith(".") or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if any(path.name.endswith(suffix) for suffix in PARTIAL_SUFFIXES):
            continue
        size_mb = path.stat().st_size / (1024 * 1024)
        quoted_name = html.escape(quote(path.name))
        rows.append(
            "<tr>"
            f"<td>{html.escape(path.name)}</td>"
            f"<td>{size_mb:.1f} MB</td>"
            f"<td><button class='row-button render-upload-button' type='button' data-file='{quoted_name}'>Render</button></td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='3'>No uploads yet.</td></tr>"


def read_render_status() -> dict:
    if not RENDER_STATUS_FILE.exists():
        return {"state": "idle"}
    try:
        return json.loads(RENDER_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"state": "unknown", "error": str(exc)}


def pipeline_info() -> dict:
    return {
        "mode": "mounted-live-pipeline",
        "pipeline_dir": str(PIPELINE_DIR),
        "pipeline_config": str(PIPELINE_CONFIG),
        "upload_server_script": str(Path(__file__).resolve()),
        "render_worker_script": str(Path(__file__).with_name("phone_render_worker.py").resolve()),
        "audio_dir": str(PIPELINE_DIR / "audio"),
        "logo_dir": str(PIPELINE_DIR / "logo"),
        "note": "Edit files in pipeline_dir to tune the editing flow without rebuilding Docker.",
    }


def write_render_status(status: dict) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    status["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    tmp = RENDER_STATUS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(RENDER_STATUS_FILE)


def output_url_for(path_value: str) -> str:
    if not path_value:
        return ""
    try:
        target = Path(path_value).resolve()
        rel = target.relative_to(OUTPUT_ROOT.resolve())
    except Exception:
        return ""
    return "/outputs/" + "/".join(quote(part) for part in rel.parts)


def page(message: str = "") -> bytes:
    message_html = f"<p class='message'>{html.escape(message)}</p>" if message else ""
    render_status = read_render_status()
    render_state = html.escape(str(render_status.get("state", "idle")))
    render_step = html.escape(str(render_status.get("step", "")))
    render_final = html.escape(str(render_status.get("final", "")))
    render_thumbnail = html.escape(str(render_status.get("thumbnail", "")))
    render_llm = html.escape(str(render_status.get("llm_status", "")))
    render_llm_cost = html.escape(str(render_status.get("llm_actual_cost_usd") or render_status.get("llm_estimated_cost_usd") or ""))
    render_youtube = html.escape(str(render_status.get("youtube_status", "")))
    render_youtube_url = html.escape(str(render_status.get("youtube_url", "")))
    render_elapsed = html.escape(str(render_status.get("elapsed_seconds", "")))
    render_rss = html.escape(str(render_status.get("max_rss_mb", "")))
    render_final_url = html.escape(output_url_for(str(render_status.get("final", ""))))
    render_thumbnail_url = html.escape(output_url_for(str(render_status.get("thumbnail", ""))))
    info = pipeline_info()
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Zero Upload</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #111;
      color: #f7f7f7;
    }}
    main {{
      max-width: 760px;
      margin: 0 auto;
      padding: 36px 18px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 30px;
    }}
    p {{
      color: #cfcfcf;
      line-height: 1.45;
    }}
    form {{
      margin: 24px 0;
      padding: 20px;
      border: 1px solid #333;
      border-radius: 8px;
      background: #1b1b1b;
    }}
    input[type=file] {{
      box-sizing: border-box;
      width: 100%;
      padding: 16px;
      border: 1px dashed #555;
      border-radius: 6px;
      background: #0d0d0d;
      color: #fff;
    }}
    button {{
      width: 100%;
      margin-top: 14px;
      padding: 14px 16px;
      border: 0;
      border-radius: 6px;
      background: #ffd400;
      color: #111;
      font-weight: 800;
      font-size: 16px;
    }}
    button:disabled {{
      opacity: 0.55;
    }}
    .row-button {{
      width: auto;
      margin: 0;
      padding: 8px 12px;
      font-size: 13px;
      background: #f7f7f7;
      color: #111;
    }}
    .progress-wrap {{
      display: none;
      margin-top: 18px;
    }}
    .progress-meta {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 8px;
      color: #f7f7f7;
      font-weight: 800;
    }}
    .progress-track {{
      height: 16px;
      overflow: hidden;
      border-radius: 999px;
      background: #2b2b2b;
      border: 1px solid #444;
    }}
    .progress-bar {{
      width: 0%;
      height: 100%;
      background: #ffd400;
      transition: width 0.18s ease;
    }}
    .status {{
      min-height: 22px;
      margin-top: 10px;
      color: #cfcfcf;
      font-weight: 700;
    }}
    .status.ok {{
      color: #5af28a;
    }}
    .status.error {{
      color: #ff6464;
    }}
    .render-card {{
      margin: 24px 0;
      padding: 20px;
      border: 1px solid #333;
      border-radius: 8px;
      background: #181818;
    }}
    .render-card button {{
      background: #f7f7f7;
      color: #111;
    }}
    .render-card a {{
      color: #ffd400;
      font-weight: 800;
    }}
    .render-output {{
      margin-top: 12px;
      padding: 12px;
      border-radius: 6px;
      background: #0d0d0d;
      color: #d8d8d8;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }}
    th, td {{
      padding: 10px 4px;
      border-bottom: 1px solid #2c2c2c;
      text-align: left;
      font-size: 14px;
      overflow-wrap: anywhere;
    }}
    .path {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      color: #aaa;
      overflow-wrap: anywhere;
    }}
    .message {{
      color: #ffd400;
      font-weight: 800;
    }}
    .small {{
      font-size: 13px;
      color: #aaa;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Agent Zero Upload</h1>
    <p>Upload one iPhone clip. The file will be saved into Agent Zero's mounted assets folder.</p>
    <p class="path">{html.escape(str(UPLOAD_DIR))}</p>
    <p class="small">Live editing pipeline: <span class="path">{html.escape(info["pipeline_dir"])}</span></p>
    <p class="small">Preset/config: <span class="path">{html.escape(info["pipeline_config"])}</span></p>
    {message_html}
    <form id="upload-form" method="post" enctype="multipart/form-data">
      <input id="video-input" type="file" name="video" accept="video/*" required>
      <button id="upload-button" type="submit">Upload Video</button>
      <div id="progress-wrap" class="progress-wrap" aria-live="polite">
        <div class="progress-meta">
          <span id="progress-label">Waiting</span>
          <span id="progress-percent">0%</span>
        </div>
        <div class="progress-track">
          <div id="progress-bar" class="progress-bar"></div>
        </div>
        <div id="upload-status" class="status"></div>
      </div>
    </form>
    <section class="render-card">
      <h2>Render Test</h2>
      <p>Start a server-side render from the newest completed upload. Partial files are ignored and the selected file must pass ffprobe first.</p>
      <button id="render-button" type="button">Render Latest Valid Upload</button>
      <div id="render-output" class="render-output">State: {render_state}
Step: {render_step}
Final: {render_final}
Thumbnail: {render_thumbnail}
LLM: {render_llm} {render_llm_cost}
YouTube: {render_youtube} {render_youtube_url}
Elapsed seconds: {render_elapsed}
Max RSS MB: {render_rss}</div>
      <p id="render-links">
        {f'<a href="{render_final_url}" target="_blank">Open final.mp4</a>' if render_final_url else ''}
        {f' &middot; <a href="{render_thumbnail_url}" target="_blank">Open thumbnail.jpg</a>' if render_thumbnail_url else ''}
        {f' &middot; <a href="{render_youtube_url}" target="_blank">Open YouTube</a>' if render_youtube_url else ''}
      </p>
    </section>
    <h2>Recent Uploads</h2>
    <table>
      <thead><tr><th>File</th><th>Size</th><th>Action</th></tr></thead>
      <tbody>{list_uploads()}</tbody>
    </table>
  </main>
  <script>
    const form = document.getElementById("upload-form");
    const input = document.getElementById("video-input");
    const button = document.getElementById("upload-button");
    const progressWrap = document.getElementById("progress-wrap");
    const progressBar = document.getElementById("progress-bar");
    const progressPercent = document.getElementById("progress-percent");
    const progressLabel = document.getElementById("progress-label");
    const status = document.getElementById("upload-status");
    const renderButton = document.getElementById("render-button");
    const renderOutput = document.getElementById("render-output");
    const renderLinks = document.getElementById("render-links");

    function setProgress(percent, label) {{
      const clean = Math.max(0, Math.min(100, Math.round(percent)));
      progressWrap.style.display = "block";
      progressBar.style.width = clean + "%";
      progressPercent.textContent = clean + "%";
      progressLabel.textContent = label;
    }}

    function setStatus(message, kind) {{
      status.textContent = message;
      status.className = "status" + (kind ? " " + kind : "");
    }}

    function postChunk(file, uploadId, index, totalChunks, chunkSize) {{
      const start = index * chunkSize;
      const end = Math.min(file.size, start + chunkSize);
      const blob = file.slice(start, end);
      const url = "/upload-chunk"
        + "?upload_id=" + encodeURIComponent(uploadId)
        + "&filename=" + encodeURIComponent(file.name)
        + "&index=" + encodeURIComponent(index)
        + "&total=" + encodeURIComponent(totalChunks)
        + "&size=" + encodeURIComponent(file.size);

      return new Promise((resolve, reject) => {{
        const xhr = new XMLHttpRequest();
        xhr.open("POST", url, true);
        xhr.setRequestHeader("Content-Type", "application/octet-stream");
        xhr.upload.addEventListener("progress", (event) => {{
          if (event.lengthComputable) {{
            const uploaded = start + event.loaded;
            setProgress((uploaded / file.size) * 100, "Uploading chunk " + (index + 1) + "/" + totalChunks);
          }}
        }});
        xhr.addEventListener("load", () => {{
          if (xhr.status >= 200 && xhr.status < 300) {{
            try {{
              resolve(JSON.parse(xhr.responseText));
            }} catch (_err) {{
              resolve({{ ok: true }});
            }}
          }} else {{
            reject(new Error("chunk " + (index + 1) + " failed with status " + xhr.status));
          }}
        }});
        xhr.addEventListener("error", () => reject(new Error("network error on chunk " + (index + 1))));
        xhr.addEventListener("abort", () => reject(new Error("upload cancelled")));
        xhr.send(blob);
      }});
    }}

    async function postChunkWithRetry(file, uploadId, index, totalChunks, chunkSize) {{
      let lastError = null;
      for (let attempt = 1; attempt <= 3; attempt++) {{
        try {{
          if (attempt > 1) {{
            setStatus("Retrying chunk " + (index + 1) + " (attempt " + attempt + "/3)...", "");
          }}
          return await postChunk(file, uploadId, index, totalChunks, chunkSize);
        }} catch (err) {{
          lastError = err;
          await new Promise((resolve) => setTimeout(resolve, 900 * attempt));
        }}
      }}
      throw lastError || new Error("chunk upload failed");
    }}

    async function uploadFileInChunks(file) {{
      const chunkSize = 8 * 1024 * 1024;
      const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize));
      const uploadId = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
      let finalResponse = null;
      for (let index = 0; index < totalChunks; index++) {{
        finalResponse = await postChunkWithRetry(file, uploadId, index, totalChunks, chunkSize);
        const uploaded = Math.min(file.size, (index + 1) * chunkSize);
        setProgress((uploaded / file.size) * 100, finalResponse.complete ? "Assembled" : "Uploaded chunk " + (index + 1) + "/" + totalChunks);
      }}
      return finalResponse || {{ ok: false }};
    }}

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      if (!input.files || input.files.length === 0) {{
        setStatus("Choose a video first.", "error");
        return;
      }}

      const file = input.files[0];

      button.disabled = true;
      input.disabled = true;
      setProgress(0, "Uploading");
      setStatus(file.name + " selected. Keep this page open until it says saved.", "");

      try {{
        const data = await uploadFileInChunks(file);
        if (!data.ok || !data.complete) {{
          throw new Error(data.error || "upload did not complete");
        }}
        setProgress(100, "Uploaded");
        setStatus("Saved as " + data.filename + " (" + data.size_mb + " MB). Refreshing list...", "ok");
        window.setTimeout(() => window.location.reload(), 1200);
      }} catch (err) {{
        setStatus("Upload failed: " + (err && err.message ? err.message : "check connection and try again."), "error");
        button.disabled = false;
        input.disabled = false;
      }}
    }});

    function renderStatusText(data) {{
      const lines = [
        "State: " + (data.state || "idle"),
        "Step: " + (data.step || ""),
        "Selected upload: " + (data.selected_upload || ""),
        "Input: " + (data.input || ""),
        "Final: " + (data.final || ""),
        "Thumbnail: " + (data.thumbnail || ""),
        "Intro mode: " + (data.intro_mode || ""),
        "Duration: " + (data.duration || ""),
        "Intro: " + (data.intro_duration || ""),
        "Cuts: " + (data.cut_count || ""),
        "LLM: " + (data.llm_status || "") + " cost: " + (data.llm_actual_cost_usd || data.llm_estimated_cost_usd || ""),
        "YouTube: " + (data.youtube_status || "") + " " + (data.youtube_url || ""),
        "Elapsed seconds: " + (data.elapsed_seconds || ""),
        "Max RSS MB: " + (data.max_rss_mb || ""),
        "Error: " + (data.error || "")
      ];
      return lines.join("\\n");
    }}

    function updateRenderLinks(data) {{
      const links = [];
      if (data.final_url) {{
        links.push('<a href="' + data.final_url + '" target="_blank">Open final.mp4</a>');
      }}
      if (data.thumbnail_url) {{
        links.push('<a href="' + data.thumbnail_url + '" target="_blank">Open thumbnail.jpg</a>');
      }}
      if (data.youtube_url) {{
        links.push('<a href="' + data.youtube_url + '" target="_blank">Open YouTube</a>');
      }}
      renderLinks.innerHTML = links.join(" &middot; ");
    }}

    async function loadRenderStatus() {{
      try {{
        const response = await fetch("/render-status", {{ cache: "no-store" }});
        const data = await response.json();
        renderOutput.textContent = renderStatusText(data);
        updateRenderLinks(data);
        renderButton.disabled = data.state === "running" || data.state === "queued";
      }} catch (_err) {{
        renderOutput.textContent = "Could not load render status.";
      }}
    }}

    renderButton.addEventListener("click", async () => {{
      renderButton.disabled = true;
      renderOutput.textContent = "Starting server render...";
      try {{
        const response = await fetch("/render-latest", {{ method: "POST" }});
        const data = await response.json();
        renderOutput.textContent = renderStatusText(data);
        updateRenderLinks(data);
      }} catch (_err) {{
        renderOutput.textContent = "Render start failed.";
        renderButton.disabled = false;
      }}
    }});

    document.addEventListener("click", async (event) => {{
      const target = event.target;
      if (!target || !target.classList || !target.classList.contains("render-upload-button")) {{
        return;
      }}
      const filename = decodeURIComponent(target.dataset.file || "");
      target.disabled = true;
      renderButton.disabled = true;
      renderOutput.textContent = "Starting render for " + filename + "...";
      try {{
        const response = await fetch("/render-file?file=" + encodeURIComponent(filename), {{ method: "POST" }});
        const data = await response.json();
        renderOutput.textContent = renderStatusText(data);
        updateRenderLinks(data);
      }} catch (_err) {{
        renderOutput.textContent = "Render start failed.";
        target.disabled = false;
        renderButton.disabled = false;
      }}
    }});

    window.setInterval(loadRenderStatus, 5000);
    loadRenderStatus();
  </script>
</body>
</html>"""
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def auto_start_render(self, filename: str | None = None) -> None:
        if not env_bool("AUTO_RENDER_ON_UPLOAD", True):
            return
        global render_process
        if render_process and render_process.poll() is None:
            return

        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = OUTPUT_ROOT / "render-launch.log"
        write_render_status(
            {
                "state": "queued",
                "step": "launch",
                "upload_dir": str(UPLOAD_DIR),
                "output_root": str(OUTPUT_ROOT),
                "log": str(log_path),
                "trigger": "auto-upload",
                "selected_upload": filename or "",
            }
        )
        script = Path(__file__).with_name("phone_render_worker.py")
        env = os.environ.copy()
        if filename:
            env["AGENTZERO_INPUT_FILE"] = filename
        log_file = log_path.open("ab", buffering=0)
        render_process = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(script.parent),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=True,
        )

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/render-status":
            self.send_json(current_render_status())
            return
        if path == "/pipeline-info":
            self.send_json(pipeline_info())
            return
        if path.startswith("/outputs/"):
            self.send_output(path)
            return
        if path not in ("", "/"):
            self.send_error(404, "Not found")
            return

        payload = page()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/render-latest":
            self.start_render()
            return
        if path == "/render-file":
            query = parse_qs(urlparse(self.path).query)
            filename = query.get("file", [""])[0]
            self.start_render(filename)
            return
        if path == "/upload-chunk":
            self.handle_upload_chunk()
            return

        content_type = self.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_error(400, "Expected multipart/form-data")
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
        )
        field = form["video"] if "video" in form else None
        if isinstance(field, list):
            field = field[0] if field else None
        if field is None or not getattr(field, "file", None):
            self.send_error(400, "Missing video field")
            return

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        filename = safe_filename(getattr(field, "filename", "upload.mov"))
        destination = UPLOAD_DIR / filename
        partial = UPLOAD_DIR / f"{filename}.part"

        with partial.open("wb") as out_file:
            shutil.copyfileobj(field.file, out_file, length=1024 * 1024)
        partial.rename(destination)
        self.auto_start_render(filename)

        if self.headers.get("X-Requested-With") == "XMLHttpRequest":
            payload = json.dumps(
                {
                    "ok": True,
                    "filename": filename,
                    "size_mb": round(destination.stat().st_size / (1024 * 1024), 1),
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(303)
        self.send_header("Location", f"/?uploaded={quote(filename)}")
        self.end_headers()

    def handle_upload_chunk(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        upload_id = safe_upload_id(query.get("upload_id", [""])[0])
        original_name = Path(unquote(query.get("filename", ["upload.mov"])[0])).name
        try:
            index = int(query.get("index", [""])[0])
            total = int(query.get("total", [""])[0])
            expected_size = int(query.get("size", [""])[0])
            content_length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            self.send_json({"ok": False, "error": "Invalid chunk metadata"}, 400)
            return
        if total <= 0 or index < 0 or index >= total or expected_size <= 0 or content_length <= 0:
            self.send_json({"ok": False, "error": "Invalid chunk bounds"}, 400)
            return
        if Path(original_name).suffix.lower() not in ALLOWED_EXTENSIONS:
            self.send_json({"ok": False, "error": "Unsupported upload extension"}, 400)
            return

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        root = upload_chunk_root(upload_id)
        chunks_dir = root / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        meta_path = root / "meta.json"

        if index == 0 and not meta_path.exists():
            meta = {
                "upload_id": upload_id,
                "original_name": original_name,
                "filename": safe_filename(original_name),
                "expected_size": expected_size,
                "total": total,
                "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")
        if not meta_path.exists():
            self.send_json({"ok": False, "error": "Upload session missing; restart upload"}, 409)
            return

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            self.send_json({"ok": False, "error": "Upload session metadata is invalid"}, 409)
            return
        if int(meta.get("expected_size", -1)) != expected_size or int(meta.get("total", -1)) != total:
            self.send_json({"ok": False, "error": "Upload metadata mismatch; restart upload"}, 409)
            return

        chunk_path = chunks_dir / f"{index:06d}.chunk"
        chunk_tmp = chunks_dir / f"{index:06d}.chunk.tmp"
        remaining = content_length
        with chunk_tmp.open("wb") as out_file:
            while remaining > 0:
                data = self.rfile.read(min(1024 * 1024, remaining))
                if not data:
                    break
                out_file.write(data)
                remaining -= len(data)
        actual_size = chunk_tmp.stat().st_size
        if actual_size != content_length:
            try:
                chunk_tmp.unlink()
            except FileNotFoundError:
                pass
            self.send_json({"ok": False, "error": f"Chunk size mismatch: got {actual_size}, expected {content_length}"}, 400)
            return
        chunk_tmp.replace(chunk_path)

        chunk_paths = [chunks_dir / f"{item:06d}.chunk" for item in range(total)]
        received = sum(path.stat().st_size for path in chunk_paths if path.exists())
        complete = all(path.exists() for path in chunk_paths)
        if not complete:
            self.send_json({
                "ok": True,
                "complete": False,
                "received_bytes": received,
                "expected_size": expected_size,
                "chunk": index,
                "total": total,
            })
            return

        if received != expected_size:
            self.send_json({"ok": False, "error": f"Final size mismatch: got {received}, expected {expected_size}"}, 409)
            return

        filename = str(meta.get("filename") or safe_filename(original_name))
        destination = UPLOAD_DIR / filename
        partial = UPLOAD_DIR / f"{filename}.part"
        with partial.open("wb") as out_file:
            for path in chunk_paths:
                with path.open("rb") as in_file:
                    shutil.copyfileobj(in_file, out_file, length=1024 * 1024)
        if partial.stat().st_size != expected_size:
            partial.unlink(missing_ok=True)
            self.send_json({"ok": False, "error": "Assembled file size mismatch"}, 409)
            return
        partial.replace(destination)
        shutil.rmtree(root, ignore_errors=True)
        self.auto_start_render(filename)
        self.send_json({
            "ok": True,
            "complete": True,
            "filename": filename,
            "size_mb": round(destination.stat().st_size / (1024 * 1024), 1),
            "received_bytes": expected_size,
        })

    def send_json(self, data: dict, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_output(self, request_path: str) -> None:
        raw_rel = request_path.removeprefix("/outputs/").strip("/")
        if not raw_rel:
            self.send_error(404, "Missing output path")
            return

        rel_parts = [unquote(part) for part in raw_rel.split("/") if part]
        target = (OUTPUT_ROOT / Path(*rel_parts)).resolve()
        root = OUTPUT_ROOT.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            self.send_error(403, "Invalid output path")
            return
        if not target.is_file():
            self.send_error(404, "Output file not found")
            return

        total = target.stat().st_size
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        range_header = self.headers.get("Range", "")
        start = 0
        end = total - 1
        status_code = 200

        if range_header.startswith("bytes="):
            try:
                range_value = range_header.removeprefix("bytes=").split(",", 1)[0]
                start_text, end_text = range_value.split("-", 1)
                start = int(start_text) if start_text else 0
                end = int(end_text) if end_text else total - 1
                start = max(0, min(start, total - 1))
                end = max(start, min(end, total - 1))
                status_code = 206
            except Exception:
                start = 0
                end = total - 1
                status_code = 200

        length = end - start + 1
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", f'inline; filename="{target.name}"')
        if status_code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.end_headers()

        with target.open("rb") as file:
            file.seek(start)
            remaining = length
            while remaining > 0:
                chunk = file.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def start_render(self, filename: str | None = None) -> None:
        global render_process
        if render_process and render_process.poll() is None:
            self.send_json(current_render_status() | {"ok": True, "message": "Render already running"}, 202)
            return

        selected_upload = ""
        if filename:
            try:
                selected_upload = resolve_upload_reference(filename).name
            except FileNotFoundError:
                self.send_json({"ok": False, "error": f"Upload not found: {Path(filename).name}"}, 404)
                return
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, 400)
                return

        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = OUTPUT_ROOT / "render-launch.log"
        write_render_status(
            {
                "state": "queued",
                "step": "launch",
                "upload_dir": str(UPLOAD_DIR),
                "output_root": str(OUTPUT_ROOT),
                "log": str(log_path),
                "selected_upload": selected_upload,
            }
        )

        script = Path(__file__).with_name("phone_render_worker.py")
        env = os.environ.copy()
        if selected_upload:
            env["AGENTZERO_INPUT_FILE"] = selected_upload
        log_file = log_path.open("ab", buffering=0)
        render_process = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(script.parent),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=True,
        )
        self.send_json(current_render_status() | {"ok": True, "pid": render_process.pid}, 202)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[phone-upload] {self.address_string()} - {fmt % args}", flush=True)


def current_render_status() -> dict:
    status = read_render_status()
    if status.get("final"):
        status["final_url"] = output_url_for(str(status["final"]))
    if status.get("thumbnail"):
        status["thumbnail_url"] = output_url_for(str(status["thumbnail"]))
    if render_process and render_process.poll() is None:
        status["process"] = "running"
    elif render_process:
        status["process"] = "exited"
        status["process_exit_code"] = render_process.poll()
    return status


def main() -> int:
    host = os.getenv("AGENTZERO_UPLOAD_HOST", "0.0.0.0")
    port = int(os.getenv("AGENTZERO_UPLOAD_PORT", "8080"))
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[phone-upload] Listening on http://{host}:{port}", flush=True)
    print(f"[phone-upload] Saving uploads to {UPLOAD_DIR}", flush=True)
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
