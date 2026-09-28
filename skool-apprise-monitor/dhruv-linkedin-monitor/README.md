# LinkedIn Post Monitor — Dhruv

Monitors the `aiautomationsbyjack` Skool community for LinkedIn-related posts and sends desktop push notifications via ntfy.

## How It Works

1. Every 3 minutes, scrapes the community feed (2 pages)
2. Checks each new post for LinkedIn keywords (30+ terms)
3. If a match is found, sends a push notification to Dhruv's ntfy topic

## Subscribe to Notifications

**Browser (desktop):**
1. Open https://push.florianrolke.com/dhruv-linkedin-alerts
2. Click "Subscribe to topic"
3. Allow browser notifications

**Phone (ntfy app):**
1. Install [ntfy](https://ntfy.sh/) from App Store / Play Store
2. Add server: `push.florianrolke.com`
3. Subscribe to topic: `dhruv-linkedin-alerts`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SKOOL_AUTH_TOKEN` | Yes | Skool session cookie (shared with main monitor) |
| `DHRUV_NTFY_URL` | Yes | ntfy topic URL (default: `https://push.florianrolke.com/dhruv-linkedin-alerts`) |
| `DHRUV_COMMUNITY` | No | Community slug (default: `aiautomationsbyjack`) |
| `STATE_DIR` | No | State directory (default: `/app/state` in Docker) |

## Commands

```bash
# Test notification
python linkedin_post_monitor.py --test-notification

# Single run (dry)
python linkedin_post_monitor.py --dry-run

# Initialize state (seed seen posts, no alerts)
python linkedin_post_monitor.py --init

# Daemon mode (production)
python linkedin_post_monitor.py --daemon --interval 180
```

## Deployment

Runs inside the existing `skool-apprise-monitor` Docker container on Coolify. The `entrypoint.sh` starts both the main monitor and this LinkedIn monitor in parallel.
