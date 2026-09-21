#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "Usage: $0 backups/YYYYMMDD-HHMMSS"; exit 2; }
source_dir=$1
[ -f "$source_dir/database.sql" ] && [ -f "$source_dir/espocrm-data.tgz" ] && [ -f "$source_dir/SHA256SUMS" ] || { echo "Invalid backup directory or missing SHA256SUMS"; exit 2; }
# Verification is intentionally before any stop/import/overwrite operation.
(
  cd "$source_dir"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -c SHA256SUMS
  else
    shasum -a 256 -c SHA256SUMS
  fi
)
docker compose stop espocrm daemon websocket
docker compose exec -T db sh -lc 'mariadb -u root -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' < "$source_dir/database.sql"
docker run --rm -v fusanhe-crm_espocrm-data:/target -v "$PWD/$source_dir":/backup:ro alpine sh -c 'rm -rf /target/* && tar xzf /backup/espocrm-data.tgz -C /target'
docker compose up -d
