# Setup Notes

1. Copy `.env.example` to `.env` and add only the keys needed for the workflow.
2. Install dependencies with `python -m pip install -e .[test]`. Add `[browser]` for Genspark automation or `[vision]` for OCR.
3. Run commands from the repo root. If scripts cannot import `scripts.common` on Windows, set `PYTHONPATH` to the repo root for that shell session:
   `PowerShell: $env:PYTHONPATH=(Get-Location).Path`
4. For no-manual-research runs, configure `APIFY_API_TOKEN` and keep `APIFY_SERP_ACTOR=apify/google-search-scraper` unless you intentionally choose another SERP actor.
5. For assisted Genspark paste, start Chrome with remote debugging, open Genspark manually, then run `scripts/genspark_assisted.py`.
6. Generated campaign data belongs in `data/` or `.tmp/`; do not commit private reports or API outputs.
