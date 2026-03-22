#!/bin/bash
# CityMind Sync Cron Script
#
# Triggers a full sync of all enabled datasets.
# Designed to be run via cron or systemd timer.
#
# Usage:
#   ./sync-cron.sh              # Use default localhost:8000
#   ./sync-cron.sh http://prod  # Use custom base URL
#
# Crontab example (daily at 2 AM):
#   0 2 * * * /path/to/sync-cron.sh >> /var/log/citymind-sync.log 2>&1

set -e

BASE_URL="${1:-http://localhost:8000}"
ENDPOINT="${BASE_URL}/sync/trigger"

echo "$(date -Iseconds) Starting CityMind sync..."
echo "Endpoint: ${ENDPOINT}"

# Trigger sync with cron as the source
response=$(curl -s -X POST "${ENDPOINT}" \
    -H "Content-Type: application/json" \
    -d '{"triggered_by": "cron"}')

echo "Response: ${response}"

# Check status
status_response=$(curl -s "${BASE_URL}/sync/status")
echo "Status: ${status_response}"

echo "$(date -Iseconds) Sync triggered successfully"
