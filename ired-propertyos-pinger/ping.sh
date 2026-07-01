#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${1:-${TARGET_URL:-https://ired-propertyos-monorepo.onrender.com}}"
MAX_RETRIES="${MAX_RETRIES:-3}"
CONNECT_TIMEOUT_SECONDS="${CONNECT_TIMEOUT_SECONDS:-10}"
MAX_TIME_SECONDS="${MAX_TIME_SECONDS:-30}"
RETRY_DELAY_SECONDS="${RETRY_DELAY_SECONDS:-10}"

if [[ -z "$TARGET_URL" ]]; then
  echo "TARGET_URL is required."
  exit 1
fi

echo "Pinging: $TARGET_URL"
echo "Started at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"

last_http_code="000"
last_exit_code="0"
response_file="/tmp/ired-propertyos-ping-response.txt"

for attempt in $(seq 1 "$MAX_RETRIES"); do
  echo "Attempt $attempt of $MAX_RETRIES"

  set +e
  last_http_code=$(curl \
    --location \
    --silent \
    --show-error \
    --output "$response_file" \
    --write-out "%{http_code}" \
    --connect-timeout "$CONNECT_TIMEOUT_SECONDS" \
    --max-time "$MAX_TIME_SECONDS" \
    --user-agent "ired-propertyos-github-actions-pinger/1.0" \
    "$TARGET_URL")
  last_exit_code=$?
  set -e

  echo "HTTP status: $last_http_code"
  echo "curl exit code: $last_exit_code"

  if [[ "$last_exit_code" -eq 0 && "$last_http_code" =~ ^(2|3)[0-9][0-9]$ ]]; then
    echo "Ping successful."
    echo "Finished at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    exit 0
  fi

  if [[ "$attempt" -lt "$MAX_RETRIES" ]]; then
    echo "Ping failed. Retrying in ${RETRY_DELAY_SECONDS}s."
    sleep "$RETRY_DELAY_SECONDS"
  fi
done

echo "Ping failed after $MAX_RETRIES attempts."
echo "Last HTTP status: $last_http_code"
echo "Last curl exit code: $last_exit_code"

if [[ -s "$response_file" ]]; then
  echo "Response body preview:"
  head -c 1000 "$response_file"
  echo
fi

exit 1
