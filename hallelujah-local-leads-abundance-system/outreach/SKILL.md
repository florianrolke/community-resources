# Form Outreach Engine

> Submit personalized messages through prospect contact forms — chambers and direct websites. The prospect sees an inbound inquiry, not cold email.

## Architecture

```
Enriched Leads (JSON)
  → Message Template + Personalization
    → Playwright navigates to contact form
      → Intelligent form detection (multi-form scoring)
        → Field classification (name, email, phone, subject, message)
          → React/Wix-safe filling (native value setter)
            → CAPTCHA solving (CapSolver API)
              → Submit + verify + screenshot
                → Log results (JSON + before/after PNGs)
```

## Scripts

| Script | Purpose | Lines |
|--------|---------|-------|
| `chamber_form_outreach.py` | Submit via chamber member profile contact forms | 592 |
| `website_form_outreach.py` | Submit via any prospect website contact form | 1,015 |

## Quick Start

```bash
# 1. Chamber form — single submission
python -X utf8 outreach/chamber_form_outreach.py \
    --url "https://local.meadowlands.org/Business-Services/Example-1609" \
    --name "Your Name" --email "you@example.com" \
    --message "Hi, I saw your listing in the Meadowlands Chamber..."

# 2. Website form — single submission
python -X utf8 outreach/website_form_outreach.py \
    --url "https://www.example.com" \
    --name "Your Name" --email "you@example.com" \
    --message "Hello, I'm reaching out because..."

# 3. Batch mode (5 at a time)
python -X utf8 outreach/website_form_outreach.py \
    --batch leads/website_outreach.json --limit 5

# 4. Dry run (fill forms but don't submit)
python -X utf8 outreach/chamber_form_outreach.py \
    --batch leads/weekly_outreach.json --dry-run
```

## How Form Detection Works

### Multi-Form Page Scoring

Most websites have 2-3 forms (contact + newsletter + search). The detection algorithm scores each `<form>`:

| Factor | Points | Rationale |
|--------|--------|-----------|
| Each visible input | +1 | More inputs = likely contact form |
| Has textarea | +5 | Newsletters never have textareas |
| Inside footer | -10 | Footer forms = newsletter subscribe |

Highest score wins. All field detection is scoped to the winning form.

### Field Classification

Fields are classified by combining 6 context strings:
```
context = name + id + placeholder + label_text + sibling_text + aria_label
```

| Field | Matches |
|-------|---------|
| `first_name` | "first" + "name", "fname", "vorname" |
| `last_name` | "last" + "name", "lname", "nachname" |
| `name` | "name" (but NOT email/company/user) |
| `email` | "email" or `type="email"` |
| `phone` | "phone", "tel", `type="tel"` |
| `subject` | "subject", "subj", "betreff" |
| `company` | "company", "organization", "firma" |
| `message` | First visible textarea (not CAPTCHA) |

### Submit Button Detection

Matches: `send|submit|contact|get in touch|request|anfrage|absenden`

**Critical:** Many business sites use "Request a Conversation" — the regex MUST include `request`.

## Wix/React Form Filling

Standard Playwright `page.fill()` fails on React-controlled inputs. The solution:

### Native Input Value Setter

```python
# Bypasses React's synthetic event system
nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
).set;
nativeSetter.call(element, value);
element.dispatchEvent(new Event('input', { bubbles: true }));
element.dispatchEvent(new Event('change', { bubbles: true }));
```

### Why Click-and-Type Fails on Wix

Clicking a new field triggers React re-render that clears previously filled fields. Solution:
1. Click **only the first field**
2. Use Tab to navigate to next fields
3. Use clipboard paste for long text (>100 chars)
4. 3s pause between fields for human-like timing

### Platform Compatibility

| Platform | Native Setter | Click+Type | Recommended |
|----------|:---:|:---:|------------|
| Wix | Yes | No (clears fields) | Native setter |
| Webflow | Yes | Yes | Either |
| WordPress (CF7) | Yes | Yes | Either |
| ChamberMaster | N/A | Yes | Click+Type |
| Squarespace | Yes | Yes | Either |

## CAPTCHA Handling

### CapSolver Integration

Both scripts use CapSolver API (`CAPSOLVER_API_KEY` in .env) for automated solving:

| CAPTCHA Type | CapSolver Task Type | Notes |
|-------------|-------------------|-------|
| reCAPTCHA v2 | `ReCaptchaV2TaskProxyLess` | Visible checkbox |
| reCAPTCHA v2 invisible | `ReCaptchaV2TaskProxyLess` + `isInvisible` | No visual checkbox |
| reCAPTCHA v3 | `ReCaptchaV3TaskProxyLess` | Invisible, score-based |
| hCaptcha | `HCaptchaTaskProxyLess` | Cloudflare alternative |
| Turnstile | `AntiTurnstileTaskProxyLess` | Cloudflare managed |

### Token Injection Flow

1. Extract site key from `data-sitekey` or iframe `src` parameter
2. Send to CapSolver API (runs in ThreadPoolExecutor to avoid blocking Playwright)
3. Receive token (JWT string)
4. Inject into `textarea[name="g-recaptcha-response"]`
5. Trigger JS callback via `___grecaptcha_cfg.clients[cid].callback(token)`

### Human-Supervised Mode

Chamber script also supports `headless=False` mode where the user manually clicks "I'm not a robot" checkboxes. The automation fills; the human verifies.

## Supported Chamber Platforms

| Platform | Form Type | CAPTCHA | Notes |
|----------|-----------|---------|-------|
| ChamberMaster | Contact tab or inline | Sometimes | "Contact" tab on detail pages |
| GrowthZone | Detail page | Rarely | Often uses mailto: instead |
| ChamberData/CCA | `_memberprofile2.aspx` | Yes (checkbox) | Pre-fills "Referral from [Chamber]" |
| Atlas | Detail page | Varies | Some forms, some mailto: |
| WordPress | Custom pages | Varies | CF7 or WPForms |
| Locable | Profile pages | Yes (checkbox) | Standard reCAPTCHA v2 |

## CLI Arguments

### Chamber Form

```
--url          Single chamber member URL
--name         Sender name (default: OUTREACH_NAME from .env)
--email        Sender email (default: OUTREACH_EMAIL from .env)
--subject      Email subject (auto-generated if empty)
--message      Message body
--batch        Path to JSON batch file
--limit        Max submissions per run (default: 5)
--dry-run      Fill forms but don't submit
--delay        Seconds between submissions (default: 5)
```

### Website Form

```
--url          Single website URL
--name         Sender name
--email        Sender email
--subject      Optional subject
--phone        Optional phone
--company      Target company name
--message      Message body
--batch        Path to JSON batch file
--limit        Max submissions per run (default: 5)
--dry-run      Fill forms but don't submit
--delay        Seconds between submissions (default: 5)
```

## Batch JSON Format

```json
[
  {
    "website": "https://example.com",
    "company_name": "Example Inc",
    "contact_form_url": "https://example.com/contact",
    "message": "Custom message (optional)"
  }
]
```

## Anti-Detection

Both scripts use stealth browser configuration:
- Custom user agent (Chrome 131)
- `--disable-blink-features=AutomationControlled`
- `navigator.webdriver` hidden via init script
- `window.chrome = { runtime: {} }` spoofing
- Persistent browser profile (cookie retention)
- Human-like delays between field fills (2-3s)

## Output

- **Log:** `.tmp/outreach_log.json` (chamber) / `.tmp/website_outreach_log.json` (website)
- **Screenshots:** `.tmp/outreach_screenshots/` and `.tmp/website_outreach_screenshots/`
- Both save after EVERY submission for crash recovery

## Rate Limiting

- **Max 5 submissions per chamber per day** to avoid being flagged
- Default 5-second delay between submissions (`--delay`)
- Human-supervised mode for reCAPTCHA v2 checkboxes when needed

## API Budget

| Item | Cost |
|------|------|
| CapSolver reCAPTCHA v2 | ~$0.001 per solve |
| CapSolver hCaptcha | ~$0.001 per solve |
| Total per submission | ~$0.001 (most forms have no CAPTCHA) |

## Gotchas

1. **Wix phone validation:** Rejects non-US phones. Use US number or leave blank
2. **mailto: links:** Some chambers use mailto: instead of forms — script detects and skips
3. **ASP.NET control IDs:** ChamberData uses nested IDs like `ctl00$ContentPlaceHolder$txtName` — split on `$` for field name matching
4. **Hidden honeypot fields:** Skipped automatically (offsetHeight/Width === 0)
5. **CapSolver timeout:** Runs in ThreadPoolExecutor to keep Playwright event loop alive
6. **Browser profile persistence:** Uses `.tmp/browser_profile/` so cookies survive between runs
