#!/bin/bash
# Transform Odoo 18 module to Odoo 17 compatibility
# Usage: ./scripts/transform_odoo17.sh [module_dir]
#
# Transformations applied:
# 1. Version string: 18.0.x.x -> 17.0.x.x
# 2. XML views: <list> -> <tree> (Odoo 17 syntax)
# 3. Test assertions: version checks updated

set -e

MODULE_DIR="${1:-karage_pos}"

if [[ ! -d "$MODULE_DIR" ]]; then
    echo "Error: Module directory '$MODULE_DIR' not found"
    exit 1
fi

echo "Applying Odoo 17 transformations to $MODULE_DIR..."

# Transform version in manifest (18.0.x.x -> 17.0.x.x)
MANIFEST_FILE="$MODULE_DIR/__manifest__.py"
if [[ -f "$MANIFEST_FILE" ]]; then
    sed -i 's/"version": "18\.0\./"version": "17.0./' "$MANIFEST_FILE"
    echo "  - Updated version to 17.0.x.x in $MANIFEST_FILE"
else
    echo "  - Warning: $MANIFEST_FILE not found"
fi

# Transform list -> tree in XML views (Odoo 17 syntax)
# Handles both <list ...> and <list> patterns
for XML_FILE in "$MODULE_DIR/views/webhook_log_views.xml" "$MODULE_DIR/views/karage_pos_payment_mapping_views.xml"; do
    if [[ -f "$XML_FILE" ]]; then
        sed -i -e 's/<list\([ >]\)/<tree\1/g' -e 's/<\/list>/<\/tree>/g' "$XML_FILE"
        echo "  - Converted <list> to <tree> in $XML_FILE"
    else
        echo "  - Warning: $XML_FILE not found"
    fi
done

# Transform test assertions for version checks
TEST_FILE="$MODULE_DIR/tests/test_models.py"
if [[ -f "$TEST_FILE" ]]; then
    sed -i 's/startswith("18\.0")/startswith("17.0")/g' "$TEST_FILE"
    sed -i 's/start with 18\.0/start with 17.0/g' "$TEST_FILE"
    echo "  - Updated version checks in $TEST_FILE"
else
    echo "  - Warning: $TEST_FILE not found"
fi

echo "Odoo 17 transformations complete."
