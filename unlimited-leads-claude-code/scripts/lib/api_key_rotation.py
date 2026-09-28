"""
API Key Rotation with Exhaustion Tracking

Manages multiple API keys per service (Exa, Tavily, Perplexity) with:
- Round-robin rotation across available keys
- Exhaustion tracking (marks keys as spent when rate-limited)
- Graceful degradation (returns None when all keys exhausted)

Production-tested across 40,000+ API calls with 6 keys per service.

Usage:
    from lib.api_key_rotation import KeyRotator

    exa = KeyRotator("EXA_API_KEY", num_keys=6)
    key = exa.get_key()        # Returns next available key
    exa.mark_exhausted(key)    # Mark key as rate-limited
    remaining = exa.remaining  # How many keys are left
"""

import os
from typing import Optional


class KeyRotator:
    """Rotates API keys with exhaustion tracking.

    Supports two naming patterns:
    - SERVICE_API_KEY, SERVICE_API_KEY_2, SERVICE_API_KEY_3, ...
    - Or custom key names passed directly

    Args:
        base_env_name: Base environment variable name (e.g., "EXA_API_KEY")
        num_keys: Total number of keys (1=just base, 6=base + _2 through _6)
        start_index: Which key to start with (0-based). Use this to skip exhausted keys.
        key_names: Optional explicit list of env var names (overrides base_env_name + num_keys)
    """

    def __init__(self, base_env_name: str, num_keys: int = 6,
                 start_index: int = 0, key_names: list[str] = None):
        if key_names:
            self._key_names = key_names
        else:
            self._key_names = [base_env_name]
            for i in range(2, num_keys + 1):
                self._key_names.append(f"{base_env_name}_{i}")

        self._index = start_index
        self._exhausted: set[str] = set()
        self._service_name = base_env_name.replace("_API_KEY", "").replace("_API_TOKEN", "")

    def get_key(self) -> Optional[str]:
        """Get the next available API key. Returns None if all exhausted."""
        available = []
        for name in self._key_names:
            key = os.environ.get(name)
            if key and key not in self._exhausted:
                available.append(key)

        if not available:
            return None

        key = available[self._index % len(available)]
        self._index += 1
        return key

    def mark_exhausted(self, key: str):
        """Mark a key as exhausted (rate-limited / quota exceeded)."""
        self._exhausted.add(key)
        remaining = self.remaining
        print(f"    [KEY ROTATION] {self._service_name} key exhausted. {remaining} keys remaining.")

    @property
    def remaining(self) -> int:
        """Number of non-exhausted keys with values set."""
        return sum(
            1 for name in self._key_names
            if os.environ.get(name) and os.environ.get(name) not in self._exhausted
        )

    @property
    def all_exhausted(self) -> bool:
        """True if every key has been marked exhausted or is unset."""
        return self.remaining == 0
