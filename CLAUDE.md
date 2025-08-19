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

## CUSTOM POS SYSTEM ARCHITECTURE

✅ **CURRENT APPROACH**: The module uses a custom POS architecture specifically designed for Karage POS integration, avoiding dependencies on Odoo's built-in POS module.

### Implementation Details:

**Custom POS Implementation:**
- Creates custom order models for Karage POS integration
- Uses custom payment tracking and processing
- Manual order and payment management suited for external POS systems
- Dependencies: base, sale, stock, product, account, stock_account

### Architecture Benefits:

1. **Independent Operation**: No dependency on Odoo's POS module
2. **Custom Integration**: Tailored specifically for Karage POS workflows
3. **Flexible Payment Processing**: Custom payment handling for external POS systems
4. **Simplified Dependencies**: Reduced module dependencies for better maintainability
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
├── models/                 # Odoo data models and business logic
│   ├── __init__.py
│   ├── logger.py          # karage.request.logger model for audit logging
│   ├── order_service.py   # Complete order processing service (LEGACY)
│   └── product_sync.py    # Product and inventory synchronization (LEGACY)
├── tests/                  # Comprehensive test suite
│   ├── __init__.py
│   ├── test_controller.py      # Basic controller tests
│   ├── test_order_processing.py # Full order processing tests
│   └── sample_request.json     # Real POS order data for testing
├── hooks.py               # Module lifecycle hooks (commented out)
└── static/description/    # Module assets
    └── icon.png
```

### Target Module Structure (Custom POS)
```
karage-pos/
├── __manifest__.py          # Dependencies: base, sale, stock, product, account, stock_account
├── __init__.py             # Module initialization
├── controllers/            # HTTP controllers for API endpoints
│   ├── __init__.py
│   └── order_controller.py # REST API for /api/karage/handleOrder
├── models/                 # Odoo data models and business logic
│   ├── __init__.py
│   ├── logger.py          # karage.request.logger model for audit logging
│   ├── karage_config.py   # Custom configuration for Karage locations
│   ├── karage_order.py    # Custom order model with Karage-specific fields
│   ├── karage_payment.py  # Custom payment model 
│   ├── karage_session.py  # Custom session model for location management
│   └── res_partner.py     # Customer extensions for integration
├── data/                   # Initial data and configuration
│   ├── karage_config_data.xml     # Default configurations for locations
│   ├── payment_method_data.xml    # Payment methods setup
│   └── sequence_data.xml          # Order numbering sequences
├── security/               # Access rights and security rules
│   ├── ir.model.access.csv     # Model access permissions
│   └── security.xml            # Security groups and rules
├── views/                  # User interface definitions
│   ├── karage_config_views.xml    # Configuration management
│   ├── karage_order_views.xml     # Order management interface
│   ├── karage_session_views.xml   # Session management
│   └── menu_views.xml             # Menu structure
├── tests/                  # Comprehensive test suite
│   ├── __init__.py
│   ├── test_controller.py         # API endpoint tests
│   ├── test_karage_orders.py      # Custom order processing tests
│   ├── test_karage_sessions.py    # Session management tests
│   └── sample_request.json        # Real POS order data for testing
├── hooks.py               # Module lifecycle hooks
└── static/description/    # Module assets
    └── icon.png
```

### Key Components

**API Endpoint**: `/api/karage/handleOrder` (POST, JSON)
- Processes complete orders from Karage POS systems
- Creates custom order records with session management
- Automatic invoice generation and inventory updates
- Logs all requests for audit purposes
- Returns detailed processing results with order IDs

**Core Components:**

**Order Processing Service**: `karage.order.service`
- Validates incoming order data
- Creates/updates customers from POS data  
- Processes order lines and creates products as needed
- Handles payment information and discounts
- Creates sale.order records for standard Odoo workflow

**Product Synchronization**: `karage.product.sync`
- Creates products from POS ItemIDs if they don't exist
- Manages stock locations for different POS locations
- Creates proper stock movements for inventory tracking
- Bulk synchronization for efficient processing

**Custom Order Management**: `karage.order` (custom model)
- Custom order workflow for external POS integration
- Automatic stock picking creation
- Proper invoice generation for accounting
- Location-based order tracking

**Custom Session Management**: `karage.session` (custom model)
- Manages multiple Karage location sessions
- Tracks order processing by location
- Handles session opening/closing workflows

**Custom Payment Processing**: `karage.payment` (custom model)
- Custom payment method integration
- Multi-payment support (cash, card, etc.)
- Manual accounting entries for external POS systems

**Audit Logging**: `karage.request.logger`
- Stores: URL, headers, body, timestamp
- Used for compliance and debugging  
- Should be cleaned up periodically via cron jobs

**Dependencies**: base, sale, stock, product, account, stock_account

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

## Custom POS Implementation Plan

### Phase 1: Infrastructure Setup
1. **Update Dependencies**: Ensure base, sale, stock, product, account, stock_account are included
2. **Create Directory Structure**: Add data/, security/, views/ folders
3. **Security Setup**: Create ir.model.access.csv and security.xml
4. **Data Setup**: Create initial custom configurations and payment methods

### Phase 2: Custom Model Development  
1. **Karage Config**: Create karage_config.py for location-specific configurations
2. **Karage Order**: Create karage_order.py with Karage-specific fields and methods
3. **Karage Payment**: Create karage_payment.py for custom payment processing
4. **Karage Session**: Create karage_session.py for location session management

### Phase 3: API Enhancement
1. **Update Controller**: Enhance order_controller.py for custom order processing
2. **Optimize Order Service**: Improve order processing for custom workflow
3. **Enhance Product Sync**: Optimize custom inventory sync with proper stock movements
4. **Invoice Integration**: Implement automatic invoice generation

### Phase 4: Interface & Testing
1. **Management Views**: Create views for custom configuration and order management
2. **Test Enhancement**: Update all tests to work with custom approach
3. **Performance Testing**: Ensure custom approach maintains good performance
4. **Documentation Update**: Update all documentation to reflect custom architecture

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

**Core Key Methods:**
- Complete order processing: `order_service.process_order()`
- Product creation: `order_service._get_or_create_product()`  
- Stock synchronization: `product_sync.sync_product_stock()`
- Customer management: `order_service._get_or_create_customer()`

**Custom Model Key Methods:**
- Karage order processing: `karage_order.process_karage_order()`
- Custom invoice generation: `karage_order.create_invoice()`
- Custom stock management: `karage_order.update_stock()`
- Session management: `karage_session.get_or_create_session_for_location()`
- Payment processing: `karage_payment.create_from_karage_data()`

## Key Custom Implementation Benefits

### 1. **Independence & Control**
- ✅ Complete control over POS workflow without external dependencies
- ✅ Custom integration tailored specifically for Karage POS systems
- ✅ No dependency on Odoo's POS module reduces complexity

### 2. **Flexible Integration**
- ✅ Custom payment processing suited for external POS systems
- ✅ Tailored order workflow for specific business requirements
- ✅ Custom field mapping and data transformation

### 3. **Simplified Architecture**
- ✅ Reduced dependencies make maintenance easier
- ✅ Custom models provide exactly the fields and methods needed
- ✅ Clear separation between POS data and ERP processing

### 4. **Enhanced Customization**
- ✅ Easy to modify and extend for specific requirements
- ✅ Custom reporting and analytics tailored to business needs
- ✅ Direct integration with Karage POS data structures

### 5. **Performance & Reliability**
- ✅ Optimized for external POS integration patterns
- ✅ Custom session management for high-volume scenarios
- ✅ Reduced overhead from unnecessary POS module features