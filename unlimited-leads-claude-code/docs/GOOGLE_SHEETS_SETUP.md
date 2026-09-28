# Google Sheets setup (optional)

**You probably don't need this.** Every script writes CSV, which opens fine in
Excel, Numbers, and Google Sheets. This is only worth doing if you want leads
landing in a live sheet your team edits.

It's also where most people get stuck, which is why it's opt-in.

## Setup

1. **Create a project** — [console.cloud.google.com](https://console.cloud.google.com), new project, any name.

2. **Enable two APIs** — APIs & Services → Library → enable **Google Sheets API** and **Google Drive API**.

3. **Create credentials** — APIs & Services → Credentials → Create credentials →
   OAuth client ID → **Desktop app**. If it asks you to configure a consent
   screen first: External, fill the required fields, and add your own email as a
   test user.

4. **Download the JSON** and save it as `credentials.json` in the repo root
   (next to `README.md`, not inside `scripts/`).

5. **Authorize once**:
   ```bash
   python -X utf8 scripts/common/read_sheet.py --sheet-url "https://docs.google.com/spreadsheets/d/YOUR_ID"
   ```
   A browser opens. Approve it. That writes `token.json` and it won't ask again.

Both files are gitignored. Never commit either.

## Use

```bash
# Scrape straight into a sheet
python -X utf8 scripts/02_local_businesses/gmaps_lead_pipeline.py \
    --search "barbers in Tuscaloosa AL" --limit 25 \
    --sheet-url "https://docs.google.com/spreadsheets/d/YOUR_ID"

# Push a file you already have
python -X utf8 scripts/common/update_sheet.py --input output/leads.csv --sheet-url "https://..."
```

Leave `--sheet-url` off and nothing Google-related runs — no browser, no credentials.

## Problems

| Symptom | Fix |
|---|---|
| "credentials.json not found" | It belongs in the repo root, not `scripts/`. |
| Browser opens every run | Delete `token.json`, authorize again. |
| 403 on an existing sheet | The account you authorized can't edit it. |
| "access blocked: not verified" | Add your email as a test user on the consent screen. |
| Quota errors | Sheets rate-limits writes. Use CSV past a few thousand rows. |
