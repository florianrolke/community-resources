# Fathom Setup

## Webhook Path

1. Start the API.
2. Expose it publicly with your domain, Cloudflare Tunnel, Coolify, or Modal.
3. In Fathom, add a webhook:
   - URL: `https://your-domain.com/webhook/fathom`
   - Event: transcript/recording completed event that includes transcript data
   - Scope: your recordings
   - Secret: optional but recommended

Set the secret in `.env`:

```env
FATHOM_WEBHOOK_SECRET=your-secret
```

The API returns `202` immediately and writes a job file to `data/jobs`.

## Poller Path

The scheduler polls Fathom every 15 minutes as a backup.

```env
FATHOM_API_KEY=your-api-key
FATHOM_POLL_MINUTES=15
```

The poller skips meetings that have no transcript and meetings already listed in `data/state/processed_meetings.json`.
