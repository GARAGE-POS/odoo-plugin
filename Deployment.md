# Odoo Marketplace Deployment Guide

## Prerequisites

- Ensure you have read the [Vendor Guidelines](https://apps.odoo.com/apps/vendor-guidelines)
- Module folder contents must be at the root of the repository (not inside a subfolder)
- Repository must be accessible (public or Odoo has deploy key access)

## Branch Naming Convention

The branch name must exactly match the Odoo series version. For Odoo 18.0, use branch `18.0`.

## Deployment Commands (Using Git Subtree Split)

Since `karage_pos` is a subfolder in a larger repository, we use `git subtree split` to extract only the module contents into a separate branch.

```bash
# 1. Make sure all changes are committed first
git add karage_pos/
git commit -m "Prepare Karage POS Integration for Odoo marketplace"

# 2. Split the karage_pos folder into a new branch called 18.0
#    This creates a branch with only the contents of karage_pos at the root
git subtree split --prefix=karage_pos -b 18.0

# 3. Push the 18.0 branch to a dedicated repository for Odoo marketplace
git push git@github.com:GARAGE-POS/odoo-plugin.git 18.0:18.0
```

### Updating the Module (Future Releases)

When you need to push updates:

```bash
# 1. Commit your changes to the main branch first
git add karage_pos/
git commit -m "Update Karage POS Integration"

# 2. Delete the old local 18.0 branch
git branch -D 18.0

# 3. Re-split with updated content
git subtree split --prefix=karage_pos -b 18.0

# 4. Force push to update the marketplace repo
git push git@github.com:GARAGE-POS/karage-pos-odoo.git 18.0:18.0 --force
```

## Repository URL Format

When registering your Git repository on Odoo Apps, use this format:

```
ssh://git@github.com/GARAGE-POS/karage-pos-odoo.git#18.0
```

## Checklist Before Submission

- [ ] Branch name matches Odoo version (`18.0`)
- [ ] Module folder is at repository root
- [ ] `__manifest__.py` has correct version format (`18.0.x.x.x`)
- [ ] `__manifest__.py` has valid license (`LGPL-3` or `OPL-1`)
- [ ] `static/description/index.html` exists with module description
- [ ] `static/description/icon.png` exists (module icon)
- [ ] `static/description/banner.png` exists (cover image, recommended 1024x500px)
- [ ] No `__pycache__` directories in repository
- [ ] All dependencies in `depends` list are valid Odoo modules
