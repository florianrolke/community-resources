"""
Checkpoint/Resume for Batch Processing

Saves progress every N records so long-running jobs survive interruptions.
Production-tested on 10,000+ member enrichment runs.

Usage:
    from lib.checkpoint import CheckpointManager

    cp = CheckpointManager("chamber_enrichment", save_every=5, output_dir=".tmp")

    for item in items:
        if cp.is_done(item["name"]):
            continue
        result = process(item)
        cp.save_result(item["name"], result)

    cp.finalize()  # Final save
"""

import json
import signal
import sys
from pathlib import Path
from typing import Any

from scripts.lib.safe_io import safe_json_write, safe_json_read


class CheckpointManager:
    """Manages checkpoint/resume for batch processing.

    Args:
        name: Checkpoint name (used for filename)
        save_every: Save checkpoint every N records
        output_dir: Directory for checkpoint file (default: .tmp)
    """

    def __init__(self, name: str, save_every: int = 5, output_dir: str = ".tmp"):
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"checkpoint_{name}.json"
        self._save_every = save_every
        self._count = 0
        self._dirty = False

        # Load existing checkpoint
        self._data: dict[str, Any] = {}
        if self._path.exists():
            self._data = safe_json_read(self._path) or {}
            print(f"  [CHECKPOINT] Resumed with {len(self._data)} existing results")

        # Register graceful shutdown
        self._original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._graceful_shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._graceful_shutdown)

    def is_done(self, key: str) -> bool:
        """Check if a key has already been processed."""
        return key in self._data

    def save_result(self, key: str, result: Any):
        """Save a result and auto-checkpoint every N records."""
        self._data[key] = result
        self._count += 1
        self._dirty = True

        if self._count % self._save_every == 0:
            self._write_checkpoint()
            print(f"  [CHECKPOINT] Saved at {len(self._data)} records")

    def get_result(self, key: str) -> Any:
        """Retrieve a previously saved result."""
        return self._data.get(key)

    @property
    def results(self) -> dict:
        """All saved results."""
        return self._data

    @property
    def count(self) -> int:
        """Number of results saved."""
        return len(self._data)

    def finalize(self):
        """Final save and restore signal handlers."""
        if self._dirty:
            self._write_checkpoint()
            print(f"  [CHECKPOINT] Final save: {len(self._data)} records")
        signal.signal(signal.SIGINT, self._original_sigint)

    def _write_checkpoint(self):
        safe_json_write(self._path, self._data)
        self._dirty = False

    def _graceful_shutdown(self, signum, frame):
        if self._dirty:
            print(f"\n  [INTERRUPT] Saving checkpoint ({len(self._data)} records)...")
            self._write_checkpoint()
            print("  [SAVED] Safe to exit.")
        sys.exit(0)
