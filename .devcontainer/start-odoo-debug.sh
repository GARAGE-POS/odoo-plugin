#!/bin/bash
echo "Starting Odoo with debugpy on port 5678..."
echo "You can attach your debugger to localhost:5678 after Odoo starts"
/usr/bin/python3 /mnt/extra-addons/.devcontainer/wait-for-psql.py --db_host db --db_port 5432 --db_user odoo --db_password odoo --timeout=30

# Kill any process listening on port 5678 to avoid orphaned debugpy processes
fuser -k 5678/tcp || true

# Start Odoo with debugpy for remote debugging (without waiting for client)
exec /usr/bin/python3 -m debugpy --listen 0.0.0.0:5678 -m odoo --addons-path=/mnt/extra-addons
