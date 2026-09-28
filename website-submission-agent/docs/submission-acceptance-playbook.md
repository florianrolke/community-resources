# Website Submission Acceptance Playbook

This playbook captures the practical lessons from live form-submission runs
across plumbing, HVAC, and mobile-home buyer websites. The goal is not to
force submissions through every website. The goal is to maximize legitimate,
auditable submissions while clearly classifying cases that need retry or manual
follow-up.

## Baseline From Live Runs

On a recent home-services run, the agent processed 1,436 unique websites and
reached out through 443 forms or form-like submissions, for an overall reached
out rate of 30.8 percent.

The most useful improvement was not stricter prefiltering. It was better form
handling after the page had already loaded:

- dynamic field mapping from labels, placeholders, `name`, `id`, and nearby text
- validation repair after a failed submit
- duplicate and hidden field fallback filling for Gravity Forms and similar builders
- delayed CAPTCHA detection after the first submit
- avoiding accidental search forms
- preserving proof screenshots and tracking columns for every attempt

## Operating Principles

Use a legitimate sender and approved message. This project is for real B2B
contact where there is a reasonable business purpose.

Start with review mode or a small dry run. Verify screenshots before increasing
volume.

Never buy anything. If the page becomes a checkout, domain-purchase screen,
payment flow, credit-card form, cart, invoice, or subscription purchase, mark it
as `checkout_or_payment_page` and stop.

Do not treat every failure as a bad lead. Many failures are recoverable with a
second pass because forms reveal validation requirements only after submit.

Save proof. Before and after screenshots, contact URL, extracted contact
details, calendar links, and status are the audit trail.

## Lead Selection

Use a broad but relevant list. Over-filtering can skip real local operators,
especially small companies with messy websites.

Deduplicate by normalized domain before the run. The same company can appear in
multiple city or category rows.

Prefer:

- real company websites
- local service businesses
- contact, quote, estimate, schedule, or request-service pages
- rows with plumbing, HVAC, drain, sewer, water heater, mitigation-adjacent,
  mobile-home buyer, or similar service intent

Treat these as lower priority or manual review:

- supply stores, manufacturers, showrooms, directories, schools, associations
- social-only pages
- domains for sale
- pages with no website
- checkout-only experiences

## Contact Page Discovery

The agent should first open the homepage and extract visible emails, phones,
calendar links, and page text.

Then it should rank links by intent. High-value link text includes:

- contact
- quote
- estimate
- request service
- schedule
- book
- appointment
- consultation
- get started
- sell your home
- cash offer

Do not rely only on `/contact`. Many successful submissions were under
`/schedule-a-repair`, `/request-service`, `/free-estimate`, `/get-a-quote`, or
embedded quote widgets.

If the best page exposes only `mailto:` or phone information, mark it as
`mailto_only` and save those contact details in tracking output.

## Form Selection

Many sites contain multiple forms. Choose the form with the highest outreach
intent, not the first form in the DOM.

Positive signals:

- textareas
- email and phone fields
- submit buttons saying contact, send, request, schedule, quote, estimate
- labels like comments, message, service needed, questions, project details

Negative signals:

- search forms
- newsletter-only forms
- login forms
- password fields
- cart or checkout fields
- product search boxes

Search-form avoidance matters. A common false positive is a global website
search field that appears before the real contact form. Penalize forms with
`search`, `site-search`, `wp-block-search`, one text field, and a submit button
that says only search.

## Field Mapping

Map fields from several signals, not just labels:

- associated `label[for]`
- wrapping label text
- placeholder
- `aria-label`
- `name`
- `id`
- surrounding text
- section heading
- validation message after submit

Expected field types:

- first name
- last name
- full name
- email
- phone
- company
- subject
- message
- address
- city
- state
- ZIP/postal code
- service type
- dropdowns
- checkboxes
- radio buttons

For full name widgets, fill both split fields and any duplicate hidden fields
that the form builder may validate later.

For number inputs, strip non-digits before filling. Some HTML number fields
reject formatted phone values.

For message fields, preserve the approved message exactly unless the campaign
requires personalization. Do not let the agent improvise copy during a locked
production campaign.

## Address And Autocomplete

Address fields are often the hardest validation issue. Use a complete fallback
address when the campaign permits it.

For autocomplete fields:

1. fill the full address
2. wait briefly for suggestions
3. press ArrowDown
4. press Enter
5. press Tab
6. dispatch `input`, `change`, and `blur`

If city, state, and postal code fields appear separately, fill them too. Some
forms validate hidden address parts even when the visible field looks complete.

## Dropdowns, Radios, And Checkboxes

Choose safe, non-purchase options:

- inquiry type: General Inquiry, Contact, Other, Service Request
- "how did you hear about us": Google or Website
- property/location questions: pick a plausible neutral option only when needed
- newsletter boxes: leave unchecked unless required for submission
- SMS consent: only check when the form blocks submission and the campaign has
  permission to provide that phone number

Never check terms that imply buying, financing, subscribing, or authorizing
charges unless the user explicitly approved that exact action.

## Validation Repair

Do not stop immediately when browser validation appears.

After the first submit:

1. inspect invalid required fields
2. read the validation text and field context
3. fill missing required fields with conservative values
4. fill duplicate hidden or builder-specific fields
5. resubmit once
6. re-check for confirmation, URL change, visible success text, or persistent
   validation errors

Useful fallback values:

- subject: campaign subject
- service needed: "Business partnership inquiry"
- comments/message: approved message
- city/state/postal code: approved sender or fallback address values
- company: sender company or sender full name when no company is provided

Classify unrecovered cases as `failed_validation` with a clear reason so they
can be retried intelligently.

## CAPTCHA Handling

CAPTCHA is not one thing. Track the type:

- reCAPTCHA
- hCaptcha
- Turnstile
- custom image CAPTCHA
- post-submit CAPTCHA

Run CAPTCHA solving before submit when detected. Also check again after submit,
because some forms reveal CAPTCHA only after the first validation attempt.

If a CAPTCHA solver returns a token, inject it and trigger the appropriate
change callbacks before resubmitting.

If CAPTCHA remains unsolved after the configured attempts, mark
`captcha_failed`. Do not burn unlimited solver credits on the same site.

## Status Semantics

Use stable statuses so later automation can reason about the run.

Reached-out statuses:

- `confirmed`: visible success message, thank-you page, or clear confirmation
- `submitted_unconfirmed`: submit likely occurred, but no reliable confirmation
- `submitted`
- `submitted_enter`

Retryable statuses:

- `failed_validation`
- `missing_required`
- `no_fillable_fields`
- `captcha_failed`
- `load_error`
- `submit_error`
- `no_submit_button`
- `detection_error`

Manual review statuses:

- `mailto_only`
- `no_contact_page`
- `no_form`
- `checkout_or_payment_page`
- `page_prefilter_rejected`
- `lead_prefilter_rejected`

## Retry Strategy

After the first pass, do not retry randomly. Sort retries by likely recovery:

1. `missing_required`
2. `no_fillable_fields`
3. `failed_validation`
4. `load_error`
5. `captcha_failed`

This prioritizes problems the agent can learn from and fix. CAPTCHA-heavy rows
are often more expensive and less predictable, so process them after easier
recoveries.

The first retry pass should use the same approved sender and message. Do not
change copy just to force a form through. The improvement should come from
better field mapping, not from message drift.

## Evidence And Tracking

Every production run should produce:

- result CSV
- tracking CSV merged back to the source rows
- before screenshot
- after screenshot
- separate confirmed-success screenshot folder
- extracted emails
- extracted phones
- extracted notes
- calendar links
- retry reason
- timestamp
- final contact URL

Calendar links matter. If a site exposes a booking link, save it even when the
form cannot be submitted.

## Cloud Running

The agent can run from a VPS or container as long as it has:

- Python dependencies installed
- Playwright browser installed
- Chrome or Chromium available
- persistent volume for `.tmp`, screenshots, and CSV outputs
- environment variables for sender defaults and CAPTCHA solver keys
- process supervisor, cron, or queue worker

Use the deterministic Python agent as the executor. General-purpose agents can
help analyze failures, but the repeatable production work should remain in
scripts with logs and checkpoints.

## What Increased Acceptance Most

The highest-impact changes were:

- submit-time validation repair
- filling hidden and duplicate form-builder fields
- better address autocomplete handling
- avoiding search forms
- delayed CAPTCHA detection after first submit
- keeping submitted-unconfirmed as reached-out but auditable
- retrying by failure type instead of rerunning the whole list

The main lesson: the agent needs to behave like a careful browser user after
validation appears, not like a static scraper that gives up after one submit.

## Retry Learning: June 17, 2026

A focused retry pass on 100 previously difficult plumbing/HVAC rows improved
reached-out count from 11 to 26. The extra 15 came from retrying only
validation/no-field failures after improving form behavior.

Add these behaviors before running retry backlogs:

- Use a broad visible-control prefill when a form is detected but no outreach
  fields are mapped. This recovered pages whose fields were inside custom
  wrappers or had weak labels.
- Skip dropdown placeholders beyond the obvious `Select...` values. Treat
  labels like `Interested In`, `Service Category`, `Service Category Needed`,
  `Pick one`, and `How can we help` as placeholders, not valid choices.
- Prefer real generic choices such as `Other`, `General`, `Inquiry`,
  `Business`, `Consultation`, `Referral`, or `Contact`.
- For state dropdowns, prefer `TX` or `Texas`.
- If direct JavaScript value setting fails on masked email/phone fields, fall
  back to typing into the field like a user.
- Re-run validation repair up to three times because some form builders reveal
  one missing field at a time.

Stop retrying automatically when a v4-style targeted retry produces no new
submissions. The remaining failures are usually deeper issues: CAPTCHA token
injection not attaching, iframe/vendor forms, hidden location/date widgets,
or custom validation that requires a manual interaction path.
