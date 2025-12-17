#!/bin/bash
# Build release zip files for different Odoo versions
# Usage: ./scripts/build_releases.sh [version|all]
#
# Examples:
#   ./scripts/build_releases.sh          # Build all versions
#   ./scripts/build_releases.sh all      # Build all versions
#   ./scripts/build_releases.sh 17.0     # Build only 17.0
#   ./scripts/build_releases.sh 18.0     # Build only 18.0
#   ./scripts/build_releases.sh 19.0     # Build only 19.0
#
# Output: dist/karage_pos-{version}.zip

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
MODULE_DIR="karage_pos"
BUILD_DIR="$ROOT_DIR/dist"
TEMP_DIR="$ROOT_DIR/.build_temp"

# Versions to build
REQUESTED_VERSION="${1:-all}"
ALL_VERSIONS=("17.0" "18.0" "19.0")

# Determine which versions to build
if [[ "$REQUESTED_VERSION" == "all" ]]; then
    VERSIONS=("${ALL_VERSIONS[@]}")
else
    if [[ ! " ${ALL_VERSIONS[*]} " =~ " ${REQUESTED_VERSION} " ]]; then
        echo "Error: Invalid version '$REQUESTED_VERSION'"
        echo "Valid versions: ${ALL_VERSIONS[*]}"
        exit 1
    fi
    VERSIONS=("$REQUESTED_VERSION")
fi

# Clean up function
cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

# Create build directory
mkdir -p "$BUILD_DIR"

echo "=== Building Karage POS releases ==="
echo "Versions: ${VERSIONS[*]}"
echo "Output directory: $BUILD_DIR"
echo ""

for VERSION in "${VERSIONS[@]}"; do
    echo "--- Building $VERSION ---"

    # Clean temp directory
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"

    # Copy module to temp directory
    cp -r "$ROOT_DIR/$MODULE_DIR" "$TEMP_DIR/"

    # Apply version-specific transformations
    if [[ "$VERSION" == "17.0" ]]; then
        echo "  Applying Odoo 17 transformations..."

        # Transform version in manifest (18.0.x.x -> 17.0.x.x)
        MANIFEST_FILE="$TEMP_DIR/$MODULE_DIR/__manifest__.py"
        if [[ -f "$MANIFEST_FILE" ]]; then
            sed -i 's/"version": "18\.0\./"version": "17.0./' "$MANIFEST_FILE"
            echo "    - Updated version to 17.0.x.x"
        fi

        # Transform list -> tree in XML views (Odoo 17 syntax)
        for XML_FILE in "$TEMP_DIR/$MODULE_DIR/views/webhook_log_views.xml" "$TEMP_DIR/$MODULE_DIR/views/karage_pos_payment_mapping_views.xml"; do
            if [[ -f "$XML_FILE" ]]; then
                sed -i -e 's/<list\([ >]\)/<tree\1/g' -e 's/<\/list>/<\/tree>/g' "$XML_FILE"
                echo "    - Converted <list> to <tree> in $(basename "$XML_FILE")"
            fi
        done

        # Transform test assertions for version checks
        TEST_FILE="$TEMP_DIR/$MODULE_DIR/tests/test_models.py"
        if [[ -f "$TEST_FILE" ]]; then
            sed -i 's/startswith("18\.0")/startswith("17.0")/g' "$TEST_FILE"
            sed -i 's/start with 18\.0/start with 17.0/g' "$TEST_FILE"
            echo "    - Updated version checks in tests"
        fi

    elif [[ "$VERSION" == "19.0" ]]; then
        echo "  Applying Odoo 19 transformations..."

        # Transform version in manifest (18.0.x.x -> 19.0.x.x)
        MANIFEST_FILE="$TEMP_DIR/$MODULE_DIR/__manifest__.py"
        if [[ -f "$MANIFEST_FILE" ]]; then
            sed -i 's/"version": "18\.0\./"version": "19.0./' "$MANIFEST_FILE"
            echo "    - Updated version to 19.0.x.x"
        fi

        # Transform test assertions for version checks
        TEST_FILE="$TEMP_DIR/$MODULE_DIR/tests/test_models.py"
        if [[ -f "$TEST_FILE" ]]; then
            sed -i 's/startswith("18\.0")/startswith("19.0")/g' "$TEST_FILE"
            sed -i 's/start with 18\.0/start with 19.0/g' "$TEST_FILE"
            echo "    - Updated version checks in tests"
        fi

        # Transform search view group elements (remove expand and string attributes)
        for XML_FILE in "$TEMP_DIR/$MODULE_DIR/views/webhook_log_views.xml" "$TEMP_DIR/$MODULE_DIR/views/karage_pos_payment_mapping_views.xml"; do
            if [[ -f "$XML_FILE" ]]; then
                sed -i 's/<group expand="[^"]*"/<group/g' "$XML_FILE"
                sed -i 's/<group string="Group By">/<group>/g' "$XML_FILE"
                echo "    - Removed deprecated group attributes in $(basename "$XML_FILE")"
            fi
        done

        # Transform _sql_constraints to models.Constraint (Odoo 19 new API)
        python3 - "$TEMP_DIR/$MODULE_DIR" << 'PYTHON_SCRIPT'
import re
import sys
import os

module_dir = sys.argv[1] if len(sys.argv) > 1 else 'karage_pos'

model_files = [
    f"{module_dir}/models/webhook_log.py",
    f"{module_dir}/models/karage_pos_payment_mapping.py",
]

for model_file in model_files:
    if not os.path.exists(model_file):
        continue

    with open(model_file, 'r') as f:
        content = f.read()

    if '_sql_constraints' not in content:
        continue

    pattern = r'_sql_constraints\s*=\s*\[(.*?)\]'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        continue

    constraints_block = match.group(1)
    constraint_pattern = r'\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']'
    constraints = re.findall(constraint_pattern, constraints_block)

    if not constraints:
        continue

    new_constraints = []
    for name, constraint_expr, message in constraints:
        attr_name = f"_{name}"
        new_constraints.append(f'    {attr_name} = models.Constraint("{constraint_expr}", "{message}")')

    new_constraints_str = '\n'.join(new_constraints)

    full_pattern = r'\n\s*_sql_constraints\s*=\s*\[.*?\]'
    replacement = f'\n{new_constraints_str}'

    new_content = re.sub(full_pattern, replacement, content, flags=re.DOTALL)

    with open(model_file, 'w') as f:
        f.write(new_content)

    print(f"    - Converted _sql_constraints in {os.path.basename(model_file)}")
PYTHON_SCRIPT

    else
        echo "  Using base version (18.0) - no transformations needed"
    fi

    # Remove __pycache__ and .pyc files
    find "$TEMP_DIR/$MODULE_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$TEMP_DIR/$MODULE_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

    # Create zip file using Python (zip command may not be available)
    ZIP_FILE="$BUILD_DIR/karage_pos-$VERSION.zip"
    rm -f "$ZIP_FILE"
    python3 - "$TEMP_DIR" "$MODULE_DIR" "$ZIP_FILE" << 'PYTHON_ZIP'
import zipfile
import os
import sys

temp_dir = sys.argv[1]
module_dir = sys.argv[2]
zip_file = sys.argv[3]

with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
    module_path = os.path.join(temp_dir, module_dir)
    for root, dirs, files in os.walk(module_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            if file.endswith('.pyc'):
                continue
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, temp_dir)
            zf.write(file_path, arcname)
PYTHON_ZIP

    echo "  Created: $ZIP_FILE"
    echo ""
done

echo "=== Build complete ==="
echo ""
echo "Generated files:"
for VERSION in "${VERSIONS[@]}"; do
    ZIP_FILE="$BUILD_DIR/karage_pos-$VERSION.zip"
    if [[ -f "$ZIP_FILE" ]]; then
        SIZE=$(du -h "$ZIP_FILE" | cut -f1)
        echo "  - karage_pos-$VERSION.zip ($SIZE)"
    fi
done
