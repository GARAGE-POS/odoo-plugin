#!/bin/bash
# Transform Odoo 18 module to Odoo 19 compatibility
# Usage: ./scripts/transform_odoo19.sh [module_dir]
#
# Transformations applied:
# 1. Version string: 18.0.x.x -> 19.0.x.x
# 2. Test assertions: version checks updated
# 3. Search view group: remove 'expand' and 'string' attributes (deprecated in Odoo 19)
# 4. _sql_constraints: convert to models.Constraint (new in Odoo 19)

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

# Transform _sql_constraints to models.Constraint (Odoo 19 new API)
# In Odoo 19, _sql_constraints is deprecated and replaced by models.Constraint
#
# Old syntax:
#   _sql_constraints = [
#       ('name', 'constraint_expression', 'message'),
#   ]
#
# New syntax:
#   _name = models.Constraint('constraint_expression', 'message')
#
# This is done via Python script for more complex transformation

python3 - "$MODULE_DIR" << 'PYTHON_SCRIPT'
import re
import sys

module_dir = sys.argv[1] if len(sys.argv) > 1 else 'karage_pos'

model_files = [
    f"{module_dir}/models/webhook_log.py",
    f"{module_dir}/models/karage_pos_payment_mapping.py",
]

import os
for model_file in model_files:
    if not os.path.exists(model_file):
        print(f"  - Warning: {model_file} not found")
        continue

    with open(model_file, 'r') as f:
        content = f.read()

    # Check if file has _sql_constraints
    if '_sql_constraints' not in content:
        print(f"  - No _sql_constraints in {model_file}")
        continue

    # Parse and transform _sql_constraints
    # First, extract the _sql_constraints block
    pattern = r'_sql_constraints\s*=\s*\[(.*?)\]'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        print(f"  - Could not parse _sql_constraints in {model_file}")
        continue

    constraints_block = match.group(1)

    # Parse individual constraints - handle multi-line tuples
    # Looking for ('name', 'constraint', 'message') patterns
    constraint_pattern = r'\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']'
    constraints = re.findall(constraint_pattern, constraints_block)

    if not constraints:
        print(f"  - Could not find constraints in {model_file}")
        continue

    # Build replacement: models.Constraint declarations
    new_constraints = []
    for name, constraint_expr, message in constraints:
        # Convert constraint name to valid Python identifier with underscore prefix
        attr_name = f"_{name}"
        new_constraints.append(f'    {attr_name} = models.Constraint("{constraint_expr}", "{message}")')

    new_constraints_str = '\n'.join(new_constraints)

    # Replace the _sql_constraints block with new declarations
    full_pattern = r'\n\s*_sql_constraints\s*=\s*\[.*?\]'
    replacement = f'\n{new_constraints_str}'

    new_content = re.sub(full_pattern, replacement, content, flags=re.DOTALL)

    with open(model_file, 'w') as f:
        f.write(new_content)

    print(f"  - Converted _sql_constraints to models.Constraint in {model_file}")

PYTHON_SCRIPT

echo "Odoo 19 transformations complete."
