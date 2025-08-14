# Testing Guide for Karage POS Module

This guide covers how to run tests and generate test coverage reports for the karage-pos Odoo module.

## Prerequisites

Before running tests, ensure that:
1. Your development environment is set up and running
2. PostgreSQL database is accessible
3. Coverage is installed in the system Python environment

### Installing Coverage

If coverage is not installed, run:
```bash
/usr/bin/python3 -m pip install coverage --break-system-packages
```

## Running Tests

### Method 1: Using VS Code Tasks

The workspace includes predefined tasks for easy testing:

1. **Update Karage Module**
   - Use VS Code Command Palette (`Ctrl+Shift+P`)
   - Search for "Tasks: Run Task"
   - Select "Update Karage Module"

2. **Install Karage Module** (first time setup)
   - Use VS Code Command Palette (`Ctrl+Shift+P`)
   - Search for "Tasks: Run Task"
   - Select "Install Karage Module"

### Method 2: Command Line

#### Basic Test Run
```bash
# Update and run tests for the karage-pos module
odoo --addons-path=/mnt/extra-addons --update=karage-pos --stop-after-init --test-enable --log-level=test
```

#### Install Module with Tests (first time)
```bash
# Install and run tests for the karage-pos module
odoo --addons-path=/mnt/extra-addons --init=karage-pos --stop-after-init --test-enable --log-level=test
```

## Test Coverage

### Running Tests with Coverage

To run tests and collect coverage data:

```bash
# Run tests with coverage collection
/usr/bin/python3 -m coverage run -m odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test
```

**Important Notes:**
- Use `/usr/bin/python3` (system Python) instead of just `python3`
- The exit code 1 is normal when using `--stop-after-init`
- Odoo stops after running tests, which is expected behavior

### Generating Coverage Reports

#### Text Report
```bash
# Generate a text-based coverage report
/usr/bin/python3 -m coverage report
```

#### HTML Report
```bash
# Generate an HTML coverage report
/usr/bin/python3 -m coverage html

# View the HTML report (opens in browser)
"$BROWSER" htmlcov/index.html
```

#### Coverage Report with Specific Modules
```bash
# Generate report focusing on your module only (excluding tests)
/usr/bin/python3 -m coverage report --include="karage-pos/*" --omit="*/tests/*"

# Generate HTML report for your module only (excluding tests)
/usr/bin/python3 -m coverage html --include="karage-pos/*" --omit="*/tests/*"
```

### Coverage Configuration

You can create a `.coveragerc` file to configure coverage settings to focus only on your module:

```ini
[run]
source = karage-pos
omit = 
    */tests/*
    */migrations/*
    */__pycache__/*
    */static/*
    */description/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError

[html]
directory = htmlcov
title = Karage POS Module Coverage Report
```

**Create the configuration file:**
```bash
# Create .coveragerc in your workspace root
cat > .coveragerc << 'EOF'
[run]
source = karage-pos

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError

[html]
directory = htmlcov
title = Karage POS Module Coverage Report
EOF
```

## Test Structure

The module follows Odoo's testing conventions:

```
karage-pos/
├── tests/
│   ├── __init__.py
│   └── test_controller.py     # Controller tests
├── controllers/
│   └── order_controller.py    # Code being tested
└── models/
    └── request_log.py         # Models being tested
```

## Common Test Commands Summary

| Purpose | Command |
|---------|---------|
| Run tests only | `odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test` |
| Run with coverage | `/usr/bin/python3 -m coverage run -m odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test` |
| Coverage report (code only) | `/usr/bin/python3 -m coverage report --include="karage-pos/*" --omit="*/tests/*"` |
| HTML coverage (code only) | `/usr/bin/python3 -m coverage html --include="karage-pos/*" --omit="*/tests/*"` |
| Install module | `odoo --init=karage-pos --addons-path=/mnt/extra-addons --stop-after-init` |

## Troubleshooting

### Common Issues

1. **ModuleNotFoundError: No module named 'odoo'**
   - Solution: Use `/usr/bin/python3` instead of `python3`
   - The system Python has Odoo installed, not the pyenv Python

2. **Coverage not found**
   - Solution: Install coverage in system Python:
   ```bash
   /usr/bin/python3 -m pip install coverage --break-system-packages
   ```

3. **Database connection errors**
   - Ensure PostgreSQL is running
   - Check database credentials in your Odoo configuration

4. **Tests not found**
   - Verify test files are in the `tests/` directory
   - Ensure test files start with `test_`
   - Check that `__init__.py` imports test modules

### Debugging Tests

To run tests with more verbose output:
```bash
odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=debug
```

To run specific test classes:
```bash
odoo --test-enable --test-tags=+karage-pos --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init
```

## Continuous Integration

For CI/CD pipelines, use this command sequence:
```bash
# Install coverage
/usr/bin/python3 -m pip install coverage --break-system-packages

# Run tests with coverage
/usr/bin/python3 -m coverage run -m odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test

# Generate reports
/usr/bin/python3 -m coverage report
/usr/bin/python3 -m coverage xml  # For CI tools that parse XML
```

## Best Practices

1. **Write comprehensive tests** for all controllers, models, and business logic
2. **Aim for high coverage** (80%+ is recommended)
3. **Test edge cases** and error conditions
4. **Use meaningful test names** that describe what is being tested
5. **Keep tests isolated** - each test should be independent
6. **Mock external dependencies** to ensure tests are reliable
7. **Regular testing** - run tests after every significant change

## Additional Resources

- [Odoo Testing Documentation](https://www.odoo.com/documentation/17.0/developer/reference/backend/testing.html)
- [Python Coverage Documentation](https://coverage.readthedocs.io/)
- [Odoo Development Best Practices](https://www.odoo.com/documentation/17.0/developer/misc/other/guidelines.html)
