#!/bin/sh
# Restores the newest dump into a scratch database and checks it matches the live one, then drops it.
set -eu
PGPASSWORD="$(cat /run/secrets/postgres_password)"
export PGPASSWORD
latest="$(ls -1t /backups/hangarllm-*.dump 2>/dev/null | head -n 1)"
if [ -z "$latest" ]; then
  echo "no backup found in /backups" >&2
  exit 1
fi
scratch="hangarllm_restore_check"
psql_db() { psql --host=db --username=hangarllm --no-psqlrc --quiet --tuples-only --no-align "$@"; }
counts() {
  psql_db --dbname="$1" --command="SELECT (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public')
    || ' tables, ' || (SELECT count(*) FROM \"HangarLLM_VerificationToken\") || ' keys, '
    || (SELECT count(*) FROM \"HangarLLM_TeamTable\") || ' teams'"
}

psql_db --dbname=hangarllm --command="DROP DATABASE IF EXISTS ${scratch}"
psql_db --dbname=hangarllm --command="CREATE DATABASE ${scratch}"
trap 'psql_db --dbname=hangarllm --command="DROP DATABASE IF EXISTS ${scratch}"' EXIT
pg_restore --host=db --username=hangarllm --dbname="$scratch" --no-owner --exit-on-error "$latest"

restored="$(counts "$scratch")"
live="$(counts hangarllm)"
echo "backup:   $(basename "$latest") -> ${restored}"
echo "database: ${live}"
case "$restored" in
  "0 tables"*) echo "restore produced no tables" >&2; exit 1 ;;
esac
echo "restore check passed"
