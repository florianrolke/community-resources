import json
from pathlib import Path

from meeting_intelligence.core.config import Settings
from meeting_intelligence.core.pipeline import process_payload


def test_pipeline_writes_artifact_with_google_and_neo4j_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    payload = json.loads(Path("examples/sample_fathom_payload.json").read_text(encoding="utf-8"))
    cfg = Settings(
        data_dir=tmp_path,
        host_name="Your Name",
        host_email="you@example.com",
        llm_provider="fallback",
        google_docs_enabled=False,
        gmail_drafts_enabled=False,
        neo4j_enabled=False,
        contacts_path=tmp_path / "config" / "contacts.json",
        style_policy_path=tmp_path / "config" / "email_style_policy.json",
        doc_config_path=tmp_path / "config" / "google_doc_config.json",
    )
    cfg.ensure_dirs()
    cfg.contacts_path.write_text('{"Alex Example": "alex@example.com"}', encoding="utf-8")
    artifact = process_payload(cfg, payload)
    assert artifact["source_id"] == "sample-001"
    assert artifact["doc"]["enabled"] is False
    assert artifact["gmail"]["enabled"] is False
    assert (tmp_path / "summaries" / "sample-001.json").exists()
    assert (tmp_path / "transcripts" / "sample-001.txt").exists()
