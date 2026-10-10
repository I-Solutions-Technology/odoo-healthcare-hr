#!/bin/bash
# Start the Healthcare HR instance on http://127.0.0.1:8095 (shared Odoo 19 core)
BASE="/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
exec /Users/jamalswilam/Desktop/odoo19/.venv/bin/python \
     /Users/jamalswilam/Desktop/odoo19/odoo-bin -c "$BASE/odoo.conf" "$@"
