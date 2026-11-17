"""Generate the art pictures with the image model of your choice. The rest of the pipeline only needs PNG files in
source-art/, so the model is exchangeable: pick a provider here, use any image tool your agent already has (an MCP
image tool such as Floot), or drop in pictures you made elsewhere.

    python generate.py prompts.json --provider openai              (OPENAI_API_KEY)
    python generate.py prompts.json --provider gemini              (GEMINI_API_KEY)
    python generate.py prompts.json --provider replicate           (REPLICATE_API_TOKEN)
    python generate.py prompts.json --provider file                (copies the files named in "file")
    python generate.py prompts.json --provider openai --dry-run    (shows each request; sends nothing, costs nothing)

prompts.json: [{"name": "jaguar", "prompt": "...", "refs": ["refs/blog-photo.jpg"], "file": "optional/own.png"}, ...]
Pictures are written to source-art/<name>.png next to prompts.json (or --out). An existing file is never overwritten:
the new one gets a -2, -3 ... suffix, so earlier rounds stay available.

Every generation costs money on the paid providers. Run --dry-run first and agree the number of pictures with the
person paying. Provider request formats follow the public API documentation; if a provider changes its API, only the
small function for that provider needs updating. --model picks another model of the same provider.
"""
import argparse
import base64
import json
import mimetypes
import os
import pathlib
import shutil
import sys
import time
import urllib.request
import uuid

DEFAULT_MODELS = {"openai": "gpt-image-1", "gemini": "gemini-2.5-flash-image", "replicate": "black-forest-labs/flux-1.1-pro",
                  "replicate-refs": "black-forest-labs/flux-kontext-pro"}


def post(url, body, headers, dry, label):
    if dry:
        shown = body if isinstance(body, dict) else f"<multipart, {len(body)} bytes>"
        print(json.dumps({"would_send": label, "url": url, "body": shown}, default=str)[:1500])
        return None
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def b64file(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()


def openai(item, model, dry):
    key = os.environ.get("OPENAI_API_KEY", "" if dry else None)
    assert key is not None, "set OPENAI_API_KEY"
    if not item.get("refs"):
        r = post("https://api.openai.com/v1/images/generations",
                 {"model": model, "prompt": item["prompt"], "size": item.get("size", "1536x1024"), "n": 1},
                 {"Authorization": "Bearer " + key, "Content-Type": "application/json"}, dry, item["name"])
    else:  # reference pictures go to the edits endpoint as multipart form data
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in (("model", model), ("prompt", item["prompt"]), ("size", item.get("size", "1536x1024"))):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for ref in item["refs"]:
            mime = mimetypes.guess_type(ref)[0] or "image/png"
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; filename="{pathlib.Path(ref).name}"\r\n'
                         f'Content-Type: {mime}\r\n\r\n'.encode() + pathlib.Path(ref).read_bytes() + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        r = post("https://api.openai.com/v1/images/edits", body,
                 {"Authorization": "Bearer " + key, "Content-Type": "multipart/form-data; boundary=" + boundary}, dry, item["name"])
    return None if r is None else base64.b64decode(r["data"][0]["b64_json"])


def gemini(item, model, dry):
    key = os.environ.get("GEMINI_API_KEY", "" if dry else None)
    assert key is not None, "set GEMINI_API_KEY"
    parts = [{"text": item["prompt"]}]
    for ref in item.get("refs", []):
        parts.append({"inline_data": {"mime_type": mimetypes.guess_type(ref)[0] or "image/png",
                                      "data": "<base64>" if dry else b64file(ref)}})
    r = post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
             {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
             {"x-goog-api-key": key, "Content-Type": "application/json"}, dry, item["name"])
    if r is None:
        return None
    for part in r["candidates"][0]["content"]["parts"]:
        blob = part.get("inlineData") or part.get("inline_data")
        if blob:
            return base64.b64decode(blob["data"])
    raise RuntimeError("no picture in the answer: " + json.dumps(r)[:400])


def replicate(item, model, dry):
    key = os.environ.get("REPLICATE_API_TOKEN", "" if dry else None)
    assert key is not None, "set REPLICATE_API_TOKEN"
    inp = {"prompt": item["prompt"], "aspect_ratio": item.get("aspect_ratio", "16:9"), "output_format": "png"}
    if item.get("refs"):  # flux-kontext style models take one input image; data URIs are accepted
        ref = item["refs"][0]
        inp["input_image"] = "<data uri>" if dry else f"data:{mimetypes.guess_type(ref)[0] or 'image/png'};base64,{b64file(ref)}"
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "Prefer": "wait"}
    r = post(f"https://api.replicate.com/v1/models/{model}/predictions", {"input": inp}, headers, dry, item["name"])
    if r is None:
        return None
    poll = r.get("urls", {}).get("get", "")
    assert poll.startswith("https://api.replicate.com/"), "unexpected status address; the key is only sent to api.replicate.com"
    while r.get("status") not in ("succeeded", "failed", "canceled"):
        time.sleep(3)
        with urllib.request.urlopen(urllib.request.Request(poll, headers=headers), timeout=60) as resp:
            r = json.loads(resp.read())
    assert r["status"] == "succeeded", r.get("error")
    out = r["output"][0] if isinstance(r["output"], list) else r["output"]
    with urllib.request.urlopen(out, timeout=120) as resp:
        return resp.read()


def save(data, out, name):
    out.mkdir(parents=True, exist_ok=True)
    target, n = out / f"{name}.png", 2
    while target.exists():
        target, n = out / f"{name}-{n}.png", n + 1
    target.write_bytes(data)
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompts")
    ap.add_argument("--provider", required=True, choices=["openai", "gemini", "replicate", "file"])
    ap.add_argument("--model")
    ap.add_argument("--out")
    ap.add_argument("--only", nargs="*", help="names to generate (default: all)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pf = pathlib.Path(a.prompts)
    items = json.loads(pf.read_text(encoding="utf-8"))
    out = pathlib.Path(a.out) if a.out else pf.parent / "source-art"
    for item in items:
        if a.only and item["name"] not in a.only:
            continue
        item["refs"] = [str((pf.parent / r).resolve()) for r in item.get("refs", [])]
        if a.provider == "file":
            src = pf.parent / item["file"]
            target = out / f"{item['name']}{src.suffix.lower()}"
            if a.dry_run:
                print(json.dumps({"would_copy": str(src), "to": str(target)}))
                continue
            out.mkdir(parents=True, exist_ok=True)
            if target.exists():
                print(json.dumps({"name": item["name"], "kept": str(target)}))
                continue
            shutil.copy2(src, target)
            print(json.dumps({"name": item["name"], "saved": str(target)}))
            continue
        model = a.model or DEFAULT_MODELS["replicate-refs" if a.provider == "replicate" and item["refs"] else a.provider]
        data = {"openai": openai, "gemini": gemini, "replicate": replicate}[a.provider](item, model, a.dry_run)
        if data is not None:
            print(json.dumps({"name": item["name"], "model": model, "saved": str(save(data, out, item["name"]))}))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
