# POS Order API - Documentation

## Overview

The POS Order API endpoint allows you to create Point of Sale orders in Odoo from external systems by sending JSON data.

## Endpoint

**POST** `/api/v1/pos/orders`

## Authentication

Include your API key in the request body:
```json
{
  "api_key": "your-api-key-here",
  ...
}
```

## Request Format

### Required Fields

- `api_key`: Your API authentication key
- `session_id`: ID of an open POS session
- `lines`: Array of order line items
- `payments`: Array of payment methods and amounts

### Optional Fields

- `partner_id`: Customer/partner ID (optional)
- `date_order`: Order date/time (defaults to current time)
- `note`: Order notes/comments
- `to_invoice`: Whether to create invoice (default: false)
- `state`: Order state - 'draft' to keep as draft, otherwise will be marked as paid if payment >= total

### JSON Structure

```json
{
  "api_key": "your-api-key",
  "session_id": 1,
  "partner_id": 1,
  "date_order": "2024-01-15 10:30:00",
  "note": "Order from external system",
  "to_invoice": false,
  "lines": [
    {
      "product_id": 1,
      "qty": 2.0,
      "price_unit": 100.0,
      "discount": 10.0
    },
    {
      "product_id": 2,
      "qty": 1.0,
      "price_unit": 50.0,
      "discount": 0.0
    }
  ],
  "payments": [
    {
      "payment_method_id": 1,
      "amount": 230.0
    }
  ]
}
```

### Order Lines

Each line item in the `lines` array should contain:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| product_id | integer | Yes | Product ID |
| qty | float | Yes | Quantity (default: 1.0) |
| price_unit | float | No | Unit price (default: product list price) |
| discount | float | No | Discount percentage (default: 0.0) |

### Payments

Each payment in the `payments` array should contain:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| payment_method_id | integer | Yes | Payment method ID |
| amount | float | Yes | Payment amount |

## Response Format

### Success Response

```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "Order 00001",
    "pos_reference": "00001",
    "amount_total": 230.0,
    "amount_paid": 230.0,
    "state": "paid",
    "date_order": "2024-01-15 10:30:00"
  },
  "error": null,
  "count": 1
}
```

### Error Response

```json
{
  "status": "error",
  "data": null,
  "error": "Error message here",
  "count": 0
}
```

## Common Errors

### Invalid API Key
```json
{
  "status": "error",
  "data": null,
  "error": "Invalid or missing API key",
  "count": 0
}
```

### Missing Required Fields
```json
{
  "status": "error",
  "data": null,
  "error": "session_id is required",
  "count": 0
}
```

### Session Not Found
```json
{
  "status": "error",
  "data": null,
  "error": "POS session 1 not found",
  "count": 0
}
```

### Session Not Open
```json
{
  "status": "error",
  "data": null,
  "error": "POS session Main Session is not open (state: closed)",
  "count": 0
}
```

### Product Not Found
```json
{
  "status": "error",
  "data": null,
  "error": "Product 999 not found",
  "count": 0
}
```

### Payment Method Not Found
```json
{
  "status": "error",
  "data": null,
  "error": "Payment method 999 not found",
  "count": 0
}
```

## Usage Examples

### cURL Example

```bash
curl -X POST "http://your-odoo-instance.com/api/v1/pos/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-api-key",
    "session_id": 1,
    "partner_id": 1,
    "lines": [
      {
        "product_id": 1,
        "qty": 2.0,
        "price_unit": 100.0,
        "discount": 0.0
      }
    ],
    "payments": [
      {
        "payment_method_id": 1,
        "amount": 200.0
      }
    ]
  }'
```

### Python Example

```python
import requests
import json

url = "http://your-odoo-instance.com/api/v1/pos/orders"
api_key = "your-api-key"

order_data = {
    "api_key": api_key,
    "session_id": 1,
    "partner_id": 1,
    "lines": [
        {
            "product_id": 1,
            "qty": 2.0,
            "price_unit": 100.0,
            "discount": 10.0
        },
        {
            "product_id": 2,
            "qty": 1.0,
            "price_unit": 50.0,
            "discount": 0.0
        }
    ],
    "payments": [
        {
            "payment_method_id": 1,
            "amount": 230.0
        }
    ],
    "note": "Order from external API",
    "to_invoice": False
}

response = requests.post(url, json=order_data)

if response.status_code == 200:
    result = response.json()
    if result["status"] == "success":
        order = result["data"]
        print(f"Order created: {order['name']}")
        print(f"Total: {order['amount_total']}")
        print(f"State: {order['state']}")
    else:
        print(f"Error: {result['error']}")
else:
    print(f"HTTP Error: {response.status_code}")
```

### JavaScript Example

```javascript
const url = "http://your-odoo-instance.com/api/v1/pos/orders";
const apiKey = "your-api-key";

const orderData = {
    api_key: apiKey,
    session_id: 1,
    partner_id: 1,
    lines: [
        {
            product_id: 1,
            qty: 2.0,
            price_unit: 100.0,
            discount: 10.0
        }
    ],
    payments: [
        {
            payment_method_id: 1,
            amount: 200.0
        }
    ],
    note: "Order from external API",
    to_invoice: false
};

fetch(url, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(orderData)
})
.then(response => response.json())
.then(data => {
    if (data.status === 'success') {
        console.log('Order created:', data.data.name);
        console.log('Total:', data.data.amount_total);
    } else {
        console.error('Error:', data.error);
    }
})
.catch(error => console.error('Request failed:', error));
```

## Prerequisites

Before using this API:

1. **POS Session**: You need an open POS session. Get the session ID from:
   - Point of Sale → Sessions
   - Find an open session
   - Use the session ID

2. **Products**: Products must exist in Odoo. Get product IDs from:
   - Inventory → Products → Products
   - Use the product ID

3. **Payment Methods**: Payment methods must be configured. Get payment method IDs from:
   - Point of Sale → Configuration → Point of Sale
   - Payment Methods tab
   - Use the payment method ID

4. **Partner (Optional)**: If you want to assign a customer:
   - Contacts → Contacts
   - Use the partner ID

## Order Processing

1. **Tax Calculation**: Taxes are automatically calculated based on:
   - Product tax settings
   - Fiscal position of the POS configuration
   - Customer tax settings (if partner is specified)

2. **Order State**: 
   - If `state` is set to `'draft'`, order remains in draft
   - Otherwise, if `amount_paid >= amount_total`, order is automatically marked as paid

3. **Order Totals**: Automatically calculated from:
   - Line item prices
   - Discounts
   - Taxes
   - Payment amounts

## Notes

- All amounts should be in the currency of the POS configuration
- Quantities can be decimal values
- Discount is applied as a percentage (e.g., 10.0 = 10%)
- Multiple payment methods can be used (split payments)
- Order will be linked to the specified POS session
- If session is closed, an error will be returned

## Troubleshooting

### Order Not Created

- Check that POS session is open
- Verify all product IDs exist
- Verify all payment method IDs exist
- Check API key is valid and active
- Review server logs for detailed errors

### Tax Calculation Issues

- Verify product has taxes configured
- Check fiscal position settings
- Ensure company currency matches

### Payment Issues

- Verify payment method exists
- Check payment amount matches or exceeds order total
- Ensure payment method is active


