#!/bin/bash
# Transform Odoo 18 module to Odoo 19 compatibility
# Usage: ./scripts/transform_odoo19.sh [module_dir]
#
# Transformations applied:
# 1. Version string: 18.0.x.x -> 19.0.x.x
# 2. Test assertions: version checks updated

set -e

MODULE_DIR="${1:-karage_pos}"

if [[ ! -d "$MODULE_DIR" ]]; then
    echo "Error: Module directory '$MODULE_DIR' not found"
    exit 1
fi

echo "Applying Odoo 19 transformations to $MODULE_DIR..."

# Transform version in manifest (18.0.x.x -> 19.0.x.x)
MANIFEST_FILE="$MODULE_DIR/__manifest__.py"
if [[ -f "$MANIFEST_FILE" ]]; then
    sed -i 's/"version": "18\.0\./"version": "19.0./' "$MANIFEST_FILE"
    echo "  - Updated version to 19.0.x.x in $MANIFEST_FILE"
else
    echo "  - Warning: $MANIFEST_FILE not found"
fi

# Transform test assertions for version checks
TEST_FILE="$MODULE_DIR/tests/test_models.py"
if [[ -f "$TEST_FILE" ]]; then
    sed -i 's/startswith("18\.0")/startswith("19.0")/g' "$TEST_FILE"
    sed -i 's/start with 18\.0/start with 19.0/g' "$TEST_FILE"
    echo "  - Updated version checks in $TEST_FILE"
else
    echo "  - Warning: $TEST_FILE not found"
fi

echo "Odoo 19 transformations complete."
