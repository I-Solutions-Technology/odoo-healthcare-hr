#!/bin/bash
# Install/upgrade suite modules, then stop (no HTTP).
#   scripts/upgrade.sh healthcare_hr_core            -> upgrade
#   scripts/upgrade.sh healthcare_hr_core -i         -> install
BASE="/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
MODULES="${1:-healthcare_hr_core}"
FLAG="${2:--u}"
exec /Users/jamalswilam/Desktop/odoo19/.venv/bin/python \
     /Users/jamalswilam/Desktop/odoo19/odoo-bin -c "$BASE/odoo.conf" -d healthcare_hr \
     "$FLAG" "$MODULES" --http-port=18595 --gevent-port=18596 --stop-after-init
