#!/bin/bash
# Start Odoo normally for development

echo "Starting Odoo normally..."
/usr/bin/python3 /mnt/extra-addons/.devcontainer/wait-for-psql.py --db_host db --db_port 5432 --db_user odoo --db_password odoo --timeout=30
exec /usr/bin/python3 -m odoo --addons-path=/mnt/extra-addons
