#!/usr/bin/env python3
"""Print a base64 campaign config value for Coolify.

Usage:
  python cloud/mobile-home/encode_campaign_config.py cloud/mobile-home/config-examples/generic-client-campaign.json
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python cloud/mobile-home/encode_campaign_config.py path/to/campaign.json", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    normalized = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(normalized).decode("ascii")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
