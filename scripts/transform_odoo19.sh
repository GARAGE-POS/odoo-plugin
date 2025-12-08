#!/bin/bash
# Transform Odoo 18 module to Odoo 19 compatibility
# Usage: ./scripts/transform_odoo19.sh [module_dir]
#
# Transformations applied:
# 1. Version string: 18.0.x.x -> 19.0.x.x
# 2. Test assertions: version checks updated
# 3. Search view group: remove 'expand' and 'string' attributes (deprecated in Odoo 19)

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

# Transform search view group elements (remove expand and string attributes - deprecated in Odoo 19)
# In Odoo 19, <group expand="0" string="Group By"> becomes just <group>
for XML_FILE in "$MODULE_DIR/views/webhook_log_views.xml" "$MODULE_DIR/views/karage_pos_payment_mapping_views.xml"; do
    if [[ -f "$XML_FILE" ]]; then
        # Remove expand="..." attribute from <group> elements
        sed -i 's/<group expand="[^"]*"/<group/g' "$XML_FILE"
        # Remove string="..." attribute from <group> elements in search views
        # We need to be careful to only remove string from group elements that had expand
        # or are in a search context - for now, just fix the common pattern
        sed -i 's/<group string="Group By">/<group>/g' "$XML_FILE"
        echo "  - Removed deprecated group attributes in $XML_FILE"
    else
        echo "  - Warning: $XML_FILE not found"
    fi
done

echo "Odoo 19 transformations complete."
