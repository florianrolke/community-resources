# Setup

1. Create a virtual environment.
2. Install dependencies: `pip install -e .[test]`.
3. Copy `.env.example` to `.env` and add only the keys needed for the source you are using.
4. Run tests with `pytest`.
5. Start every paid-source workflow with dry-run mode.

Useful commands:

```powershell
python scripts/generate_event_queries.py --niche "manufactured housing" --city "Las Vegas" --year 2026 --event-name "MHI 2026 Congress & Expo"
python scripts/run_apify_event_actor.py --actor 10times --payload-json tests/fixtures/apify_10times_payload.json --dry-run
pytest
```