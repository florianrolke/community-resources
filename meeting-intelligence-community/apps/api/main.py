"""FastAPI webhook receiver for Fathom meeting transcripts."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from meeting_intelligence.core.config import settings
from meeting_intelligence.core.fathom import parse_payload_bytes, recording_id, verify_webhook_signature
from meeting_intelligence.core.storage import enqueue_payload, processed_ids, read_json
from meeting_intelligence.vectorizer.neo4j_store import search_transcripts


cfg = settings()
app = FastAPI(title="Meeting Intelligence API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "app": cfg.app_name}


@app.post("/webhook/fathom")
async def fathom_webhook(request: Request):
    raw_body = await request.body()
    if not verify_webhook_signature(cfg.fathom_webhook_secret, dict(request.headers), raw_body):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = parse_payload_bytes(raw_body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    source_id = recording_id(payload)
    if source_id in processed_ids(cfg):
        return JSONResponse(status_code=200, content={"status": "duplicate", "source_id": source_id})

    job_path = enqueue_payload(cfg, payload)
    return JSONResponse(status_code=202, content={"status": "accepted", "source_id": source_id, "job": str(job_path)})


@app.get("/meetings/{source_id}")
def meeting_artifact(source_id: str):
    artifact = read_json(cfg.summaries_dir / f"{source_id}.json", None)
    if not artifact:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return artifact


@app.get("/search")
def semantic_search(q: str, limit: int = 5):
    if not cfg.neo4j_enabled:
        raise HTTPException(status_code=400, detail="Neo4j is disabled")
    return {"query": q, "results": search_transcripts(cfg, q, limit)}


@app.get("/local-docs/{source_id}")
def local_doc_notice(source_id: str):
    artifact = read_json(cfg.summaries_dir / f"{source_id}.json", None)
    if not artifact:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return {"message": "Google Docs disabled. Summary artifact returned instead.", "artifact": artifact}
