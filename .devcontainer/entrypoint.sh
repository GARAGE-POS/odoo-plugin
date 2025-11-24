#!/bin/bash

set -e

echo "[entrypoint] Fixing ownership of /mnt/extra-addons..."
sudo chown -R odoo:odoo /mnt/extra-addons 2>/dev/null || true

if [ -v PASSWORD_FILE ]; then
    echo "[entrypoint] Reading password from file..."
    PASSWORD="$(< $PASSWORD_FILE)"
fi

echo "[entrypoint] Setting database connection variables..."
: ${HOST:=${DB_PORT_5432_TCP_ADDR:='db'}}
: ${PORT:=${DB_PORT_5432_TCP_PORT:=5432}}
: ${USER:=${DB_ENV_POSTGRES_USER:=${POSTGRES_USER:='odoo'}}}
: ${PASSWORD:=${DB_ENV_POSTGRES_PASSWORD:=${POSTGRES_PASSWORD:='odoo'}}}

DB_ARGS=()
function check_config() {
    param="$1"
    value="$2"
    if grep -q -E "^\s*\b${param}\b\s*=" "$ODOO_RC" ; then
        value=$(grep -E "^\s*\b${param}\b\s*=" "$ODOO_RC" |cut -d " " -f3|sed 's/["\n\r]//g')
    fi;
    DB_ARGS+=("--${param}")
    DB_ARGS+=("${value}")
}
check_config "db_host" "$HOST"
check_config "db_port" "$PORT"
check_config "db_user" "$USER"
check_config "db_password" "$PASSWORD"

echo "[entrypoint] Entrypoint arguments: $@"
case "$1" in
    -- | odoo)
        shift
        if [[ "$1" == "scaffold" ]] ; then
            echo "[entrypoint] Running odoo scaffold..."
            exec odoo "$@"
        else
            echo "[entrypoint] Waiting for PostgreSQL..."
            wait-for-psql.py ${DB_ARGS[@]} --timeout=30
            echo "[entrypoint] Starting odoo..."
            exec odoo "$@" "${DB_ARGS[@]}"
        fi
        ;;
    -*)
        echo "[entrypoint] Waiting for PostgreSQL..."
        wait-for-psql.py ${DB_ARGS[@]} --timeout=30
        echo "[entrypoint] Starting odoo with arguments..."
        exec odoo "$@" "${DB_ARGS[@]}"
        ;;
    *)
        echo "[entrypoint] Executing custom command: $@"
        exec "$@"
esac
