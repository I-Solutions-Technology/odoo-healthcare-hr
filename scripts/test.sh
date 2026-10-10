#!/bin/bash
# Run module tests on a throw-away database (healthcare_hr_test).
#   scripts/test.sh healthcare_hr_core,healthcare_hr_shift
set -euo pipefail
BASE="/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
ODOO="/Users/jamalswilam/Desktop/odoo19"
MODULES="${1:-healthcare_hr_core}"
DB="${2:-healthcare_hr_test}"
TAGS=""
IFS=',' read -ra PARTS <<< "$MODULES"
for module in "${PARTS[@]}"; do TAGS="${TAGS:+$TAGS,}/${module}"; done
PORT=$((18000 + RANDOM % 900))
psql -h localhost -U odoo19_user -d postgres -qAtc "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$DB' and pid <> pg_backend_pid()" >/dev/null || true
dropdb -h localhost -U odoo19_user --if-exists "$DB"
: > "$BASE/logs/test.log"
createdb -h localhost -U odoo19_user "$DB"
"$ODOO/.venv/bin/python" "$ODOO/odoo-bin" -c "$BASE/odoo.conf" \
    -d "$DB" --db-filter="^${DB}$" --http-port="$PORT" --gevent-port="$((PORT + 1))" \
    -i "$MODULES" --test-enable --test-tags "$TAGS" \
    --log-level=test --stop-after-init --logfile="$BASE/logs/test.log"
echo "--- results ---"
grep -E "tests? .*(failed|error)|FAIL:|ERROR:|Ran [0-9]+ test|0 failed" "$BASE/logs/test.log" | tail -30
