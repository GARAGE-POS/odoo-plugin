# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Odoo 17 addon development repository containing the `karage-pos` module. The module provides complete custom POS-to-ERP integration by:

- **Processing complete orders** from Karage POS into custom order records
- **Managing inventory** automatically through standard Odoo stock pickings
- **Creating products** and customers automatically from POS data
- **Handling payments** and order details with proper invoice generation
- **Audit logging** all API requests for compliance and debugging

Due to the nature of the project, we need to log all the incoming requests that we get on the endpoints that we provide.

The main logic of the project follows a custom POS workflow:
- When a new order is created on Karage POS, a webhook will be sent to Odoo containing the order details
- The order creates custom order records with payment tracking
- Invoices are automatically generated for accounting integration
- Inventory is updated through standard Odoo stock picking mechanisms

## POS SYSTEM ARCHITECTURE

✅ **CURRENT APPROACH**: The module extends Odoo's built-in POS system for Karage POS integration, leveraging standard POS functionality while adding Karage-specific customizations.

### Implementation Details:

**Standard POS Extension:**
- Extends `pos.order` model with Karage-specific fields and methods
- Uses standard POS session, payment, and order line models
- Integrates with standard POS configuration and payment methods
- Dependencies: base, sale, stock, product, account, stock_account, point_of_sale

**Note:** This module leverages Odoo's built-in Point of Sale (point_of_sale) module as a foundation and extends it with Karage-specific functionality for seamless integration.

### Architecture Benefits:

1. **Standard POS Integration**: Leverages proven POS module functionality and workflows
2. **Karage-Specific Extensions**: Tailored specifically for Karage POS integration needs
3. **Standard Payment Processing**: Uses established POS payment methods and processing
4. **Proven Architecture**: Built on stable, well-tested POS module foundation
```json
{"CreditCustomerID":0,"CustomerContact":"","DiscountCode":"","AmountTotal":25,"LocationID":404,"CheckoutDate":"10-08-2025 05:16:43 PM","CustomerID":0,"Remark":"","OrderDetails":[{"itemType":"oil","ItemID":170388,"checkQty":0,"AlternateName":"زيت فوكس 5W30 Syn Sn ","Name":"Fuchs Oil 5W30 Syn Sn ","localStock":-169,"PackageID":0,"IsInventoryItem":true,"UniqueID":1907401772308368892,"OrderDetailID":0,"DiscountAmount":0,"OldQuantity":0,"Cost":20,"CurrentStock":-168,"Mode":"Add","OrderDetailPackages":[],"ItemTypeValue":"10000","Price":25,"Status":201,"Quantity":1}],"OrderCheckoutDetails":[{"PaymentMode":1,"AmountDiscount":0,"CardNumber":"","AmountPaid":18.75,"CardType":"Cash","CardHolderName":""}],"OrderStatus":103,"AmountPaid":18.75,"DiscountPercent":0,"HolderName":"","PartialPayment":0,"CustomerName":"","GrandTotal":18.75,"AmountDiscount":6.25,"TaxPercent":0,"IsPartialPaid":false,"ServiceCharges":0,"Tax":0,"BalanceAmount":0,"PaymentMode":1,"OrderTakerID":"2487"}
```

## Core Commands

### Testing Commands
```bash
# Run tests for the karage-pos module (most common command)
odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test

# Install module for first time
odoo --init=karage-pos --addons-path=/mnt/extra-addons --stop-after-init

# Run tests with coverage
/usr/bin/python3 -m coverage run -m odoo --test-enable --update=karage-pos --addons-path=/mnt/extra-addons --stop-after-init --log-level=test

# Generate coverage reports
/usr/bin/python3 -m coverage report --include="karage-pos/*" --omit="*/tests/*"
/usr/bin/python3 -m coverage html --include="karage-pos/*" --omit="*/tests/*"
```

### Important Notes
- **Always use `/usr/bin/python3`** instead of `python3` when running coverage commands - system Python has Odoo installed
- Exit code 1 is normal when using `--stop-after-init` flag
- Coverage must be installed in system Python: `/usr/bin/python3 -m pip install coverage --break-system-packages`

## Architecture

### Current Module Structure
```
karage-pos/
├── __manifest__.py          # Module metadata and dependencies
├── __init__.py             # Module initialization
├── controllers/            # HTTP controllers for API endpoints
│   ├── __init__.py
│   └── order_controller.py # REST API for /api/karage/handleOrder
├── data/                   # Initial data and configuration
│   ├── payment_method_data.xml  # Payment methods setup
│   ├── pos_config_data.xml      # POS configuration data
│   └── sequence_data.xml        # Order numbering sequences
├── models/                 # Odoo data models and business logic
│   ├── __init__.py
│   ├── logger.py          # karage.request.logger model for audit logging
│   ├── order_service.py   # Order processing service (LEGACY)
│   ├── pos_config.py      # POS configuration extensions for Karage
│   ├── pos_order.py       # POS order extensions with Karage fields
│   ├── pos_payment.py     # POS payment extensions
│   ├── pos_session.py     # POS session extensions for Karage locations
│   └── product_sync.py    # Product synchronization service
├── security/               # Access rights and security rules
│   ├── ir.model.access.csv     # Model access permissions
│   └── security.xml            # Security groups and rules
├── tests/                  # Comprehensive test suite
│   ├── __init__.py
│   ├── sample_request.json      # Real POS order data for testing
│   ├── test_controller.py       # API endpoint tests
│   ├── test_order_processing.py # Order processing tests
│   └── test_pos_migration.py    # POS migration tests
├── views/                  # User interface definitions
│   ├── menu_views.xml           # Menu structure
│   ├── pos_config_views.xml     # POS configuration management
│   ├── pos_order_views.xml      # Order management interface
│   └── pos_session_views.xml    # Session management
├── hooks.py               # Module lifecycle hooks
└── static/description/    # Module assets
    └── icon.png
```

### Key Components

**API Endpoint**: `/api/karage/handleOrder` (POST, JSON)
- Processes complete orders from Karage POS systems
- Uses standard POS order creation and processing workflow
- Automatic invoice generation through standard POS mechanisms
- Logs all requests for audit purposes
- Returns processing results with POS order IDs

**Current Models:**

**POS Order Extension**: `pos.order` (extended)
- Adds Karage-specific fields (karage_order_id, karage_location_id, karage_order_data)
- Implements process_karage_order() method for external POS integration
- Uses standard POS workflow with Karage customizations

**POS Configuration Extension**: `pos.config` (extended)
- Adds Karage location mapping and configuration
- Manages sessions for different Karage locations
- Configures payment methods and invoice generation

**POS Session Extension**: `pos.session` (extended)
- Handles session management for Karage locations
- Integrates with standard POS session workflow

**Order Processing Service**: `karage.order.service` (LEGACY)
- Alternative processing service (being phased out)
- Used for custom order processing logic

**Product Synchronization**: `karage.product.sync`
- Creates products from POS ItemIDs if they don't exist
- Manages inventory synchronization
- Handles product creation and updates

**Audit Logging**: `karage.request.logger`
- Stores: URL, headers, body, timestamp
- Used for compliance and debugging
- Should be cleaned up periodically via cron jobs

**Dependencies**: base, sale, stock, product, account, stock_account, point_of_sale

## Development Workflow

1. **Module Updates**: Use `--update=karage-pos` flag (not `--init`) for development changes
2. **Testing**: Always run tests after changes using the test commands above
3. **Order Processing**: 
   - Creates sale.order records in 'sale' state (confirmed) for standard Odoo workflow
   - Custom order models track Karage-specific data and handle external POS integration
4. **Product Management**: Products are auto-created with ItemID as default_code for easy lookup
5. **Stock Locations**: Each POS LocationID gets its own stock location in Odoo
6. **Session Management**: Each LocationID has corresponding custom configuration and session tracking
7. **Coverage**: Aim for high test coverage, HTML reports are available in `htmlcov/` directory

## Test-Driven Development Approach

### Current Testing Strategy
1. **Inventory Setup**: Create test products with proper stock levels
2. **Order Processing Tests**: Verify complete order workflow from API to accounting
3. **Integration Tests**: Test POS order creation, payment processing, and invoice generation
4. **Monitoring Tests**: Verify request logging and system state tracking

## Testing Framework

- **TransactionCase**: For testing business logic (order processing, product sync)
- **HttpCase**: For testing API endpoints with real HTTP requests
- **Test Coverage**: Order validation, customer creation, product management, inventory sync
- **Sample Data**: Real POS order data in `sample_request.json` for realistic testing
- **Comprehensive Guide**: Detailed testing instructions in `TESTING_GUIDE.md`

## File References

**Core Business Logic:**
- Order processing service: `karage-pos/models/order_service.py:15-60`
- Product synchronization: `karage-pos/models/product_sync.py:15-50`
- Main API controller: `karage-pos/controllers/order_controller.py:10-62`

**Data Models:**
- Request logging: `karage-pos/models/logger.py:3-10`

**Testing:**
- Basic controller tests: `karage-pos/tests/test_controller.py:5-89`
- Full order processing tests: `karage-pos/tests/test_order_processing.py:10-200`
- Sample POS data: `karage-pos/tests/sample_request.json`

**Current Key Methods:**
- POS order processing: `pos.order.process_karage_order()` *(pos_order.py:26)*
- Order processing service: `karage.order.service.process_order()` *(order_service.py - LEGACY)*
- Product creation: `pos.order._get_or_create_product_karage()` *(pos_order.py:179)*
- Customer management: `pos.order._get_or_create_customer_karage()` *(pos_order.py:108)*
- Payment processing: `pos.order._process_karage_payments()` *(pos_order.py:242)*

## Key Implementation Benefits

### 1. **Standard POS Integration**
- ✅ Leverages proven Odoo POS module functionality and reliability
- ✅ Standard invoice generation and accounting integration
- ✅ Built on established POS session and payment processing

### 2. **Karage-Specific Extensions**
- ✅ Custom fields for Karage order tracking and audit trail
- ✅ External POS integration while maintaining standard workflows
- ✅ Flexible product and customer creation from POS data

### 3. **Proven Architecture**
- ✅ Based on stable, well-tested POS module foundation
- ✅ Standard inventory management through POS stock movements
- ✅ Established payment methods and session management