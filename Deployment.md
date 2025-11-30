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

## Repository URL Format

When registering your Git repository on Odoo Apps, use this format:

```
ssh://git@github.com/GARAGE-POS/odoo-plugin.git#18.0
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
