#!/bin/bash
# Entrypoint: run main monitor + Dhruv's LinkedIn monitor in parallel

echo "Starting Skool monitors..."
echo "  1. Main monitor (ICP + wins + mentions)"
echo "  2. Dhruv LinkedIn post monitor"

MONITOR_INTERVAL="${MONITOR_INTERVAL_SECONDS:-180}"

# Start main monitor in background
python skool_apprise_monitor.py --daemon --interval "$MONITOR_INTERVAL" &
MAIN_PID=$!

# Start LinkedIn monitor in background
python dhruv-linkedin-monitor/linkedin_post_monitor.py --daemon --interval "$MONITOR_INTERVAL" &
DHRUV_PID=$!

echo "  Main monitor PID: $MAIN_PID"
echo "  LinkedIn monitor PID: $DHRUV_PID"

# Wait for either to exit (if one crashes, container restarts both)
wait -n $MAIN_PID $DHRUV_PID
EXIT_CODE=$?

echo "A monitor exited with code $EXIT_CODE — stopping container"
kill $MAIN_PID $DHRUV_PID 2>/dev/null
exit $EXIT_CODE
