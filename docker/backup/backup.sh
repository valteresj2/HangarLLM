#!/bin/sh
# Dumps the gateway database every BACKUP_INTERVAL_SECONDS and keeps the newest BACKUP_KEEP dumps.
set -eu
PGPASSWORD="$(cat /run/secrets/postgres_password)"
export PGPASSWORD
interval="${BACKUP_INTERVAL_SECONDS:-86400}"
keep="${BACKUP_KEEP:-7}"

while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  partial="/backups/.hangarllm-${stamp}.dump.partial"
  if pg_dump --host=db --username=hangarllm --dbname=hangarllm --format=custom --file="$partial"; then
    mv "$partial" "/backups/hangarllm-${stamp}.dump"
    echo "backup written: hangarllm-${stamp}.dump"
  else
    rm -f "$partial"
    echo "backup failed at ${stamp}" >&2
  fi
  ls -1t /backups/hangarllm-*.dump 2>/dev/null | tail -n "+$((keep + 1))" | while read -r old; do rm -f "$old"; done
  sleep "$interval"
done
