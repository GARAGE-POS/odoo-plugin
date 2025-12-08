#!/bin/bash
# Deploy script for multi-version Odoo module deployment
# Usage: ./deploy.sh <version> [--dry-run]
# Examples:
#   ./deploy.sh 18.0        # Deploy to 18.0 branch
#   ./deploy.sh 17.0        # Deploy to 17.0 branch (with transformations)
#   ./deploy.sh 17.0 --dry-run  # Preview changes without deploying

set -e

VERSION="${1:-}"
DRY_RUN="${2:-}"
MODULE_DIR="karage_pos"
SOURCE_BRANCH="main"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version> [--dry-run]"
    echo "  version: 17.0 or 18.0"
    echo "  --dry-run: Preview changes without deploying"
    exit 1
fi

if [[ "$VERSION" != "17.0" && "$VERSION" != "18.0" && "$VERSION" != "19.0" ]]; then
    echo "Error: Version must be 17.0, 18.0, or 19.0"
    exit 1
fi

echo "=== Deploying $MODULE_DIR to branch $VERSION ==="

# Store current branch
CURRENT_BRANCH=$(git branch --show-current)

# Ensure we're on a clean working tree for deployment
if [[ -n $(git status --porcelain) ]]; then
    echo "Warning: Working tree has uncommitted changes"
    if [[ "$DRY_RUN" != "--dry-run" ]]; then
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo ""
    echo "=== DRY RUN MODE ==="
    echo "Would perform the following:"
    echo "1. Create orphan branch $VERSION-temp"
    echo "2. Copy $MODULE_DIR from $SOURCE_BRANCH"

    if [[ "$VERSION" == "17.0" ]]; then
        echo "3. Transform files for Odoo 17:"
        echo "   - __manifest__.py: version 18.0.x.x -> 17.0.x.x"
        echo "   - webhook_log_views.xml: <list> -> <tree>"
    elif [[ "$VERSION" == "19.0" ]]; then
        echo "3. Transform files for Odoo 19:"
        echo "   - __manifest__.py: version 18.0.x.x -> 19.0.x.x"
        echo "   - models: _sql_constraints -> models.Constraint"
        echo "   - views: remove deprecated group attributes"
    fi

    echo "4. Commit and force-push to $VERSION branch"
    echo ""
    echo "Preview of transformed __manifest__.py version line:"
    grep -n '"version"' "$MODULE_DIR/__manifest__.py" | sed "s/18.0/${VERSION}/"

    if [[ "$VERSION" == "17.0" ]]; then
        echo ""
        echo "Preview of transformed XML (list -> tree):"
        grep -n '<list\|</list>' "$MODULE_DIR/views/webhook_log_views.xml" | sed 's/<list/<tree/g; s/<\/list>/<\/tree>/g'
    fi
    exit 0
fi

# Create temporary orphan branch
echo "Creating orphan branch $VERSION-temp..."
git checkout --orphan "$VERSION-temp"
git rm -rf . > /dev/null 2>&1 || true

# Restore module from source branch
echo "Restoring $MODULE_DIR from $SOURCE_BRANCH..."
git checkout "$SOURCE_BRANCH" -- "$MODULE_DIR/"

# Apply version-specific transformations
if [[ "$VERSION" == "17.0" ]]; then
    # Use centralized transform script (restore it first since orphan branch is empty)
    git checkout "$SOURCE_BRANCH" -- scripts/transform_odoo17.sh
    ./scripts/transform_odoo17.sh "$MODULE_DIR"
    # Remove scripts dir - not needed for deployment
    rm -rf scripts/
elif [[ "$VERSION" == "19.0" ]]; then
    # Use centralized transform script (restore it first since orphan branch is empty)
    git checkout "$SOURCE_BRANCH" -- scripts/transform_odoo19.sh
    ./scripts/transform_odoo19.sh "$MODULE_DIR"
    # Remove scripts dir - not needed for deployment
    rm -rf scripts/
fi

# Stage and commit - only the module folder (bypass pre-commit since orphan branch has no config)
echo "Committing changes..."
git reset HEAD -- scripts/ 2>/dev/null || true
git add "$MODULE_DIR/"
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "Karage POS Integration module for Odoo $VERSION"

# Replace existing branch
echo "Updating $VERSION branch..."
git branch -D "$VERSION" 2>/dev/null || true
git branch -m "$VERSION-temp" "$VERSION"

# Push to remote
echo "Pushing to origin/$VERSION..."
git push origin "$VERSION" --force

# Return to original branch
echo "Returning to $CURRENT_BRANCH..."
git checkout "$CURRENT_BRANCH"

echo ""
echo "=== Deployment complete ==="
echo "Branch $VERSION has been updated and pushed to origin"
echo "Repository URL: ssh://git@github.com/GARAGE-POS/odoo-plugin.git#$VERSION"
