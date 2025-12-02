# Odoo Marketplace Deployment Guide

## Prerequisites

- Ensure you have read the [Vendor Guidelines](https://apps.odoo.com/apps/vendor-guidelines)
- Module must be inside a folder named after the module (e.g., `karage_pos/`) at the repository root
- Repository must be accessible (public or Odoo has deploy key access)

## Branch Naming Convention

The branch name must exactly match the Odoo series version. For Odoo 18.0, use branch `18.0`.

## Deployment Commands

The `18.0` branch contains only the `karage_pos` module folder (not the development files like tests configs, CI/CD, etc.).

### Initial Deployment

```bash
# 1. Create an orphan branch (no history from main)
git checkout --orphan 18.0-temp

# 2. Remove all files from staging
git rm -rf .

# 3. Restore only the karage_pos folder from main
git checkout main -- karage_pos/

# 4. Stage and commit
git add karage_pos/
git commit -m "Karage POS Integration module for Odoo 18.0"

# 5. Delete old 18.0 branch if it exists and rename
git branch -D 18.0 2>/dev/null
git branch -m 18.0-temp 18.0

# 6. Push to remote (force to overwrite)
git push origin 18.0 --force

# 7. Switch back to main
git checkout main
```

### Updating the Module (Future Releases)

When you need to push updates after making changes on `main`:

```bash
# 1. Commit your changes to the main branch first
git add karage_pos/
git commit -m "Update Karage POS Integration"

# 2. Switch to 18.0 branch
git checkout 18.0

# 3. Update karage_pos folder from main
git checkout main -- karage_pos/

# 4. Commit and push
git add karage_pos/
git commit -m "Update Karage POS Integration"
git push origin 18.0

# 5. Switch back to main
git checkout main
```

## Multi-Version Deployment

This module supports both Odoo 17 and Odoo 18. Each version requires its own deployment branch.

| Odoo Version | Branch | Version in manifest |
|--------------|--------|---------------------|
| 18.0 | `18.0` | `18.0.0.1` |
| 17.0 | `17.0` | `17.0.0.1` |

### Version Differences

The following files need modification for Odoo 17 compatibility:

1. **`__manifest__.py`**: Version string must start with `17.0.`
2. **`views/webhook_log_views.xml`**: Replace `<list>` with `<tree>` (Odoo 17 syntax)

### Deploying to Odoo 17

Use the deployment script to automatically transform and deploy:

```bash
./deploy.sh 17.0
```

Or manually:

```bash
# 1. Create/switch to 17.0 branch
git checkout --orphan 17.0-temp || git checkout 17.0-temp
git rm -rf .

# 2. Restore karage_pos from main
git checkout main -- karage_pos/

# 3. Transform for Odoo 17
sed -i 's/"version": "18.0/"version": "17.0/' karage_pos/__manifest__.py
sed -i 's/<list /<tree /g; s/<\/list>/<\/tree>/g' karage_pos/views/webhook_log_views.xml

# 4. Commit and deploy
git add karage_pos/
git commit -m "Karage POS Integration module for Odoo 17.0"
git branch -D 17.0 2>/dev/null
git branch -m 17.0-temp 17.0
git push origin 17.0 --force
git checkout main
```

## Repository URL Format

When registering your Git repository on Odoo Apps, use this format:

**Odoo 18:**
```
ssh://git@github.com/GARAGE-POS/odoo-plugin.git#18.0
```

**Odoo 17:**
```
ssh://git@github.com/GARAGE-POS/odoo-plugin.git#17.0
```

## Checklist Before Submission

- [ ] Branch name matches Odoo version (`18.0`)
- [ ] Module is inside a folder named `karage_pos/` at repository root
- [ ] `__manifest__.py` has correct version format (`18.0.x.x.x`)
- [ ] `__manifest__.py` has valid license (`LGPL-3` or `OPL-1`)
- [ ] `static/description/index.html` exists with module description
- [ ] `static/description/icon.png` exists (module icon)
- [ ] `static/description/banner.png` exists (cover image, recommended 1024x500px)
- [ ] No `__pycache__` directories in repository
- [ ] All dependencies in `depends` list are valid Odoo modules
