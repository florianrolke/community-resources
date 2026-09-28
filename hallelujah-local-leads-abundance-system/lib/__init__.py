"""
Hallelujah Local Leads Abundance System — Shared Library

Common utilities used across all 4 pillars:
- Chamber of Commerce Scraper
- BNI Chapter Scraper
- Magazine Advertiser Pipeline
- Waterfall Enrichment Engine
"""

from lib.windows_compat import fix_encoding
from lib.icp_classifier import classify_business
from lib.api_key_rotation import KeyRotator
from lib.checkpoint import CheckpointManager
from lib.linkedin_validator import extract_linkedin_url, validate_linkedin_for_person
from lib.rate_limiter import rate_limited_delay
from lib.safe_io import safe_json_write, safe_json_read

# Auto-fix Windows encoding on import
fix_encoding()
