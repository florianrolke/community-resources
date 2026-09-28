"""Environment-driven configuration for the meeting intelligence package."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "meeting-intelligence")
    host_name: str = os.getenv("HOST_NAME", "Your Name")
    host_email: str = os.getenv("HOST_EMAIL", "you@example.com").lower()
    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8080")

    fathom_api_key: str = os.getenv("FATHOM_API_KEY", "")
    fathom_webhook_secret: str = os.getenv("FATHOM_WEBHOOK_SECRET", "")
    fathom_poll_minutes: int = env_int("FATHOM_POLL_MINUTES", 15)

    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_summary_model: str = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
    gemini_summary_model: str = os.getenv("GEMINI_SUMMARY_MODEL", "gemini-1.5-flash")

    google_docs_enabled: bool = env_bool("GOOGLE_DOCS_ENABLED", False)
    gmail_drafts_enabled: bool = env_bool("GMAIL_DRAFTS_ENABLED", False)
    google_calendar_enabled: bool = env_bool("GOOGLE_CALENDAR_ENABLED", False)
    google_docs_token_json: str = os.getenv("GOOGLE_DOCS_TOKEN_JSON", "")
    google_gmail_token_json: str = os.getenv("GOOGLE_GMAIL_TOKEN_JSON", "")
    google_calendar_token_json: str = os.getenv("GOOGLE_CALENDAR_TOKEN_JSON", "")
    google_docs_template_id: str = os.getenv("GOOGLE_DOCS_TEMPLATE_ID", "")
    google_drive_folder_id: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    neo4j_enabled: bool = env_bool("NEO4J_ENABLED", True)
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "meeting-intelligence-password")
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimension: int = env_int("EMBEDDING_DIMENSION", 1536)
    chunk_words: int = env_int("CHUNK_WORDS", 420)
    chunk_overlap_words: int = env_int("CHUNK_OVERLAP_WORDS", 60)

    contacts_path: Path = Path(os.getenv("CONTACTS_PATH", "data/config/contacts.json"))
    style_policy_path: Path = Path(os.getenv("STYLE_POLICY_PATH", "data/config/email_style_policy.json"))
    doc_config_path: Path = Path(os.getenv("DOC_CONFIG_PATH", "data/config/google_doc_config.json"))

    next_meeting_days: int = env_int("NEXT_MEETING_DAYS", 7)

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def transcripts_dir(self) -> Path:
        return self.data_dir / "transcripts"

    @property
    def summaries_dir(self) -> Path:
        return self.data_dir / "summaries"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    def ensure_dirs(self) -> None:
        for path in [
            self.data_dir,
            self.raw_dir,
            self.jobs_dir,
            self.processed_dir,
            self.transcripts_dir,
            self.summaries_dir,
            self.state_dir,
            self.contacts_path.parent,
            self.style_policy_path.parent,
            self.doc_config_path.parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def settings() -> Settings:
    cfg = Settings()
    cfg.ensure_dirs()
    return cfg
