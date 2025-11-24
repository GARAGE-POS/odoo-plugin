[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=bugs)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=coverage)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=ncloc)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Technical Debt](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=sqale_index)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=GARAGE-POS_odoo-plugin&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=GARAGE-POS_odoo-plugin)
# Karage POS Odoo Integration

This project provides complete integration between Karage POS systems and Odoo 17 ERP through a custom addon module. The `karage-pos` module processes complete orders from external POS systems into Odoo's standard POS workflow, managing inventory, customers, products, and accounting automatically.

## Quick Start

### With DevContainer (Recommended)
```bash
# Open in VS Code and reopen in container, then:
odoo --init=karage-pos --addons-path=/mnt/extra-addons --stop-after-init
odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test
```

### Local Installation
```bash
# Install the module (first time only)
odoo --init=karage-pos --addons-path=/mnt/extra-addons --stop-after-init

# Run tests
odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test
```

## Architecture Overview

The module extends Odoo's built-in Point of Sale (POS) system to handle external POS integration:

- **API Endpoint**: `/api/karage/handleOrder` processes complete orders from Karage POS
- **Standard POS Extension**: Leverages `pos.order`, `pos.session`, and `pos.config` models
- **Automatic Processing**: Creates products, customers, and handles inventory through standard Odoo workflows
- **Audit Logging**: All API requests are logged for compliance and debugging

## Prerequisites

### Local Development
- Odoo 17 installed and configured
- System Python with Odoo dependencies
- Coverage module for testing (optional): `/usr/bin/python3 -m pip install coverage --break-system-packages`

### Development Container (Recommended)
- [Docker](https://www.docker.com/get-started) installed
- [VS Code](https://code.visualstudio.com/) with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

## Development Environment Setup

### Option 1: Using Development Containers (Recommended)

Development containers provide a consistent, isolated environment with all dependencies pre-configured.

#### Getting Started with DevContainers

1. **Open in VS Code**: Open the project folder in VS Code
2. **Reopen in Container**: When prompted, click "Reopen in Container" or use Command Palette (`Ctrl+Shift+P`) → "Dev Containers: Reopen in Container"
3. **Wait for Setup**: The container will build automatically with Odoo 17 and all dependencies

#### DevContainer Benefits

- ✅ **Pre-configured Environment**: Odoo 17, PostgreSQL, and Python dependencies included
- ✅ **Consistent Development**: Same environment across all developers
- ✅ **Isolated Dependencies**: No conflicts with local Python installations
- ✅ **VS Code Integration**: Debugging, extensions, and tools work seamlessly
- ✅ **Port Forwarding**: Odoo web interface automatically accessible

#### DevContainer Commands

Once inside the development container:

```bash
# Install the module (first time only)
odoo --init=karage-pos --addons-path=/workspace --stop-after-init

# Run tests
odoo --test-enable --update=karage-pos --addons-path=/workspace --stop-after-init --log-level=test

# Start Odoo in development mode
odoo --addons-path=/workspace --dev=reload,qweb,werkzeug,xml

# Run with coverage
python3 -m coverage run -m odoo --test-enable --update=karage-pos --addons-path=/workspace --stop-after-init --log-level=test
```

#### DevContainer Configuration

The development container includes:
- **Odoo 17**: Pre-installed and configured
- **PostgreSQL**: Database server ready for use
- **Python Dependencies**: All required packages installed
- **VS Code Extensions**: Python, Odoo development extensions
- **Port Forwarding**: Port 8069 for Odoo web interface

### Option 2: Local Installation

If you prefer local development without containers:

## Installation

### 1. Module Installation

For first-time installation:
```bash
odoo --init=karage-pos --addons-path=/mnt/extra-addons --stop-after-init
```

For updates during development:
```bash
odoo --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init
```

### 2. Module Structure

```
karage-pos/
├── __manifest__.py          # Module metadata and dependencies
├── controllers/             # API endpoints
│   └── order_controller.py  # Main /api/karage/handleOrder endpoint
├── models/                  # Business logic and data models
│   ├── pos_order.py        # POS order extensions with Karage integration
│   ├── pos_config.py       # POS configuration for Karage locations
│   ├── pos_session.py      # Session management
│   ├── product_sync.py     # Product synchronization service
│   └── logger.py           # Request audit logging
├── data/                   # Initial configuration data
├── security/               # Access rights and security rules
├── tests/                  # Comprehensive test suite
└── views/                  # User interface definitions
```

## Running the Application

### 1. Development Mode

#### With DevContainer
```bash
# Start Odoo in development mode (inside container)
odoo --addons-path=/workspace --dev=reload,qweb,werkzeug,xml
```
Access the Odoo web interface at [http://localhost:8069](http://localhost:8069)

#### Local Installation
```bash
# Start Odoo in development mode
odoo --addons-path=/mnt/extra-addons --dev=reload,qweb,werkzeug,xml
```

### 2. Production Mode

For production deployment:
```bash
odoo --addons-path=/mnt/extra-addons  # or /workspace in container
```

### 3. API Usage

The module provides a REST API endpoint for POS integration:

**Endpoint**: `POST /api/karage/handleOrder`
**Content-Type**: `application/json`

Sample request payload:
```json
{
  "CreditCustomerID": 0,
  "CustomerContact": "",
  "AmountTotal": 25,
  "LocationID": 404,
  "CheckoutDate": "10-08-2025 05:16:43 PM",
  "CustomerID": 0,
  "OrderDetails": [
    {
      "ItemID": 170388,
      "Name": "Fuchs Oil 5W30 Syn Sn",
      "Price": 25,
      "Quantity": 1,
      "Cost": 20
    }
  ],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 1,
      "AmountPaid": 18.75,
      "CardType": "Cash"
    }
  ],
  "OrderStatus": 103,
  "AmountPaid": 18.75,
  "GrandTotal": 18.75
}
```

## Testing

### 1. Basic Testing

#### With DevContainer
```bash
# Run all tests for the karage-pos module
odoo --test-enable --update=karage-pos --addons-path=/workspace --stop-after-init --log-level=test
```

#### Local Installation
```bash
# Run all tests for the karage-pos module
odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test
```

**Note**: Exit code 1 is normal when using `--stop-after-init` flag.

### 2. Test Coverage

#### With DevContainer
```bash
# Run tests with coverage (inside container)
python3 -m coverage run -m odoo --test-enable --update=karage-pos --addons-path=/workspace --stop-after-init --log-level=test

# Generate coverage report
python3 -m coverage report --include="karage-pos/*" --omit="*/tests/*"

# Generate HTML coverage report
python3 -m coverage html --include="karage-pos/*" --omit="*/tests/*"
```

#### Local Installation
```bash
# Run tests with coverage
/usr/bin/python3 -m coverage run -m odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test

# Generate coverage report
/usr/bin/python3 -m coverage report --include="karage-pos/*" --omit="*/tests/*"

# Generate HTML coverage report
/usr/bin/python3 -m coverage html --include="karage-pos/*" --omit="*/tests/*"
```

Coverage reports will be available in the `htmlcov/` directory.

### 3. Test Categories

The test suite includes:

- **API Endpoint Tests** (`test_controller.py`): HTTP request handling and response validation
- **Order Processing Tests** (`test_order_processing.py`): Complete order workflow testing
- **POS Migration Tests** (`test_pos_migration.py`): POS system integration testing

### 4. Sample Test Data

Real POS order data is available in `tests/sample_request.json` for realistic testing scenarios.

## Development Workflow

### 1. Making Changes

#### With DevContainer
1. Edit code in the appropriate module files
2. Update the module:
   ```bash
   odoo --update=karage-pos --addons-path=/workspace --stop-after-init
   ```
3. Run tests to verify changes:
   ```bash
   odoo --test-enable --update=karage-pos --addons-path=/workspace --stop-after-init --log-level=test
   ```

#### Local Installation
1. Edit code in the appropriate module files
2. Update the module:
   ```bash
   odoo --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init
   ```
3. Run tests to verify changes:
   ```bash
   odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test
   ```

### 2. Key Development Files

- **API Logic**: `karage-pos/controllers/order_controller.py:10-62`
- **Order Processing**: `karage-pos/models/pos_order.py:26` (process_karage_order method)
- **Product Management**: `karage-pos/models/product_sync.py:15-50`
- **Request Logging**: `karage-pos/models/logger.py:3-10`

### 3. Important Notes

#### For DevContainer Development
- **Python commands**: Use `python3` directly (Python is pre-configured in container)
- **Addons path**: Always use `/workspace` as the addons path
- **Port forwarding**: Odoo web interface accessible at `localhost:8069`
- **Database**: PostgreSQL is pre-configured and running in the container

#### For Local Development
- **Always use `/usr/bin/python3`** for coverage commands (system Python has Odoo installed)
- **Addons path**: Use `/mnt/extra-addons` or your local addons directory

#### General
- **Module dependencies**: base, sale, stock, product, account, stock_account, point_of_sale
- **Standard POS integration**: The module extends existing POS functionality rather than replacing it

## Key Features

### 1. Order Processing
- Processes complete external POS orders into standard Odoo POS workflow
- Automatic invoice generation through standard POS mechanisms
- Handles multiple payment methods and partial payments
- Creates confirmed sale orders for standard Odoo business flow

### 2. Product Management
- Auto-creates products from POS ItemID data if they don't exist
- Uses ItemID as product default_code for easy lookup
- Manages inventory synchronization between POS and Odoo

### 3. Customer Management
- Automatically creates customers from POS data when needed
- Links orders to existing customers when possible
- Handles both registered and anonymous customers

### 4. Inventory Management
- Each POS LocationID gets its own stock location in Odoo
- Standard stock movements through POS picking mechanisms
- Real-time inventory updates from POS transactions

### 5. Session Management
- Each LocationID has corresponding POS configuration and session tracking
- Automatic session management for different POS locations
- Configurable payment methods per location

### 6. Audit and Compliance
- All API requests logged with full details (URL, headers, body, timestamp)
- Complete audit trail for debugging and compliance purposes
- Should be cleaned up periodically via cron jobs

## Troubleshooting

### Common Issues

1. **Module not loading**: Ensure all dependencies are installed and addons-path is correct
2. **Test failures**: Check that test products and stock locations are properly configured
3. **API errors**: Review request logs in `karage.request.logger` model
4. **Coverage issues**: Use system Python (`/usr/bin/python3`) instead of virtual environment

### Logs and Debugging

- **Test logs**: Use `--log-level=test` flag for detailed test output
- **API request logs**: Check `karage.request.logger` records in Odoo backend
- **System logs**: Standard Odoo logging configuration applies

## Contributing

1. Follow the existing code structure and naming conventions
2. Add appropriate tests for new functionality
3. Ensure test coverage remains high
4. Update this README if adding new features or changing workflows

## License

This project follows Odoo's licensing terms. See Odoo documentation for details.
