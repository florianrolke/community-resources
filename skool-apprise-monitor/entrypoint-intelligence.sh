#!/bin/bash
# Dump current environment vars to /app/.env so cron jobs can load them via python-dotenv
# (cron doesn't inherit parent process env vars)

printenv | grep -v "^BASH\|^SHLVL\|^_=" | while IFS= read -r line; do
    key="${line%%=*}"
    val="${line#*=}"
    printf '%s=%s\n' "$key" "$val"
done > /app/.env

echo "[$(date -u '+%Y-%m-%d %H:%M UTC')] Intelligence container started. Env written to /app/.env."
echo "[$(date -u '+%Y-%m-%d %H:%M UTC')] Cron schedule:"
echo "  Intelligence: 8am, 2pm, 8pm EST (13/19/01 UTC)"
echo "  Daily digest: 11pm EST (04 UTC)"
echo "  Weekly report: Sunday 10pm EST (03 UTC Mon)"

# Start cron in foreground
exec cron -f
