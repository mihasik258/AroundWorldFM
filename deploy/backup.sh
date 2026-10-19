#!/bin/sh
set -eu

while true; do
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  target="/backups/aroundfm-${stamp}.dump"
  if pg_dump --format=custom --no-owner --file="${target}.partial"; then
    mv "${target}.partial" "${target}"
    echo "backup ${target} done"
  else
    rm -f "${target}.partial"
    echo "backup failed" >&2
  fi
  find /backups -name 'aroundfm-*.dump' -mtime "+${BACKUP_KEEP_DAYS}" -delete
  sleep 86400
done
