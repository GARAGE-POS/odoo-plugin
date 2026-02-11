# Karage POS - Webhook Integration for Odoo

A custom Odoo addon that provides a REST API webhook endpoint for integrating external POS systems with Odoo's Point of Sale module.

## Table of Contents

- [Quick Start Checklist](#quick-start-checklist)
- [API Authentication](#api-authentication)
- [POS Configuration](#pos-configuration)
- [Payment Method Matching](#payment-method-matching)
- [Journal Configuration](#journal-configuration)
- [Partner/Customer Setup](#partnercustomer-setup)
- [Product Requirements](#product-requirements)
- [System Parameters Reference](#system-parameters-reference)
- [Webhook API Reference](#webhook-api-reference)
- [Troubleshooting](#troubleshooting)

---

## Quick Start Checklist

Before the webhook integration will work, complete these steps:

- [ ] **1. Create API Key**: User menu > Preferences > Account Security > New API Key
- [ ] **2. Configure Payment Methods**: Assign journals to each payment method
- [ ] **3. Name Journals Correctly**: Include CardType keywords in journal names (e.g., "Cash", "Card", "Visa")
- [ ] **4. Set External POS**: Settings > Karage POS > External POS Configuration
- [ ] **5. Configure Picking Type**: Set stock picking type with source location on POS config
- [ ] **6. Set Up Products**: Mark products as `Can be Sold` and `Available in POS`
- [ ] **7. Create Default Partner** (optional): Set `karage_pos.default_partner_id` for auto-invoicing

---

## API Authentication

### Creating an API Key

1. Log into Odoo as the user that will process webhook requests
2. Click your user icon (top right) > **Preferences**
3. Go to **Account Security** section
4. Click **New API Key**
5. Enter a description (e.g., "Karage POS Webhook")
6. **Copy the key immediately** - it cannot be viewed again!

### Using the API Key

Include the API key in all webhook requests:

```http
POST /api/v1/webhook/pos-order/bulk
X-API-KEY: your-api-key-here
Content-Type: application/json
```

### API Key Scopes

The system tries multiple scopes for authentication. Configure in Settings > Karage POS:

- Default: `rpc,odoo.addons.base.models.res_users`

---

## POS Configuration

### Setting the External POS

1. Go to **Settings > Karage POS**
2. Select **External POS Configuration** - this is the POS that will receive webhook orders
3. Save

The addon creates a default POS named "KARAGE - Default POS" during installation.

### Required POS Settings

| Setting | Location | Required |
|---------|----------|----------|
| Payment Methods | POS Config > Payment Methods | Yes - at least one with journal |
| Picking Type | POS Config > Inventory > Operation Type | Yes - for inventory deduction |
| Sales Journal | POS Config > Accounting > Default Journal | Yes |
| Invoice Journal | POS Config > Accounting > Default Invoice Journal | Yes |
| Pricelist | POS Config > Pricing > Default Pricelist | Yes |

---

## Payment Method Matching

This is the most critical configuration. The webhook uses `CardType` from the request to find the correct Odoo payment method.

### How Matching Works

The system uses **3 strategies** in priority order:

#### Strategy 1: CardType in Journal Name (Primary)

The system searches for a payment method whose **journal name contains the CardType** (case-insensitive).

| CardType in Request | Journal Name Must Contain |
|---------------------|---------------------------|
| `Cash` | "cash" |
| `Card` | "card" |
| `Visa` | "visa" |
| `Mada` | "mada" |
| `Mastercard` | "mastercard" |

**Example**: If webhook sends `CardType=Visa`, these journal names would match:
- "Visa Payments" ✅
- "Credit Card - Visa" ✅
- "Bank Account" ❌

#### Strategy 2: Fallback Payment Method

If Strategy 1 fails, uses the configured fallback:
- System Parameter: `karage_pos.fallback_payment_method_id`
- Set to the ID of a payment method to use when CardType doesn't match

#### Strategy 3: Cash for PaymentMode=1

If `PaymentMode=1`, the system looks for a payment method with `is_cash_count=True`.

### Recommended Journal Naming Convention

Create journals with clear names that include the payment type:

| Payment Type | Recommended Journal Name |
|--------------|--------------------------|
| Cash | "Cash" or "Cash Register" |
| Credit Card | "Card Payments" or "Credit Card" |
| Visa | "Visa Card" or "Visa Payments" |
| Mada | "Mada Card" or "Mada Payments" |
| Mastercard | "Mastercard" |
| Bank Transfer | "Bank Transfer" |

### Setting Up Payment Methods

1. Go to **Point of Sale > Configuration > Payment Methods**
2. For each payment method:
   - Assign a **Journal** (required!)
   - The journal name should contain the CardType keyword
3. Add payment methods to your POS configuration

### Example Configuration

```
Payment Method: "Karage - Visa"
├── Journal: "Visa Card Payments" (type: bank)
└── Added to POS Config: "KARAGE - Default POS"

When webhook sends: {"CardType": "Visa", "AmountPaid": 100}
→ System finds journal containing "visa" → Uses "Karage - Visa" payment method
```

---

## Journal Configuration

### Required Journals

| Journal | Type | Purpose | Where to Set |
|---------|------|---------|--------------|
| POS Sales Journal | `sale` | Records POS order revenue | POS Config > Default Journal |
| Invoice Journal | `sale` | Generates customer invoices | POS Config > Default Invoice Journal |
| Payment Journals | `bank` or `cash` | For each payment method | Payment Method > Journal |

### Creating a Payment Journal

1. Go to **Accounting > Configuration > Journals**
2. Click **Create**
3. Set:
   - **Name**: Include payment type (e.g., "Visa Card Payments")
   - **Type**: Bank (for cards) or Cash
   - **Company**: Same as POS
4. Save
5. Assign to payment method

---

## Partner/Customer Setup

Partners are used for invoice generation. If no partner is resolved, the order still succeeds but no invoice is created.

### Partner Resolution Priority

The system resolves partners in this order:

1. **Order-level `partner_id`** - Direct Odoo partner ID in the order
2. **Top-level `partner_id`** - Default partner for all orders in request
3. **Order-level `customer_ref`** - Matches `res.partner.ref` field
4. **Top-level `customer_ref`** - Default customer reference for all orders
5. **Default partner** - From `karage_pos.default_partner_id` setting
6. **None** - Order created without invoice

### Using Customer Reference

To use `customer_ref` lookup:

1. Go to **Contacts**
2. Open a partner
3. Set the **Reference** field (Internal Reference)
4. Use this reference in webhook requests

```json
{
  "customer_ref": "CUST-001",
  "orders": [...]
}
```

### Setting Default Partner

For automatic invoicing on all orders:

1. Go to **Settings > Technical > System Parameters**
2. Create/edit: `karage_pos.default_partner_id`
3. Set value to a partner ID (e.g., `15`)

---

## Product Requirements

### Product Flags

By default, products must have these flags enabled:

| Flag | Default Requirement | Config Parameter |
|------|---------------------|------------------|
| **Can be Sold** | Required | `karage_pos.product_require_sale_ok` |
| **Available in POS** | Required | `karage_pos.product_require_available_in_pos` |
| **Active** | Always required | N/A |
| **Same Company** | Required | `karage_pos.enforce_product_company_match` |

To disable a requirement, set the config parameter to `False`.

### Product Lookup Priority

The webhook finds products using these fields (in order):

1. **OdooItemID** - Direct Odoo product ID (best performance)
2. **ItemID** - Legacy product ID
3. **ItemName** - Exact match on product name
4. **ItemName** - Fuzzy/partial match (with warning)

**Recommendation**: Always use `OdooItemID` for reliable matching.

```json
{
  "OrderItems": [
    {
      "OdooItemID": 35722,  // Preferred
      "PriceWithoutTax": 18.75,
      "Quantity": 1
    }
  ]
}
```

---

## System Parameters Reference

All configuration parameters (Settings > Technical > System Parameters):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `karage_pos.external_pos_config_id` | Auto-set | POS config ID for webhook orders |
| `karage_pos.fallback_payment_method_id` | `0` | Fallback payment method when CardType doesn't match |
| `karage_pos.fallback_payment_mode` | `1` | Default PaymentMode when not provided |
| `karage_pos.default_partner_id` | `0` | Default partner for invoicing |
| `karage_pos.api_key_scopes` | `rpc,odoo.addons.base.models.res_users` | API authentication scopes |
| `karage_pos.valid_order_statuses` | `103,106` | Valid OrderStatus codes (103=sale, 106=refund) |
| `karage_pos.bulk_sync_max_orders` | `1000` | Max orders per bulk request |
| `karage_pos.external_order_source_code` | `karage_pos_webhook` | Source identifier on orders |
| `karage_pos.product_require_sale_ok` | `True` | Require "Can be Sold" flag |
| `karage_pos.product_require_available_in_pos` | `True` | Require "Available in POS" flag |
| `karage_pos.enforce_product_company_match` | `True` | Require product in same company |
| `karage_pos.auto_close_sessions` | `True` | Auto-close idle POS sessions |
| `karage_pos.session_idle_timeout_minutes` | `60` | Minutes before auto-close |
| `karage_pos.acceptable_session_states` | `opened,opening_control` | Valid session states for orders |

---

## Webhook API Reference

### Endpoint

```
POST /api/v1/webhook/pos-order/bulk
```

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-KEY` | Yes | Odoo API key for authentication |
| `Content-Type` | Yes | Must be `application/json` |

### Request Body

```json
{
  "pos_config_id": 5,
  "partner_id": 15,
  "customer_ref": "CUST-001",
  "orders": [
    {
      "OrderID": "12345",
      "OrderDate": "2025-01-15T10:30:00+00:00",
      "OrderStatus": 103,
      "partner_id": 20,
      "customer_ref": "CUST-002",
      "OrderItems": [
        {
          "OdooItemID": 35722,
          "ItemID": 0,
          "ItemName": "Product Name",
          "PriceWithoutTax": 100.00,
          "Quantity": 2,
          "DiscountPercentage": 10
        }
      ],
      "CheckoutDetails": [
        {
          "PaymentMode": 1,
          "CardType": "Cash",
          "AmountPaid": 180.00
        }
      ]
    }
  ]
}
```

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pos_config_id` | Integer | No | POS config to use (falls back to default) |
| `partner_id` | Integer | No | Default partner for all orders |
| `customer_ref` | String | No | Customer reference lookup |
| `orders` | Array | Yes | Array of order objects |

#### Order Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `OrderID` | String | Yes | External order identifier |
| `OrderDate` | ISO 8601 | No | Order datetime |
| `OrderStatus` | Integer | Yes | 103=sale, 106=refund |
| `partner_id` | Integer | No | Order-level partner override |
| `customer_ref` | String | No | Order-level customer ref |
| `OrderItems` | Array | Yes | Line items |
| `CheckoutDetails` | Array | Yes | Payment details |

#### Order Item Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `OdooItemID` | Integer | Recommended | Odoo product ID |
| `ItemID` | Integer | No | Legacy product ID |
| `ItemName` | String | No | Product name (fuzzy match) |
| `PriceWithoutTax` | Float | Yes | Unit price excluding tax |
| `Quantity` | Float | Yes | Quantity (negative for refunds) |
| `DiscountPercentage` | Float | No | Discount percent (0-100) |

#### Checkout Detail Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `PaymentMode` | Integer | No | 1=Cash, 2=Card, etc. |
| `CardType` | String | Yes | Payment type for matching |
| `AmountPaid` | Float | Yes | Payment amount |

### Response

#### Success (200)

```json
{
  "status": "success",
  "data": {
    "pos_config_id": 5,
    "total": 2,
    "successful": 2,
    "failed": 0,
    "results": [
      {
        "external_order_id": "12345",
        "status": "success",
        "pos_order_id": 150,
        "pos_order_name": "KARAGE - Default POS/0001",
        "amount_total": 207.00,
        "tax_percent": 15.00
      }
    ]
  },
  "error": null,
  "count": 1
}
```

#### Partial Success (207)

Some orders succeeded, some failed. Check individual results.

#### Error (400/401/500)

```json
{
  "status": "error",
  "data": null,
  "error": "Error message here",
  "count": 0
}
```

---

## Troubleshooting

### Payment Method Not Found

**Error**: `No payment method found for PaymentMode=2, CardType=Card`

**Cause**: No payment method has a journal name containing "Card".

**Solutions**:
1. Rename your card payment journal to include "Card" (e.g., "Card Payments")
2. Or set `karage_pos.fallback_payment_method_id` to a default payment method ID
3. Verify the payment method is added to your POS configuration

---

### Duplicate Order Error

**Error**: `Duplicate order: OrderID 720 already exists as KARAGE - Default POS/0043`

**Cause**: This OrderID was already processed successfully.

**Solutions**:
1. This is expected behavior - the system prevents duplicate processing
2. Use unique OrderIDs for each new order
3. Check if the order already exists in Odoo POS orders

---

### Product Not Found

**Error**: `Product not found: OdooItemID=35722, ItemID=0, ItemName="Product"`

**Cause**: Product doesn't exist or doesn't meet requirements.

**Solutions**:
1. Verify the product exists in Odoo
2. Check product has `Can be Sold` enabled
3. Check product has `Available in POS` enabled
4. Verify product belongs to the same company as the POS
5. Use the correct `OdooItemID` (product.product ID, not product.template ID)

---

### Invalid Partner ID

**Error**: `partner_id must be greater than zero` or `partner_id 999 does not exist in Odoo`

**Cause**: The partner_id provided is invalid or doesn't exist.

**Solutions**:
1. Verify the partner exists in Odoo Contacts
2. Use a valid positive integer for partner_id
3. Or use `customer_ref` instead to lookup by reference

---

### POS Config Not Found

**Error**: `pos_config_id 99 does not exist in Odoo`

**Cause**: The specified POS configuration doesn't exist.

**Solutions**:
1. Go to Point of Sale > Configuration > Point of Sale
2. Find a valid POS config and use its ID
3. Or omit `pos_config_id` to use the default from settings

---

### API Key Authentication Failed

**Error**: `Invalid or missing API key`

**Cause**: The API key is invalid, expired, or not provided.

**Solutions**:
1. Verify the `X-API-KEY` header is included in the request
2. Create a new API key (User menu > Preferences > Account Security)
3. Check the user has appropriate permissions
4. Verify API key scopes in settings

---

### Session Errors

**Error**: `No POS configuration found for external sync`

**Cause**: No external POS is configured.

**Solutions**:
1. Go to Settings > Karage POS
2. Set the External POS Configuration
3. Ensure the POS has payment methods with journals configured

---

## Support

For issues and feature requests, please contact your system administrator or refer to the Odoo documentation.
