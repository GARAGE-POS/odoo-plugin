# Karage POS Webhook Integration - Setup Guide

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Initial Configuration](#initial-configuration)
4. [Product Configuration](#product-configuration)
5. [POS Session Management](#pos-session-management)
6. [API Authentication](#api-authentication)
7. [Testing the Integration](#testing-the-integration)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance](#maintenance)

---

## Overview

This guide provides step-by-step instructions for setting up the Karage POS Webhook Integration module in Odoo 18. This module allows your external POS system to sync sales orders to Odoo via webhook API, supporting both single order syncing and bulk daily syncing.

### What This Integration Does
- Accepts sales orders from external POS systems via webhook
- Creates POS orders in Odoo with proper accounting entries
- Automatically deducts inventory
- Records payments with multiple payment methods
- Prevents duplicate orders
- Uses external timestamps from your POS system
- Validates order statuses (only accepts completed orders by default)

---

## Prerequisites

Before starting the setup, ensure you have:

1. **Odoo 18** installed and running
2. **Administrator access** to Odoo
3. The **karage_pos module** installed and activated
4. Access to the **PostgreSQL database** (for advanced troubleshooting only)
5. Basic understanding of Odoo POS configuration

---

## Initial Configuration

### Step 1: Access Module Settings

1. Log in to Odoo as an administrator
2. Go to **Settings** (or **General Settings**)
3. Scroll down to find **Karage POS** section

### Step 2: Configure Module Parameters

The module provides several configuration options:

#### Idempotency Configuration
- **Processing Timeout**: Default 5 minutes
  - Maximum time a request can stay in "processing" status before being considered stuck
  - Recommended: Keep default unless you have specific requirements

- **Record Retention**: Default 30 days
  - Number of days to keep old idempotency records
  - Set to 0 to disable automatic cleanup
  - Recommended: 30 days for most use cases

#### Bulk Sync Configuration
- **Maximum Orders per Bulk Request**: Default 1000 orders
  - Limits the number of orders in a single bulk sync request
  - Adjust based on your server capacity
  - Recommended: 500-1000 for most systems

#### Order Validation
- **Valid Order Statuses**: Default "103"
  - Comma-separated list of valid OrderStatus values (e.g., "103,104")
  - Only orders with these status codes will be accepted
  - Status 103 = Completed orders
  - Adjust based on your external POS system's status codes

### Step 3: Save Configuration

Click **Save** to apply all settings.

---

## Product Configuration

**CRITICAL**: All products that will be synced from your external POS system must have proper tax configuration in Odoo.

### Step 1: Configure Product Taxes

For each product that will be synced:

1. Go to **Point of Sale → Products → Products**
2. Open the product (e.g., "Office Chair", "Fuchs Oil 5W30", etc.)
3. Go to the **General Information** tab
4. In the **Customer Taxes** field, add the appropriate tax rate (e.g., 15%)
5. Ensure the following fields are checked:
   - ✅ **Can be Sold**
   - ✅ **Available in POS**
6. Click **Save**

### Step 2: Verify Product Availability

Ensure all products:
- Have correct **Sales Price** set
- Are marked as **Active**
- Are in the same **Company** as your POS configuration
- Are set to **Available in POS**

### Why This Matters
If a product doesn't have taxes configured, but your external POS sends tax amounts, the order will fail with:
```
"Failed to confirm order: Order is not fully paid"
```

This happens because Odoo calculates the order total without tax, while your payment includes tax, causing a mismatch.

---

## POS Session Management

The webhook integration requires an active POS session. The system can automatically manage sessions, but proper configuration is important.

### Option 1: Dedicated External Sync POS Configuration (Recommended)

Create a dedicated POS configuration for webhook integration:

1. Go to **Point of Sale → Configuration → Point of Sale**
2. Click **Create**
3. Set up the configuration:
   - **Name**: Include one of these keywords: "External", "Webhook", "API", or "Integration"
     - Example: "External POS Sync" or "Webhook Integration"
   - **Available Pricelist**: Select default pricelist
   - **Company**: Select your company
   - **Payment Methods**: Configure at minimum:
     - ✅ Cash (required)
     - ✅ Bank/Card (recommended)
4. **Payment Method Configuration** (CRITICAL):
   - Each payment method MUST have a **Journal** configured
   - To check/configure journals:
     - Go to **Point of Sale → Configuration → Payment Methods**
     - For each method, ensure the **Journal** field is set
     - Cash usually uses "Cash" journal
     - Card usually uses "Bank" journal
5. Save the configuration

### Option 2: Use Existing POS Configuration

If you want to use an existing POS configuration:

1. Ensure it has proper payment methods configured with journals
2. Keep a session open manually, or let the system create sessions automatically
3. The system will search for any available POS configuration if no dedicated one is found

### Understanding POS Session States

POS sessions can be in different states:
- **opening_control**: Session is being initialized
- **opened**: Session is active and ready (this is what you want)
- **closing_control**: Session is being closed
- **closed**: Session is closed

### Troubleshooting Multiple Sessions

If you encounter the error:
```
"Another session is already opened for this point of sale"
```

This means multiple sessions exist for the same POS configuration. To fix this:

**Via Odoo UI:**
1. Go to **Point of Sale → Orders → Sessions**
2. Find sessions in "Opening Control" state for your POS configuration
3. Close them by clicking **Close Session** or use the action menu

**Via Database (Advanced):**
```sql
-- View all sessions for a POS config (replace 3 with your config_id)
SELECT id, name, state, config_id
FROM pos_session
WHERE config_id = 3
ORDER BY id DESC;

-- Close stuck sessions (replace IDs with actual stuck session IDs)
UPDATE pos_session
SET state = 'closed', stop_at = NOW()
WHERE id IN (44, 45, 46, 47);
```

---

## API Authentication

The webhook endpoints use Odoo's built-in API key authentication system.

### Step 1: Create an API Key

1. Click your **User Icon** (top right corner)
2. Select **Preferences**
3. Go to the **Account Security** tab
4. Click **New API Key** button
5. Enter a description:
   - Example: "Karage POS Webhook Integration"
   - ⚠️ **Important**: This description is the only way to identify the key later!
6. Set the key duration:
   - For production: Select **Persistent Key** (never expires)
   - For testing: Choose a temporary duration (1 Day, 1 Week, etc.)
7. Click **Generate Key**
8. **COPY THE KEY IMMEDIATELY**
   - ⚠️ **Critical**: You won't be able to see it again!
   - Store it securely (password manager, secrets vault, etc.)

### Step 2: Configure External POS System

Add the API key to your external POS system's webhook configuration:

**Header Format:**
```
X-API-KEY: your_api_key_here
```

**Example curl request:**
```bash
curl -X POST http://your-odoo-server.com/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_api_key_here" \
  -d @payload.json
```

---

## Testing the Integration

### Step 1: Prepare Test Data

Create a test payload with actual product IDs from your Odoo system:

**Single Order Payload Example:**
```json
{
    "OrderID": 2001,
    "OrderDate": "2025-11-27T14:30:00",
    "AmountDiscount": 0.0,
    "AmountPaid": 80.50,
    "AmountTotal": 70.00,
    "BalanceAmount": 0.0,
    "GrandTotal": 80.50,
    "Tax": 10.50,
    "TaxPercent": 15.0,
    "OrderStatus": 103,
    "PaymentMode": 1,
    "OrderItems": [
        {
            "OdooItemID": 5,
            "ItemName": "Office Chair",
            "Price": 70.00,
            "Quantity": 1,
            "DiscountAmount": 0.00
        }
    ],
    "CheckoutDetails": [
        {
            "PaymentMode": 1,
            "AmountPaid": 80.50,
            "CardType": "Cash"
        }
    ]
}
```

### Step 2: Send Test Request

**Single Order Endpoint:**
```bash
POST /api/v1/webhook/pos-order
```

**Bulk Sync Endpoint:**
```bash
POST /api/v1/webhook/pos-order/bulk
```

### Step 3: Verify Success Response

**Successful Response (Single Order):**
```json
{
    "status": "success",
    "data": {
        "id": 23,
        "name": "Bakery Shop/0001",
        "pos_reference": false,
        "amount_total": 80.5,
        "amount_paid": 80.5,
        "amount_tax": 10.5,
        "state": "paid",
        "date_order": "2025-11-27 14:30:00",
        "external_order_id": 2001
    },
    "error": null,
    "count": 1
}
```

**Successful Response (Bulk Sync):**
```json
{
    "status": "success",
    "message": "Processed 10 orders: 8 succeeded, 2 failed",
    "data": {
        "total": 10,
        "succeeded": 8,
        "failed": 2,
        "results": [...]
    }
}
```

### Step 4: Verify in Odoo

1. Go to **Point of Sale → Orders → Orders**
2. Find the newly created order (e.g., "Bakery Shop/0001")
3. Verify:
   - ✅ State is "Paid"
   - ✅ Amount Total matches your payload
   - ✅ Tax is calculated correctly
   - ✅ Date matches your OrderDate
   - ✅ External Order ID is recorded
4. Check inventory:
   - Go to **Inventory → Operations → Transfers**
   - Find the picking (e.g., "WH/POS/00001")
   - Verify it's in "Done" state
   - Check the product quantity was deducted

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "No open POS session found"

**Cause**: No POS session is open for webhook integration.

**Solution**:
- The system should automatically create and open a session
- If not, manually open a session:
  1. Go to **Point of Sale → Dashboard**
  2. Select your POS configuration
  3. Click **New Session**

#### 2. "Another session is already opened"

**Cause**: Multiple sessions exist for the same POS configuration, some in "opening_control" state.

**Solution**:
1. Go to **Point of Sale → Orders → Sessions**
2. Close all stuck sessions in "Opening Control" state
3. Keep only one session in "Opened" state
4. See [POS Session Management](#pos-session-management) section for details

#### 3. "Failed to confirm order: Order is not fully paid"

**Cause**: Product tax configuration mismatch.

**Solution**:
1. Check if the product has taxes configured in Odoo
2. Go to the product and add the appropriate customer tax (e.g., 15%)
3. Ensure the tax percentage matches what your external POS sends
4. See [Product Configuration](#product-configuration) section

#### 4. "No payment methods configured"

**Cause**: POS configuration has no payment methods linked.

**Solution**:
1. Go to **Point of Sale → Configuration → Point of Sale**
2. Edit your POS configuration
3. Add payment methods (Cash, Bank, etc.)
4. Save and retry

#### 5. "Journal not found for payment method"

**Cause**: Payment method exists but has no journal configured.

**Solution**:
1. Go to **Point of Sale → Configuration → Payment Methods**
2. Find the payment method (e.g., "Customer Account", "Cash")
3. Set the **Journal** field (e.g., Cash journal, Bank journal)
4. Save

#### 6. "Duplicate order: OrderID X already exists"

**Cause**: An order with the same OrderID was already processed.

**Solution**:
- This is expected behavior (duplicate prevention)
- Use a unique OrderID for each order
- If you need to retry a failed order, first delete or archive the failed order in Odoo

#### 7. "Invalid OrderStatus: X not in allowed statuses"

**Cause**: The OrderStatus in your payload is not in the allowed list.

**Solution**:
1. Go to **Settings → Karage POS**
2. Update **Valid Order Statuses** field
3. Add the status code (e.g., "103,104,105")
4. Save

#### 8. "Product not found"

**Cause**: The OdooItemID (or ItemID/ItemName) doesn't match any product in Odoo.

**Solution**:
1. Verify the product ID exists: **Point of Sale → Products → Products**
2. Ensure the product is:
   - Active
   - Available in POS
   - Can be Sold
3. Use the correct product ID in your payload

#### 9. "current transaction is aborted"

**Cause**: Database transaction was aborted due to a previous error.

**Solution**:
- This is typically already handled by the code using savepoints
- If you still see this, restart the Odoo service

---

## Maintenance

### Regular Maintenance Tasks

#### 1. Monitor Idempotency Records

Idempotency records are automatically cleaned up based on your retention settings. To manually check:

1. Go to **Technical → Database Structure → Models**
2. Search for "karage.pos.idempotency"
3. View records and their status

#### 2. Review Webhook Logs

Webhook activity is logged. To check logs:

1. Go to **Technical → Database Structure → Models**
2. Search for "karage.pos.webhook.log"
3. Review recent activity and errors

#### 3. Close Old POS Sessions

Periodically close old POS sessions to avoid accumulation:

1. Go to **Point of Sale → Orders → Sessions**
2. Filter by state: "Opened" or "Opening Control"
3. Close sessions that are no longer needed

#### 4. Audit External Orders

To view all orders synced from external POS:

```sql
SELECT id, name, state, external_order_id, external_order_source, date_order
FROM pos_order
WHERE external_order_source = 'karage_pos_webhook'
ORDER BY date_order DESC;
```

Or use Odoo's UI:
1. Go to **Point of Sale → Orders → Orders**
2. Add custom filter: "External Order Source" = "karage_pos_webhook"

### Backup Recommendations

1. **Regular Database Backups**: Use Odoo's backup feature or PostgreSQL dumps
2. **API Key Backup**: Store API keys securely in a password manager
3. **Configuration Documentation**: Document your specific settings and customizations

### Performance Optimization

#### For High Volume Syncing

If you're processing thousands of orders daily:

1. **Increase Bulk Sync Limit**:
   - Go to **Settings → Karage POS**
   - Increase "Maximum Orders per Bulk Request" (e.g., 2000)
   - Monitor server performance

2. **Adjust Idempotency Retention**:
   - Reduce retention days to 7-14 days for high volume
   - This reduces database size

3. **Use Bulk Sync Endpoint**:
   - Instead of sending orders one-by-one
   - Send all orders in a single bulk request daily
   - This is more efficient

4. **Dedicated Database Connection**:
   - Consider using a dedicated database connection for webhook requests
   - Configure Odoo's worker settings appropriately

---

## Summary Checklist

Before going live, verify:

- ✅ Module installed and configured
- ✅ API key created and stored securely
- ✅ All products have appropriate taxes configured
- ✅ POS configuration created with payment methods
- ✅ All payment methods have journals configured
- ✅ POS session management strategy decided
- ✅ Test orders successfully processed
- ✅ Inventory deduction verified
- ✅ Accounting entries verified
- ✅ External POS system configured with API key
- ✅ Error handling and retry logic implemented in external system
- ✅ Monitoring and alerting set up

---

## Support

For issues or questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review Odoo server logs
3. Consult the test_guide.md file for detailed API examples
4. Contact your Odoo administrator or developer

---

## Appendix: Field Mapping Reference

### Required Fields in Payload

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| OrderID | Integer/String | Unique order identifier | 2001 |
| OrderDate | ISO DateTime | Order timestamp from external POS | "2025-11-27T14:30:00" |
| OrderStatus | Integer | Order status code | 103 |
| AmountPaid | Float | Total amount paid by customer | 80.50 |
| AmountTotal | Float | Order subtotal (before tax) | 70.00 |
| Tax | Float | Total tax amount | 10.50 |
| TaxPercent | Float | Tax percentage | 15.0 |
| OrderItems | Array | List of order items | See below |
| CheckoutDetails | Array | Payment details | See below |

### OrderItems Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| OdooItemID | Integer | Direct Odoo product_id (recommended) | 5 |
| ItemID | Integer | Legacy item identifier | 1 |
| ItemName | String | Product name (fallback) | "Office Chair" |
| Price | Float | Unit price | 70.00 |
| Quantity | Float | Quantity ordered | 1 |
| DiscountAmount | Float | Total discount for this line | 0.00 |

### CheckoutDetails Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| PaymentMode | Integer | Payment method code | 1 |
| AmountPaid | Float | Amount paid via this method | 80.50 |
| CardType | String | Payment type description | "Cash" |

### PaymentMode Values

| Code | Description | Odoo Mapping |
|------|-------------|--------------|
| 1 | Cash | Cash journal |
| 2 | Card | Bank/Card journal |
| 3 | Credit | Credit journal |
| 5 | Tabby | Tabby journal |
| 6 | Tamara | Tamara journal |
| 7 | StcPay | StcPay journal |
| 8 | Bank Transfer | Bank journal |

---

**Document Version**: 1.0
**Last Updated**: 2025-11-27
**Module Version**: karage_pos v1.0
