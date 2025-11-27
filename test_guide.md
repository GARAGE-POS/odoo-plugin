# Karage POS Webhook Testing Guide

This guide covers testing the enhanced webhook endpoints with new features including OdooItemID support, bulk sync, duplicate detection, and order validation.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Single Order Endpoint](#single-order-endpoint)
3. [Bulk Sync Endpoint](#bulk-sync-endpoint)
4. [New Features Testing](#new-features-testing)
5. [Configuration](#configuration)

---

## Prerequisites

Before testing, ensure you have:

1. **API Key**: Create an API key in Odoo (User Icon → Preferences → Account Security → New API Key)
2. **Open POS Session**: Navigate to Point of Sale → Sessions → New Session
3. **Payment Methods**: Configure at least one payment method (Cash, Card, etc.)
4. **Products**: Have products available in POS or test with product creation

---

## Single Order Endpoint

### Endpoint: `POST /api/v1/webhook/pos-order`

### 1. Basic Test with OdooItemID (NEW - Recommended)

**Using direct Odoo Product ID (fastest and most reliable):**

```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -H "Idempotency-Key: test-order-$(date +%s)" \
  -d '{
    "OrderID": 12345,
    "OrderDate": "2025-11-27T14:30:00",
    "OrderStatus": 103,
    "AmountTotal": 100.00,
    "AmountPaid": 100.00,
    "GrandTotal": 100.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [
      {
        "OdooItemID": 1,
        "ItemName": "Test Product",
        "Price": 100.00,
        "Quantity": 1,
        "DiscountAmount": 0.00
      }
    ],
    "CheckoutDetails": [
      {
        "PaymentMode": 1,
        "AmountPaid": 100.00,
        "CardType": "Cash"
      }
    ]
  }'
```

**Note:** Replace `OdooItemID: 1` with an actual product ID from your Odoo database.

### 2. Legacy Test with ItemID (Backward Compatible)

**Using legacy ItemID field:**

```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -H "Idempotency-Key: test-order-$(date +%s)" \
  -d '{
    "OrderID": 12346,
    "OrderDate": "2025-11-27T14:35:00",
    "OrderStatus": 103,
    "AmountTotal": 100.00,
    "AmountPaid": 100.00,
    "GrandTotal": 100.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [
      {
        "ItemID": 1,
        "ItemName": "Test Product",
        "Price": 100.00,
        "Quantity": 1,
        "DiscountAmount": 0.00
      }
    ],
    "CheckoutDetails": [
      {
        "PaymentMode": 1,
        "AmountPaid": 100.00,
        "CardType": "Cash"
      }
    ]
  }'
```

### 3. Full Example with Tax and Multiple Items

```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -H "Idempotency-Key: order-2025-11-27-001" \
  -d '{
    "OrderID": 639,
    "OrderDate": "2025-11-27T10:30:00",
    "OrderStatus": 103,
    "AmountDiscount": 0.0,
    "AmountPaid": 92.0,
    "AmountTotal": 80.0,
    "BalanceAmount": 0.0,
    "GrandTotal": 92.0,
    "Tax": 12.0,
    "TaxPercent": 15.0,
    "PaymentMode": 1,
    "OrderItems": [
      {
        "OdooItemID": 1,
        "ItemName": "Fuchs Oil 5W30 Syn Sn",
        "Price": 80.00,
        "Quantity": 1,
        "DiscountAmount": 0.00
      }
    ],
    "CheckoutDetails": [
      {
        "PaymentMode": 1,
        "AmountPaid": 92.00,
        "CardType": "Cash"
      }
    ]
  }'
```

---

## Bulk Sync Endpoint (NEW)

### Endpoint: `POST /api/v1/webhook/pos-order/bulk`

### 1. Basic Bulk Sync Test

**Process multiple orders in a single request:**

```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order/bulk \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -d '{
    "orders": [
      {
        "OrderID": 1001,
        "OrderDate": "2025-11-27T08:00:00",
        "OrderStatus": 103,
        "AmountTotal": 50.00,
        "AmountPaid": 50.00,
        "GrandTotal": 50.00,
        "Tax": 0.00,
        "TaxPercent": 0.00,
        "BalanceAmount": 0.00,
        "OrderItems": [
          {
            "OdooItemID": 1,
            "ItemName": "Product A",
            "Price": 50.00,
            "Quantity": 1,
            "DiscountAmount": 0.00
          }
        ],
        "CheckoutDetails": [
          {
            "PaymentMode": 1,
            "AmountPaid": 50.00,
            "CardType": "Cash"
          }
        ]
      },
      {
        "OrderID": 1002,
        "OrderDate": "2025-11-27T09:00:00",
        "OrderStatus": 103,
        "AmountTotal": 75.00,
        "AmountPaid": 75.00,
        "GrandTotal": 75.00,
        "Tax": 0.00,
        "TaxPercent": 0.00,
        "BalanceAmount": 0.00,
        "OrderItems": [
          {
            "OdooItemID": 2,
            "ItemName": "Product B",
            "Price": 75.00,
            "Quantity": 1,
            "DiscountAmount": 0.00
          }
        ],
        "CheckoutDetails": [
          {
            "PaymentMode": 1,
            "AmountPaid": 75.00,
            "CardType": "Cash"
          }
        ]
      }
    ]
  }'
```

### 2. Expected Bulk Response

**All successful:**
```json
{
  "status": "success",
  "data": {
    "total": 2,
    "successful": 2,
    "failed": 0,
    "results": [
      {
        "external_order_id": 1001,
        "status": "success",
        "pos_order_id": 123,
        "pos_order_name": "Order/0001",
        "amount_total": 50.0
      },
      {
        "external_order_id": 1002,
        "status": "success",
        "pos_order_id": 124,
        "pos_order_name": "Order/0002",
        "amount_total": 75.0
      }
    ]
  },
  "count": 2
}
```

**Partial success:**
```json
{
  "status": "success",
  "data": {
    "total": 2,
    "successful": 1,
    "failed": 1,
    "results": [
      {
        "external_order_id": 1001,
        "status": "success",
        "pos_order_id": 123,
        "pos_order_name": "Order/0001",
        "amount_total": 50.0
      },
      {
        "external_order_id": 1002,
        "status": "error",
        "error": "Product not found: OdooItemID=999, ItemID=0, ItemName=\"Invalid Product\""
      }
    ]
  },
  "count": 2
}
```

---

## New Features Testing

### 1. Test Duplicate Order Detection (NEW)

**First request - creates order:**
```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -d '{
    "OrderID": 999,
    "OrderDate": "2025-11-27T12:00:00",
    "OrderStatus": 103,
    "AmountTotal": 50.00,
    "AmountPaid": 50.00,
    "GrandTotal": 50.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [{"OdooItemID": 1, "ItemName": "Test", "Price": 50.00, "Quantity": 1, "DiscountAmount": 0.00}],
    "CheckoutDetails": [{"PaymentMode": 1, "AmountPaid": 50.00, "CardType": "Cash"}]
  }'
```

**Second request with same OrderID - should be rejected:**
```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -d '{
    "OrderID": 999,
    "OrderDate": "2025-11-27T12:05:00",
    "OrderStatus": 103,
    "AmountTotal": 50.00,
    "AmountPaid": 50.00,
    "GrandTotal": 50.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [{"OdooItemID": 1, "ItemName": "Test", "Price": 50.00, "Quantity": 1, "DiscountAmount": 0.00}],
    "CheckoutDetails": [{"PaymentMode": 1, "AmountPaid": 50.00, "CardType": "Cash"}]
  }'
```

**Expected response:**
```json
{
  "status": "error",
  "data": null,
  "error": "Duplicate order: OrderID 999 already exists as Order/0001",
  "count": 0
}
```

### 2. Test OrderStatus Validation (NEW)

**Invalid status (not completed):**
```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -d '{
    "OrderID": 888,
    "OrderDate": "2025-11-27T13:00:00",
    "OrderStatus": 100,
    "AmountTotal": 50.00,
    "AmountPaid": 50.00,
    "GrandTotal": 50.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [{"OdooItemID": 1, "ItemName": "Test", "Price": 50.00, "Quantity": 1, "DiscountAmount": 0.00}],
    "CheckoutDetails": [{"PaymentMode": 1, "AmountPaid": 50.00, "CardType": "Cash"}]
  }'
```

**Expected response:**
```json
{
  "status": "error",
  "data": null,
  "error": "Invalid OrderStatus: 100. Only completed orders (103) are accepted.",
  "count": 0
}
```

### 3. Test Product Lookup Priority (NEW)

**Priority 1 - OdooItemID (preferred):**
- If `OdooItemID` is provided and valid, it's used immediately
- Fastest and most reliable method

**Priority 2 - ItemID (legacy):**
- If `OdooItemID` not provided, falls back to `ItemID`
- Maintains backward compatibility

**Priority 3 - ItemName (fallback):**
- If neither ID provided, searches by product name
- Logs warning suggesting to use OdooItemID

**Priority 4 - Fuzzy match:**
- Case-insensitive name search as last resort
- Logs warning about accuracy

### 4. Test External Timestamp (NEW)

**Order with past timestamp:**
```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -d '{
    "OrderID": 777,
    "OrderDate": "2025-11-26T08:30:00",
    "OrderStatus": 103,
    "AmountTotal": 50.00,
    "AmountPaid": 50.00,
    "GrandTotal": 50.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [{"OdooItemID": 1, "ItemName": "Test", "Price": 50.00, "Quantity": 1, "DiscountAmount": 0.00}],
    "CheckoutDetails": [{"PaymentMode": 1, "AmountPaid": 50.00, "CardType": "Cash"}]
  }'
```

The order will be created with `date_order` set to `2025-11-26 08:30:00` (external timestamp), not current time.

---

## Test Idempotency (Existing Feature)

Run the same request twice with the same Idempotency-Key - the second request returns cached response:

**First request - creates order:**
```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -H "Idempotency-Key: idempotency-test-123" \
  -d '{
    "OrderID": 555,
    "OrderDate": "2025-11-27T15:00:00",
    "OrderStatus": 103,
    "AmountTotal": 50.00,
    "AmountPaid": 50.00,
    "GrandTotal": 50.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [{"OdooItemID": 1, "ItemName": "Test", "Price": 50.00, "Quantity": 1, "DiscountAmount": 0.00}],
    "CheckoutDetails": [{"PaymentMode": 1, "AmountPaid": 50.00, "CardType": "Cash"}]
  }'
```

**Second request - returns cached response (no new order created):**
```bash
curl -X POST http://localhost:8069/api/v1/webhook/pos-order \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY_HERE" \
  -H "Idempotency-Key: idempotency-test-123" \
  -d '{
    "OrderID": 555,
    "OrderDate": "2025-11-27T15:00:00",
    "OrderStatus": 103,
    "AmountTotal": 50.00,
    "AmountPaid": 50.00,
    "GrandTotal": 50.00,
    "Tax": 0.00,
    "TaxPercent": 0.00,
    "BalanceAmount": 0.00,
    "OrderItems": [{"OdooItemID": 1, "ItemName": "Test", "Price": 50.00, "Quantity": 1, "DiscountAmount": 0.00}],
    "CheckoutDetails": [{"PaymentMode": 1, "AmountPaid": 50.00, "CardType": "Cash"}]
  }'
```

---

## Configuration

### Accessing Settings

1. Navigate to: **Settings** → **Karage POS**
2. Configure the following:

#### Bulk Sync Configuration
- **Bulk Sync Max Orders**: Maximum orders per bulk request (default: 1000)

#### Order Validation
- **Valid Order Statuses**: Comma-separated list (e.g., "103,104")
  - Default: "103" (completed orders only)

#### Idempotency Configuration
- **Processing Timeout**: Max time in processing status (default: 5 minutes)
- **Record Retention**: Days to keep old records (default: 30 days)

---

## Expected Responses

### Success Response

```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "Order 00123-456-0001",
    "pos_reference": "Order 00123-456-0001",
    "amount_total": 100.0,
    "amount_paid": 100.0,
    "amount_tax": 0.0,
    "state": "paid",
    "date_order": "2025-11-27 10:30:00",
    "external_order_id": 12345
  },
  "error": null,
  "count": 1
}
```

### Common Error Responses

**Missing API Key:**
```json
{
  "status": "error",
  "data": null,
  "error": "Invalid or missing API key",
  "count": 0
}
```

**No Open POS Session:**
```json
{
  "status": "error",
  "data": null,
  "error": "No open POS session found. Please open a POS session first.",
  "count": 0
}
```

**Product Not Found:**
```json
{
  "status": "error",
  "data": null,
  "error": "Product not found: OdooItemID=999, ItemID=0, ItemName=\"Invalid Product\"",
  "count": 0
}
```

**Duplicate Order (NEW):**
```json
{
  "status": "error",
  "data": null,
  "error": "Duplicate order: OrderID 999 already exists as Order/0001",
  "count": 0
}
```

**Invalid Order Status (NEW):**
```json
{
  "status": "error",
  "data": null,
  "error": "Invalid OrderStatus: 100. Only completed orders (103) are accepted.",
  "count": 0
}
```

**Product Not Available in POS (NEW):**
```json
{
  "status": "error",
  "data": null,
  "error": "Product 'Test Product' (ID: 1) is not available in POS",
  "count": 0
}
```

**Bulk Size Limit Exceeded (NEW):**
```json
{
  "status": "error",
  "data": null,
  "error": "Too many orders: 1500. Maximum allowed: 1000",
  "count": 0
}
```

---

## Troubleshooting

### Issue: "Duplicate order" error
**Solution:** Each OrderID can only be used once. Use a unique OrderID for each order or wait for the existing order to be processed.

### Issue: "Invalid OrderStatus" error
**Solution:** Only completed orders (status 103) are accepted by default. Check Settings → Karage POS → Valid Order Statuses to configure accepted statuses.

### Issue: "Product not found" error
**Solution:**
- Ensure the product exists in Odoo
- Use OdooItemID (direct product_id) for best results
- Check that product is marked as "Available in POS"
- Verify product is active and available for sale

### Issue: Orders not deducting inventory
**Solution:**
- Check that POS session is open
- Verify POS configuration has picking type configured
- Ensure products have proper stock tracking enabled

### Issue: Bulk sync timing out
**Solution:**
- Reduce batch size (default limit: 1000 orders)
- Split large syncs into multiple smaller batches
- Increase server timeout settings if needed

---

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/webhook/pos-order` | POST | Create single POS order |
| `/api/v1/webhook/pos-order/bulk` | POST | Create multiple POS orders (NEW) |

---

## New Fields Reference

### OrderItems
- `OdooItemID` (NEW, recommended): Direct Odoo product_id
- `ItemID` (legacy): Legacy product identifier
- `ItemName`: Product name (fallback)

### Order Level
- `OrderDate` (NEW): External order timestamp (ISO format)
- `OrderStatus` (validated): Order status code (103 = completed)
- `OrderID`: External order identifier (must be unique)

---

## Testing Checklist

- [ ] Single order with OdooItemID
- [ ] Single order with ItemID (legacy)
- [ ] Single order with only ItemName (fallback)
- [ ] Bulk sync with 2-10 orders
- [ ] Bulk sync with partial failures
- [ ] Duplicate order detection (same OrderID)
- [ ] Invalid OrderStatus rejection
- [ ] Idempotency with Idempotency-Key
- [ ] External timestamp preservation
- [ ] Product validation (inactive, not in POS, etc.)
- [ ] Multiple payment methods
- [ ] Orders with tax calculations
- [ ] Orders with discounts

---

## Support

For issues or questions:
1. Check webhook logs in Odoo: Settings → Technical → Webhook Logs
2. Review Odoo server logs for detailed error messages
3. Verify POS session is open and configured correctly
4. Ensure products and payment methods are properly set up