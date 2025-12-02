# Odoo Marketplace Deployment Guide

## Overview

This repository uses a **single-source, multi-target** deployment strategy:

- **Development** happens on `main` branch using Odoo 18 syntax
- **Deployment branches** (`18.0`, `17.0`) contain only the module folder
- **Automated transformations** convert Odoo 18 code to Odoo 17 compatibility

```
main (development)
  │
  ├──► 18.0 branch (direct copy)
  │
  └──► 17.0 branch (with transformations)
```

## Quick Start

### Deploy to Both Versions

```bash
# Make sure you're on main with latest changes
git checkout main
git pull origin main

# Deploy to Odoo 18 (direct copy)
PRE_COMMIT_ALLOW_NO_CONFIG=1 ./deploy.sh 18.0

# Deploy to Odoo 17 (with transformations)
PRE_COMMIT_ALLOW_NO_CONFIG=1 ./deploy.sh 17.0
```

### Preview Changes (Dry Run)

```bash
./deploy.sh 17.0 --dry-run
./deploy.sh 18.0 --dry-run
```

## Branch Structure

| Branch | Purpose | Odoo Version | Contains |
|--------|---------|--------------|----------|
| `main` | Development | 18.0 syntax | Full repo (CI, tests, scripts, module) |
| `18.0` | Deployment | 18.0 | Only `karage_pos/` folder |
| `17.0` | Deployment | 17.0 | Only `karage_pos/` folder (transformed) |

## Multi-Version Support

### Supported Versions

| Odoo Version | Branch | Manifest Version | Python | Status |
|--------------|--------|------------------|--------|--------|
| 18.0 | `18.0` | `18.0.0.1` | 3.11+ | ✅ Primary |
| 17.0 | `17.0` | `17.0.0.1` | 3.10+ | ✅ Supported |

### Odoo 17 Transformations

The `scripts/transform_odoo17.sh` script automatically applies these changes:

| File | Transformation | Reason |
|------|----------------|--------|
| `__manifest__.py` | `18.0.x.x` → `17.0.x.x` | Version must match Odoo series |
| `views/webhook_log_views.xml` | `<list>` → `<tree>` | Odoo 17 uses `tree`, Odoo 18 uses `list` |
| `tests/test_models.py` | Version assertions updated | Tests check correct version |

### Code Compatibility

The module code handles version differences at runtime:

```python
# Example: general_note field only exists in Odoo 18+
pos_order_model = request.env["pos.order"]
if "general_note" in pos_order_model._fields:
    order_vals["general_note"] = f'External Order ID: {order_id}'
```

## Deployment Script Reference

### Usage

```bash
./deploy.sh <version> [--dry-run]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `version` | Yes | Target Odoo version: `17.0` or `18.0` |
| `--dry-run` | No | Preview changes without deploying |

### What the Script Does

1. Creates an orphan branch (no git history)
2. Copies only `karage_pos/` from `main`
3. For Odoo 17: runs transformation script
4. Commits and force-pushes to target branch
5. Returns to original branch

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `PRE_COMMIT_ALLOW_NO_CONFIG=1` | Bypass pre-commit hooks (deployment branches have no config) |

## CI/CD Pipeline

### Automated Testing

The CI runs tests against both Odoo versions on every push to `main`:

```yaml
# .github/workflows/coverage.yml
strategy:
  matrix:
    odoo_version: ['18.0', '17.0']
```

For Odoo 17 tests, the CI automatically applies transformations before running tests.

### Test Results

Both versions must pass before merging to `main`.

## Odoo Apps Marketplace

### Repository URLs

When registering on [Odoo Apps](https://apps.odoo.com/):

**Odoo 18:**
```
ssh://git@github.com/GARAGE-POS/odoo-plugin.git#18.0
```

**Odoo 17:**
```
ssh://git@github.com/GARAGE-POS/odoo-plugin.git#17.0
```

### Submission Checklist

Before submitting to Odoo Apps:

- [ ] Branch name matches Odoo version (`18.0` or `17.0`)
- [ ] Module folder is `karage_pos/` at repository root
- [ ] `__manifest__.py` version starts with correct Odoo series
- [ ] `__manifest__.py` has valid license (`LGPL-3`)
- [ ] `static/description/index.html` exists
- [ ] `static/description/icon.png` exists (module icon)
- [ ] `static/description/banner.png` exists (1024x500px recommended)
- [ ] No `__pycache__` directories
- [ ] All `depends` are valid Odoo modules

## Manual Deployment (Alternative)

If you prefer not to use the deployment script:

### Deploy Odoo 18

```bash
git checkout --orphan 18.0-temp
git rm -rf .
git checkout main -- karage_pos/
git add karage_pos/
git commit -m "Karage POS Integration module for Odoo 18.0"
git branch -D 18.0 2>/dev/null || true
git branch -m 18.0-temp 18.0
git push origin 18.0 --force
git checkout main
```

### Deploy Odoo 17

```bash
git checkout --orphan 17.0-temp
git rm -rf .
git checkout main -- karage_pos/
git checkout main -- scripts/transform_odoo17.sh
./scripts/transform_odoo17.sh karage_pos
rm -rf scripts/
git add karage_pos/
git commit -m "Karage POS Integration module for Odoo 17.0"
git branch -D 17.0 2>/dev/null || true
git branch -m 17.0-temp 17.0
git push origin 17.0 --force
git checkout main
```

## Troubleshooting

### Pre-commit Hook Errors

If you see pre-commit errors during deployment:

```bash
PRE_COMMIT_ALLOW_NO_CONFIG=1 ./deploy.sh <version>
```

### Uncommitted Changes Warning

The script warns if you have uncommitted changes. Either:
- Commit or stash your changes first
- Type `y` to continue anyway (changes won't affect deployment)

### Force Push Blocked

If force-push is blocked by branch protection:
- Temporarily disable branch protection for deployment branches
- Or use a deploy token with bypass permissions

## Adding Support for New Odoo Versions

To add support for a new version (e.g., Odoo 19):

1. **Update CI matrix** in `.github/workflows/coverage.yml`
2. **Create transformation script** if needed (e.g., `scripts/transform_odoo19.sh`)
3. **Update `deploy.sh`** to handle the new version
4. **Test thoroughly** before deploying
5. **Update this documentation**

## Prerequisites

- Git installed and configured
- Push access to the repository
- Read the [Odoo Vendor Guidelines](https://apps.odoo.com/apps/vendor-guidelines)
