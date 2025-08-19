# 🧪 **Karage POS - QA Testing Manual**

**Version**: 2.0 (Post-Migration)  
**Date**: January 2025  
**Target**: Odoo 17 with Standard POS Integration  
**Scope**: Complete functional testing of migrated Karage POS module

---

## 📋 **Table of Contents**

1. [Pre-Testing Setup](#pre-testing-setup)
2. [Test Environment Requirements](#test-environment-requirements)
3. [Demo Data Setup](#demo-data-setup)
4. [Test Scenarios Overview](#test-scenarios-overview)
5. [Detailed Test Cases](#detailed-test-cases)
6. [API Testing with Sample Requests](#api-testing-with-sample-requests)
7. [UI Testing Guide](#ui-testing-guide)
8. [Performance Testing](#performance-testing)
9. [Data Verification Procedures](#data-verification-procedures)
10. [Troubleshooting Guide](#troubleshooting-guide)

---

## 🔧 **Pre-Testing Setup**

### **System Requirements**
- Odoo 17 Enterprise or Community
- karage-pos module installed and updated
- Database with demo data (recommended)
- Administrative access to Odoo
- API testing tool (Postman, curl, or similar)

### **Module Installation Verification**
```bash
# 1. Update the module
odoo --update=karage-pos --addons-path=/path/to/addons --stop-after-init

# 2. Verify module is installed
# Check in Apps menu for "Karage POS" with status "Installed"

# 3. Run module tests
odoo --test-enable --update=karage-pos --addons-path=/path/to/addons --stop-after-init
```

### **Access Requirements**
- **System Administrator**: For configuration and troubleshooting
- **POS Manager**: For daily operations testing  
- **POS User**: For basic functionality testing
- **API User**: For webhook/API endpoint testing

---

## 🖥️ **Test Environment Requirements**

### **Hardware Requirements**
- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores
- **Storage**: 50GB available space
- **Network**: Stable internet connection for API calls

### **Software Dependencies**
```bash
# Verify required modules are installed
pip3 list | grep -E "(odoo|psycopg2|lxml|Pillow)"

# Check Odoo version
odoo --version
```

### **Database Setup**
```sql
-- Create test database (if needed)
CREATE DATABASE karage_pos_test;

-- Verify database connection
\l karage_pos_test
```

---

## 🎯 **Demo Data Setup**

### **1. Test Locations Setup**

**Location 1: Main Store (404)**
- High-volume location
- Multiple product categories
- Cash and card payments

**Location 2: Branch Store (405)**  
- Medium-volume location
- Limited product range
- Primarily cash payments

**Location 3: New Store (999)**
- New location (auto-created during testing)
- Testing auto-configuration features

### **2. Test Products**

```json
{
  "test_products": [
    {
      "ItemID": 170388,
      "Name": "Fuchs Oil 5W30 Syn",
      "itemType": "oil",
      "Price": 25.00,
      "Cost": 20.00,
      "Category": "Automotive"
    },
    {
      "ItemID": 170389,
      "Name": "Brake Pads Premium",
      "itemType": "parts", 
      "Price": 85.50,
      "Cost": 65.00,
      "Category": "Auto Parts"
    },
    {
      "ItemID": 170390,
      "Name": "Car Wash Shampoo",
      "itemType": "maintenance",
      "Price": 15.75,
      "Cost": 8.50,
      "Category": "Maintenance"
    }
  ]
}
```

### **3. Test Customers**

```json
{
  "test_customers": [
    {
      "CustomerID": 12345,
      "CustomerName": "Ahmed Al-Rashid",
      "CustomerContact": "+966501234567"
    },
    {
      "CustomerID": 12346,
      "CustomerName": "Sarah Mohammed",
      "CustomerContact": "+966507654321"
    },
    {
      "CustomerID": 0,
      "CustomerName": "",
      "CustomerContact": ""
    }
  ]
}
```

### **4. Payment Methods Test Data**

- **Cash (PaymentMode: 1)**: Most common payment
- **Card (PaymentMode: 2)**: Credit/Debit cards
- **Mixed Payments**: Multiple payment methods per order

---

## 📊 **Test Scenarios Overview**

| **Test ID** | **Scenario** | **Priority** | **Type** | **Duration** |
|-------------|--------------|--------------|----------|--------------|
| TC001 | Basic Order Processing | P1 | Functional | 15 min |
| TC002 | Customer Creation & Management | P1 | Functional | 10 min |
| TC003 | Product Auto-Creation | P1 | Functional | 10 min |
| TC004 | Payment Processing | P1 | Functional | 15 min |
| TC005 | Multi-Location Support | P1 | Functional | 20 min |
| TC006 | Session Management | P2 | Functional | 15 min |
| TC007 | Invoice Generation | P1 | Integration | 10 min |
| TC008 | Inventory Updates | P1 | Integration | 15 min |
| TC009 | Error Handling | P1 | Negative | 20 min |
| TC010 | High Volume Processing | P2 | Performance | 30 min |
| TC011 | UI Management Interface | P2 | UI | 25 min |
| TC012 | Security & Permissions | P2 | Security | 20 min |

**Total Estimated Time: 3.5 hours**

---

## 🔍 **Detailed Test Cases**

### **TC001: Basic Order Processing** ⭐ P1
**Objective**: Verify standard order processing workflow  
**Prerequisites**: Module installed, API endpoint accessible

**Test Steps**:
1. Send POST request to `/api/karage/handleOrder`
2. Use sample order data (see API section)
3. Verify response contains success=true
4. Check POS order creation in Odoo UI
5. Validate session auto-creation
6. Confirm inventory adjustment

**Expected Results**:
- ✅ HTTP 200 response
- ✅ `success: true` in JSON response
- ✅ `pos_order_id` returned
- ✅ POS order visible in Orders menu
- ✅ Session created/updated
- ✅ Stock picking generated

**Sample Request**: [See TC001 in API section](#tc001-basic-order-processing-api)

---

### **TC002: Customer Creation & Management** ⭐ P1
**Objective**: Test customer auto-creation and linking

**Test Scenarios**:
1. **New Customer with Details**
2. **Existing Customer by ID**
3. **Anonymous Customer (Walk-in)**

**Test Steps**:
1. Process order with new customer data
2. Verify customer record creation
3. Process order with existing CustomerID
4. Verify customer linking (no duplicates)
5. Process order without customer details
6. Verify default customer usage

**Expected Results**:
- ✅ New customers created in res.partner
- ✅ Existing customers linked correctly
- ✅ Default "Walk-in Customer" used when needed
- ✅ No duplicate customer records

**Sample Requests**: [See TC002 in API section](#tc002-customer-management-api)

---

### **TC003: Product Auto-Creation** ⭐ P1
**Objective**: Verify product creation and categorization

**Test Steps**:
1. Process order with new ItemID
2. Verify product creation with correct attributes
3. Check product availability in POS
4. Validate category assignment
5. Process order with existing ItemID
6. Verify no duplicate products created

**Expected Results**:
- ✅ Products created with ItemID as default_code
- ✅ Correct price and cost assignment
- ✅ `available_in_pos = True`
- ✅ Proper category assignment
- ✅ No duplicate products

**Validation Query**:
```sql
SELECT name, default_code, list_price, standard_price, available_in_pos 
FROM product_product pp
JOIN product_template pt ON pp.product_tmpl_id = pt.id
WHERE default_code = '170388';
```

---

### **TC004: Payment Processing** ⭐ P1
**Objective**: Test payment method handling and processing

**Test Scenarios**:
1. **Single Cash Payment**
2. **Single Card Payment**  
3. **Multiple Payment Methods**
4. **Partial Payments**

**Test Steps**:
1. Process orders with different payment types
2. Verify pos.payment records creation
3. Check payment method mapping
4. Validate amount accuracy
5. Confirm journal entries (if accounting enabled)

**Expected Results**:
- ✅ pos.payment records created
- ✅ Correct payment method assignment
- ✅ Accurate amount processing
- ✅ Proper journal entries

**Sample Requests**: [See TC004 in API section](#tc004-payment-processing-api)

---

### **TC005: Multi-Location Support** ⭐ P1
**Objective**: Test location-specific POS configurations

**Test Steps**:
1. Process orders for different LocationIDs
2. Verify auto-creation of POS configs
3. Check session segregation by location
4. Validate location-specific settings
5. Test concurrent processing

**Expected Results**:
- ✅ Separate pos.config per location
- ✅ Unique sessions per location
- ✅ No cross-location data mixing
- ✅ Proper location naming

**Validation**:
```python
# Check POS configs
configs = env['pos.config'].search([('karage_location_id', '!=', False)])
print([(c.name, c.karage_location_id) for c in configs])

# Check sessions
sessions = env['pos.session'].search([('karage_location_id', '!=', False)])
print([(s.name, s.karage_location_id, s.state) for s in sessions])
```

---

### **TC006: Session Management** P2
**Objective**: Verify POS session lifecycle management

**Test Steps**:
1. Process first order for new location
2. Verify session auto-creation and opening
3. Process multiple orders for same location
4. Verify session reuse
5. Test session state transitions

**Expected Results**:
- ✅ Sessions auto-created when needed
- ✅ Sessions reused for same location
- ✅ Proper state management (opened/closed)
- ✅ Order count tracking

---

### **TC007: Invoice Generation** ⭐ P1
**Objective**: Test automatic invoice creation

**Test Steps**:
1. Process order with auto-invoice enabled
2. Verify invoice creation
3. Check invoice details accuracy
4. Validate accounting entries
5. Test invoice numbering sequence

**Expected Results**:
- ✅ Invoices auto-generated
- ✅ Correct customer and amounts
- ✅ Proper tax calculations
- ✅ Sequential numbering

**Validation**:
```python
# Check invoices
pos_order = env['pos.order'].browse(order_id)
invoice = pos_order.account_move
print(f"Invoice: {invoice.name}, Amount: {invoice.amount_total}")
```

---

### **TC008: Inventory Updates** ⭐ P1
**Objective**: Verify stock picking and inventory integration

**Test Steps**:
1. Check initial product stock levels
2. Process sales order
3. Verify stock picking creation
4. Confirm inventory reduction
5. Check stock move records

**Expected Results**:
- ✅ Stock pickings auto-created
- ✅ Inventory levels updated
- ✅ Stock moves properly recorded
- ✅ Accurate quantity calculations

---

### **TC009: Error Handling** ⭐ P1
**Objective**: Test system behavior with invalid data

**Test Scenarios**:
1. **Missing Required Fields**
2. **Invalid Data Types**
3. **Empty Order Details**
4. **Network/System Errors**

**Test Steps**:
1. Send requests with various invalid data
2. Verify proper error responses
3. Check error logging
4. Ensure system stability

**Expected Results**:
- ✅ Graceful error handling
- ✅ Descriptive error messages
- ✅ Proper HTTP status codes
- ✅ Error logging for debugging

**Sample Requests**: [See TC009 in API section](#tc009-error-handling-api)

---

## 🌐 **API Testing with Sample Requests**

### **TC001: Basic Order Processing API**

**Endpoint**: `POST /api/karage/handleOrder`

**Sample Request**:
```json
{
  "CreditCustomerID": 0,
  "CustomerContact": "",
  "DiscountCode": "",
  "AmountTotal": 25,
  "LocationID": 404,
  "CheckoutDate": "19-08-2025 02:30:15 PM",
  "CustomerID": 0,
  "Remark": "QA Test Order - Basic Processing",
  "OrderDetails": [
    {
      "itemType": "oil",
      "ItemID": 170388,
      "checkQty": 0,
      "AlternateName": "زيت فوكس 5W30 Syn Sn",
      "Name": "Fuchs Oil 5W30 Syn",
      "localStock": -169,
      "PackageID": 0,
      "IsInventoryItem": true,
      "UniqueID": 1907401772308368892,
      "OrderDetailID": 0,
      "DiscountAmount": 0,
      "OldQuantity": 0,
      "Cost": 20,
      "CurrentStock": -168,
      "Mode": "Add",
      "OrderDetailPackages": [],
      "ItemTypeValue": "10000",
      "Price": 25,
      "Status": 201,
      "Quantity": 1
    }
  ],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 1,
      "AmountDiscount": 0,
      "CardNumber": "",
      "AmountPaid": 25.00,
      "CardType": "Cash",
      "CardHolderName": ""
    }
  ],
  "OrderStatus": 103,
  "AmountPaid": 25.00,
  "DiscountPercent": 0,
  "HolderName": "",
  "PartialPayment": 0,
  "CustomerName": "",
  "GrandTotal": 25.00,
  "AmountDiscount": 0,
  "TaxPercent": 0,
  "IsPartialPaid": false,
  "ServiceCharges": 0,
  "Tax": 0,
  "BalanceAmount": 0,
  "PaymentMode": 1,
  "OrderTakerID": "QA_TEST_001"
}
```

**Expected Response**:
```json
{
  "success": true,
  "pos_order_id": 123,
  "pos_order_name": "KPOS/2025/00001",
  "session_id": 456,
  "invoice_id": 789,
  "log_id": 101,
  "api_version": "2.0",
  "message": "Order processed successfully using standard POS workflow"
}
```

**cURL Command**:
```bash
curl -X POST http://localhost:8069/api/karage/handleOrder \
  -H "Content-Type: application/json" \
  -d @tc001_request.json
```

---

### **TC002: Customer Management API**

#### **TC002A: New Customer Creation**
```json
{
  "LocationID": 404,
  "CustomerID": 98765,
  "CustomerName": "Fatima Al-Zahra",
  "CustomerContact": "+966551234567",
  "OrderDetails": [
    {
      "ItemID": 170389,
      "Name": "Brake Pads Premium",
      "Quantity": 1,
      "Price": 85.50,
      "Cost": 65.00,
      "itemType": "parts"
    }
  ],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 2,
      "AmountPaid": 85.50,
      "CardType": "Credit Card",
      "CardHolderName": "Fatima Al-Zahra"
    }
  ],
  "AmountTotal": 85.50,
  "OrderTakerID": "QA_TEST_002A"
}
```

#### **TC002B: Existing Customer**
```json
{
  "LocationID": 404,
  "CustomerID": 98765,
  "CustomerName": "Fatima Al-Zahra",
  "OrderDetails": [
    {
      "ItemID": 170390,
      "Name": "Car Wash Shampoo",
      "Quantity": 2,
      "Price": 15.75,
      "Cost": 8.50,
      "itemType": "maintenance"
    }
  ],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 1,
      "AmountPaid": 31.50,
      "CardType": "Cash"
    }
  ],
  "AmountTotal": 31.50,
  "OrderTakerID": "QA_TEST_002B"
}
```

#### **TC002C: Anonymous Customer**
```json
{
  "LocationID": 404,
  "CustomerID": 0,
  "CustomerName": "",
  "CustomerContact": "",
  "OrderDetails": [
    {
      "ItemID": 170388,
      "Name": "Fuchs Oil 5W30 Syn",
      "Quantity": 1,
      "Price": 25.00,
      "Cost": 20.00,
      "itemType": "oil"
    }
  ],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 1,
      "AmountPaid": 25.00,
      "CardType": "Cash"
    }
  ],
  "AmountTotal": 25.00,
  "OrderTakerID": "QA_TEST_002C"
}
```

---

### **TC004: Payment Processing API**

#### **TC004A: Multiple Payment Methods**
```json
{
  "LocationID": 405,
  "CustomerID": 11111,
  "CustomerName": "Omar Hassan",
  "OrderDetails": [
    {
      "ItemID": 170391,
      "Name": "Premium Tire Set",
      "Quantity": 4,
      "Price": 150.00,
      "Cost": 120.00,
      "itemType": "tires"
    }
  ],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 1,
      "AmountPaid": 200.00,
      "CardType": "Cash"
    },
    {
      "PaymentMode": 2,
      "AmountPaid": 400.00,
      "CardType": "Credit Card",
      "CardHolderName": "Omar Hassan",
      "CardNumber": "****1234"
    }
  ],
  "AmountTotal": 600.00,
  "AmountPaid": 600.00,
  "OrderTakerID": "QA_TEST_004A"
}
```

#### **TC004B: Partial Payment**
```json
{
  "LocationID": 405,
  "CustomerID": 22222,
  "CustomerName": "Layla Ahmed",
  "OrderDetails": [
    {
      "ItemID": 170392,
      "Name": "Engine Service Package",
      "Quantity": 1,
      "Price": 500.00,
      "Cost": 350.00,
      "itemType": "service"
    }
  ],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 1,
      "AmountPaid": 300.00,
      "CardType": "Cash"
    }
  ],
  "AmountTotal": 500.00,
  "AmountPaid": 300.00,
  "PartialPayment": 1,
  "IsPartialPaid": true,
  "BalanceAmount": 200.00,
  "OrderTakerID": "QA_TEST_004B"
}
```

---

### **TC009: Error Handling API**

#### **TC009A: Missing Required Fields**
```json
{
  "CustomerID": 0,
  "OrderDetails": [
    {
      "ItemID": 170388,
      "Name": "Test Product"
    }
  ]
}
```

**Expected Response**:
```json
{
  "success": false,
  "error": "Missing required fields: LocationID",
  "log_id": 102,
  "api_version": "2.0"
}
```

#### **TC009B: Empty Order Details**
```json
{
  "LocationID": 404,
  "OrderDetails": [],
  "OrderCheckoutDetails": [
    {
      "PaymentMode": 1,
      "AmountPaid": 0,
      "CardType": "Cash"
    }
  ]
}
```

**Expected Response**:
```json
{
  "success": false,
  "error": "Order must contain at least one item",
  "log_id": 103,
  "api_version": "2.0"
}
```

#### **TC009C: Invalid Data Types**
```json
{
  "LocationID": "invalid",
  "CustomerID": "not_a_number",
  "OrderDetails": "not_an_array"
}
```

---

## 🖥️ **UI Testing Guide**

### **Navigation Testing**

1. **Access Karage POS Menu**
   - Go to Main Menu → Point of Sale → Karage POS
   - Verify all menu items are accessible

2. **POS Configuration Management**
   - Navigate to Configuration → POS Configurations
   - Verify list shows Karage locations
   - Test filtering and search functionality

3. **Order Management**
   - Navigate to Orders menu
   - Verify Karage orders are displayed
   - Test order detail views

### **Configuration Testing**

#### **POS Configuration Form**
```
Test Steps:
1. Create new POS configuration
2. Set Karage Location ID: 777
3. Enable Auto Generate Invoices
4. Set default customer
5. Save and verify
```

**Expected Results**:
- ✅ Configuration saves successfully
- ✅ Location ID validation works
- ✅ No duplicate location IDs allowed

#### **Session Management**
```
Test Steps:
1. View Sessions menu
2. Check session states
3. Verify location segregation
4. Test session opening/closing
```

### **Data Display Testing**

#### **Order List View**
- ✅ Karage Order ID column visible
- ✅ Location ID column visible  
- ✅ Proper sorting and filtering
- ✅ Correct data formatting

#### **Order Detail View**
- ✅ Karage-specific fields displayed
- ✅ Payment information accurate
- ✅ Product details correct
- ✅ Customer information linked

---

## ⚡ **Performance Testing**

### **Load Testing Scenarios**

#### **TC010A: High Volume Orders**
**Objective**: Test system performance under load

**Test Setup**:
- 100 concurrent API requests
- Different location IDs (404, 405, 406, 407)
- Varied order sizes (1-10 items per order)

**Test Script**:
```bash
#!/bin/bash
# high_volume_test.sh

for i in {1..100}; do
  curl -X POST http://localhost:8069/api/karage/handleOrder \
    -H "Content-Type: application/json" \
    -d "{
      \"LocationID\": $((404 + $i % 4)),
      \"OrderTakerID\": \"LOAD_TEST_$i\",
      \"OrderDetails\": [{
        \"ItemID\": $((170000 + $i)),
        \"Name\": \"Load Test Product $i\",
        \"Quantity\": $((1 + $i % 3)),
        \"Price\": $((10 + $i % 50)),
        \"Cost\": $((5 + $i % 25)),
        \"itemType\": \"test\"
      }],
      \"OrderCheckoutDetails\": [{
        \"PaymentMode\": 1,
        \"AmountPaid\": $((10 + $i % 50)),
        \"CardType\": \"Cash\"
      }],
      \"AmountTotal\": $((10 + $i % 50))
    }" &
done

wait
echo "Load test completed"
```

**Performance Metrics**:
- ✅ Response time < 2 seconds per request
- ✅ No memory leaks or crashes
- ✅ Database connection stability
- ✅ Session management efficiency

#### **TC010B: Concurrent Location Processing**
**Objective**: Test multi-location concurrent processing

**Test Steps**:
1. Send 50 orders to Location 404
2. Send 50 orders to Location 405  
3. Send 25 orders to Location 999 (new)
4. Monitor system resources

**Expected Results**:
- ✅ All orders processed successfully
- ✅ No cross-location data contamination
- ✅ Proper session segregation maintained
- ✅ Database performance stable

---

## ✅ **Data Verification Procedures**

### **Database Validation Queries**

#### **Order Processing Verification**
```sql
-- Verify POS orders created
SELECT 
    po.name as order_name,
    po.karage_order_id,
    po.karage_location_id,
    ps.name as session_name,
    pc.name as config_name
FROM pos_order po
JOIN pos_session ps ON po.session_id = ps.id
JOIN pos_config pc ON ps.config_id = pc.id
WHERE po.karage_order_id IS NOT NULL
ORDER BY po.create_date DESC
LIMIT 10;
```

#### **Customer Creation Verification**
```sql
-- Check customer records
SELECT 
    name,
    ref as customer_id,
    phone,
    customer_rank,
    create_date
FROM res_partner 
WHERE ref ~ '^[0-9]+$' 
ORDER BY create_date DESC
LIMIT 10;
```

#### **Product Creation Verification**  
```sql
-- Verify product creation
SELECT 
    pt.name,
    pp.default_code as item_id,
    pt.list_price,
    pt.standard_price,
    pt.available_in_pos,
    pc.name as category
FROM product_product pp
JOIN product_template pt ON pp.product_tmpl_id = pt.id
JOIN product_category pc ON pt.categ_id = pc.id
WHERE pp.default_code ~ '^[0-9]+$'
ORDER BY pt.create_date DESC
LIMIT 10;
```

#### **Payment Processing Verification**
```sql
-- Check payment records
SELECT 
    po.name as order_name,
    pp.amount,
    ppm.name as payment_method,
    pp.card_type,
    pp.karage_payment_mode
FROM pos_payment pp
JOIN pos_order po ON pp.pos_order_id = po.id
JOIN pos_payment_method ppm ON pp.payment_method_id = ppm.id
WHERE po.karage_order_id IS NOT NULL
ORDER BY pp.create_date DESC
LIMIT 10;
```

#### **Session Management Verification**
```sql
-- Check session status
SELECT 
    ps.name,
    ps.karage_location_id,
    ps.state,
    ps.karage_order_count,
    ps.start_at,
    ps.stop_at
FROM pos_session ps
WHERE ps.karage_location_id IS NOT NULL
ORDER BY ps.start_at DESC;
```

### **API Response Validation**

#### **Success Response Schema**
```json
{
  "type": "object",
  "required": ["success", "pos_order_id", "pos_order_name", "session_id", "log_id", "api_version", "message"],
  "properties": {
    "success": {"type": "boolean", "enum": [true]},
    "pos_order_id": {"type": "integer", "minimum": 1},
    "pos_order_name": {"type": "string", "pattern": "^KPOS/\\d{4}/\\d{5}$"},
    "session_id": {"type": "integer", "minimum": 1},
    "invoice_id": {"type": ["integer", "null"]},
    "log_id": {"type": "integer", "minimum": 1},
    "api_version": {"type": "string", "enum": ["2.0"]},
    "message": {"type": "string"}
  }
}
```

#### **Error Response Schema**
```json
{
  "type": "object", 
  "required": ["success", "error", "api_version"],
  "properties": {
    "success": {"type": "boolean", "enum": [false]},
    "error": {"type": "string", "minLength": 1},
    "log_id": {"type": ["integer", "null"]},
    "api_version": {"type": "string", "enum": ["2.0"]}
  }
}
```

---

## 🔧 **Troubleshooting Guide**

### **Common Issues and Solutions**

#### **Issue 1: Module Installation Fails**
**Symptoms**: Error during module update/installation

**Diagnosis**:
```bash
# Check module dependencies
grep -r "depends.*=" karage-pos/__manifest__.py

# Verify database connection
psql -d your_database -c "\dt" | grep -E "(pos_|account_|stock_)"
```

**Solutions**:
1. Ensure all dependencies are installed
2. Update base modules first
3. Check database permissions
4. Clear Odoo cache: `rm -rf ~/.odoo/`

#### **Issue 2: API Returns 500 Error**
**Symptoms**: Internal server error on API calls

**Diagnosis**:
```bash
# Check Odoo logs
tail -f /var/log/odoo/odoo.log | grep -i error

# Test with minimal request
curl -X POST http://localhost:8069/api/karage/handleOrder \
  -H "Content-Type: application/json" \
  -d '{"LocationID": 404, "OrderDetails": [{"ItemID": 1, "Name": "Test", "Quantity": 1, "Price": 1}]}'
```

**Solutions**:
1. Check data format and required fields
2. Verify content-type header
3. Review server logs for specific errors
4. Test with administrator privileges

#### **Issue 3: Orders Not Creating Invoices**
**Symptoms**: POS orders created but no invoices generated

**Diagnosis**:
```sql
-- Check POS config settings
SELECT name, karage_auto_invoice, invoice_journal_id 
FROM pos_config 
WHERE karage_location_id IS NOT NULL;

-- Check order states  
SELECT name, state, to_invoice, account_move
FROM pos_order 
WHERE karage_order_id IS NOT NULL
LIMIT 5;
```

**Solutions**:
1. Enable auto-invoice in POS configuration
2. Ensure proper invoice journal setup
3. Check order state (should be 'paid' for invoicing)
4. Verify accounting module permissions

#### **Issue 4: Inventory Not Updating**
**Symptoms**: Orders processed but stock levels unchanged

**Diagnosis**:
```sql
-- Check stock pickings
SELECT sp.name, sp.state, sp.pos_order_id
FROM stock_picking sp
JOIN pos_order po ON sp.pos_order_id = po.id
WHERE po.karage_order_id IS NOT NULL
ORDER BY sp.create_date DESC
LIMIT 5;

-- Check product types
SELECT pt.name, pt.type 
FROM product_template pt
JOIN product_product pp ON pt.id = pp.product_tmpl_id
WHERE pp.default_code ~ '^[0-9]+$'
LIMIT 5;
```

**Solutions**:
1. Ensure products are type 'product' (stockable)
2. Check stock picking creation and validation
3. Verify warehouse and location setup
4. Review stock move records

### **Performance Issues**

#### **Slow API Response Times**
**Diagnosis**:
- Monitor database query performance
- Check system resources (CPU, Memory)
- Review concurrent session handling

**Solutions**:
- Optimize database indexes
- Increase system resources
- Implement request queuing if needed

---

## 📋 **Test Execution Checklist**

### **Pre-Test Checklist**
- [ ] Test environment set up and accessible
- [ ] karage-pos module installed and updated
- [ ] Demo data configured
- [ ] API testing tools ready
- [ ] Test database backup created
- [ ] User accounts with proper permissions

### **Execution Checklist**

#### **Functional Tests**
- [ ] TC001: Basic Order Processing
- [ ] TC002: Customer Management (A, B, C)
- [ ] TC003: Product Auto-Creation
- [ ] TC004: Payment Processing (A, B)
- [ ] TC005: Multi-Location Support
- [ ] TC006: Session Management
- [ ] TC007: Invoice Generation
- [ ] TC008: Inventory Updates
- [ ] TC009: Error Handling (A, B, C)

#### **Integration Tests**
- [ ] POS-ERP data synchronization
- [ ] Accounting module integration
- [ ] Inventory module integration
- [ ] Customer portal access (if applicable)

#### **UI Tests**
- [ ] Menu navigation
- [ ] Configuration forms
- [ ] Order management interface
- [ ] Reporting and analytics

#### **Performance Tests**  
- [ ] TC010A: High Volume Orders
- [ ] TC010B: Concurrent Location Processing
- [ ] Memory leak testing
- [ ] Database performance monitoring

#### **Security Tests**
- [ ] API authentication
- [ ] User permission validation
- [ ] Data access controls
- [ ] Audit trail verification

### **Post-Test Checklist**
- [ ] All test results documented
- [ ] Issues logged and prioritized
- [ ] Performance metrics recorded
- [ ] Database consistency verified
- [ ] Test environment cleaned up
- [ ] Final test report generated

---

## 📊 **Test Reporting Template**

### **Test Execution Summary**

| **Metric** | **Target** | **Actual** | **Status** |
|------------|------------|------------|------------|
| **Test Cases Executed** | 15 | ___ | ___ |
| **Pass Rate** | 100% | ___% | ___ |
| **API Response Time** | < 2s | ___s | ___ |
| **Order Processing Success** | 100% | ___% | ___ |
| **Data Consistency** | 100% | ___% | ___ |

### **Issue Summary**

| **Severity** | **Count** | **Examples** |
|--------------|-----------|--------------|
| **Critical** | ___ | ___ |
| **High** | ___ | ___ |
| **Medium** | ___ | ___ |
| **Low** | ___ | ___ |

### **Recommendations**

1. **Priority 1 Issues**: ___
2. **Performance Improvements**: ___
3. **Additional Testing Needed**: ___
4. **Production Readiness**: ___

---

**End of QA Testing Manual**

---

> 📝 **Note**: This manual should be updated with each module version change and maintained as a living document throughout the development lifecycle.

> 🔄 **Version Control**: Track changes to this manual alongside code changes to ensure testing procedures remain current and accurate.

> 👥 **Team Collaboration**: Share this manual with development, QA, and operations teams to ensure consistent testing approaches across environments.