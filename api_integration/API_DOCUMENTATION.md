# API Integration - Complete API Documentation

## Overview

This document provides complete documentation for the API Integration module endpoints, including detailed JSON format specifications, request/response examples, and error handling.

## Table of Contents

1. [Authentication](#authentication)
2. [Base URL and Endpoints](#base-url-and-endpoints)
3. [Response Format](#response-format)
4. [Unit of Measures API](#unit-of-measures-api)
5. [Products API](#products-api)
6. [Vendors API](#vendors-api)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)
9. [Best Practices](#best-practices)

## Authentication

All API endpoints require authentication using an API key.

### Getting an API Key

1. Log in to Odoo as Administrator
2. Navigate to **Settings → API Configuration**
3. Create a new API configuration
4. Copy the generated API key

### Using the API Key

Include the API key as a query parameter in all requests:

```
?api_key=YOUR_API_KEY_HERE
```

## Base URL and Endpoints

**Base URL:** `http://your-odoo-instance.com`

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/uom` | Get unit of measures |
| GET | `/api/v1/products` | Get products |
| GET | `/api/v1/vendors` | Get vendors |
| POST | `/api/v1/pos/orders` | Create POS order |

## Response Format

All API responses follow a standard format:

```json
{
  "status": "success" | "error",
  "data": <response_data>,
  "error": <error_message_or_null>,
  "count": <number_of_items>
}
```

### Success Response Example

```json
{
  "status": "success",
  "data": [...],
  "error": null,
  "count": 10
}
```

### Error Response Example

```json
{
  "status": "error",
  "data": null,
  "error": "Invalid or missing API key",
  "count": 0
}
```

## Unit of Measures API

### Endpoint
```
GET /api/v1/uom
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| api_key | string | Yes | - | API authentication key |
| limit | integer | No | All | Maximum number of records |
| offset | integer | No | 0 | Number of records to skip |

### Request Example

```bash
curl "http://your-odoo-instance.com/api/v1/uom?api_key=abc123&limit=10&offset=0"
```

### Response Example

```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "Units",
      "category_id": {
        "id": 1,
        "name": "Unit"
      },
      "factor": 1.0,
      "factor_inv": 1.0,
      "rounding": 0.01,
      "uom_type": "reference",
      "active": true
    },
    {
      "id": 2,
      "name": "Dozen",
      "category_id": {
        "id": 1,
        "name": "Unit"
      },
      "factor": 12.0,
      "factor_inv": 0.08333333333333333,
      "rounding": 0.01,
      "uom_type": "bigger",
      "active": true
    }
  ],
  "error": null,
  "count": 2
}
```

### Field Descriptions

- **id**: Unique identifier for the UoM
- **name**: Display name of the unit
- **category_id**: UoM category object with id and name
- **factor**: Conversion factor to reference unit (e.g., 12 for dozen)
- **factor_inv**: Inverse conversion factor (1/factor)
- **rounding**: Rounding precision for calculations
- **uom_type**: Type of UoM (reference, bigger, smaller)
- **active**: Whether the UoM is active

## Products API

### Endpoint
```
GET /api/v1/products
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| api_key | string | Yes | - | API authentication key |
| limit | integer | No | All | Maximum number of records |
| offset | integer | No | 0 | Number of records to skip |
| active_only | boolean | No | true | Return only active products |

### Request Example

```bash
curl "http://your-odoo-instance.com/api/v1/products?api_key=abc123&limit=5&offset=0&active_only=true"
```

### Response Example

```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "Office Chair",
      "description": "Ergonomic office chair with adjustable height",
      "description_purchase": "Purchase description for office chair",
      "description_sale": "Sales description for office chair",
      "type": "storable",
      "categ_id": {
        "id": 1,
        "name": "Furniture"
      },
      "categories": [
        {
          "id": 1,
          "name": "Furniture"
        },
        {
          "id": 2,
          "name": "Office / Furniture"
        }
      ],
      "list_price": 299.99,
      "standard_price": 150.00,
      "uom_id": {
        "id": 1,
        "name": "Units"
      },
      "uom_po_id": {
        "id": 1,
        "name": "Units"
      },
      "barcode": "1234567890123",
      "default_code": "CHAIR-001",
      "sale_ok": true,
      "purchase_ok": true,
      "active": true,
      "weight": 15.5,
      "volume": 0.2,
      "image_url": "/web/image/product.template/1/image_1920",
      "variants": [
        {
          "id": 1,
          "default_code": "CHAIR-001-BLACK",
          "barcode": "1234567890124",
          "weight": 15.5,
          "volume": 0.2
        },
        {
          "id": 2,
          "default_code": "CHAIR-001-WHITE",
          "barcode": "1234567890125",
          "weight": 15.5,
          "volume": 0.2
        }
      ],
      "suppliers": [
        {
          "id": 1,
          "name": "Furniture Supplier Inc",
          "price": 120.00,
          "currency_id": {
            "id": 1,
            "name": "USD"
          },
          "min_qty": 10.0,
          "delay": 7
        }
      ]
    }
  ],
  "error": null,
  "count": 1
}
```

### Field Descriptions

#### Product Fields
- **id**: Product template ID
- **name**: Product name
- **description**: Internal description
- **description_purchase**: Description for purchase orders
- **description_sale**: Description for sales orders
- **type**: Product type (consu, service, storable)
- **categ_id**: Main product category
- **categories**: Array of all categories this product belongs to
- **list_price**: Sale price
- **standard_price**: Cost/standard price
- **uom_id**: Unit of measure for sales
- **uom_po_id**: Unit of measure for purchases
- **barcode**: Product barcode (EAN13, UPC, etc.)
- **default_code**: Internal reference code
- **sale_ok**: Can be sold (boolean)
- **purchase_ok**: Can be purchased (boolean)
- **active**: Whether product is active
- **weight**: Product weight
- **volume**: Product volume
- **image_url**: URL to product image (if available)

#### Variants Array
Each product variant includes:
- **id**: Variant ID
- **default_code**: Variant internal code
- **barcode**: Variant barcode
- **weight**: Variant weight
- **volume**: Variant volume

#### Suppliers Array
Each supplier includes:
- **id**: Supplier partner ID
- **name**: Supplier name
- **price**: Supplier price for this product
- **currency_id**: Currency object (id, name)
- **min_qty**: Minimum order quantity
- **delay**: Delivery delay in days

## Vendors API

### Endpoint
```
GET /api/v1/vendors
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| api_key | string | Yes | - | API authentication key |
| limit | integer | No | All | Maximum number of records |
| offset | integer | No | 0 | Number of records to skip |
| active_only | boolean | No | true | Return only active vendors |

### Request Example

```bash
curl "http://your-odoo-instance.com/api/v1/vendors?api_key=abc123&limit=10&offset=0&active_only=true"
```

### Response Example

```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "Furniture Supplier Inc",
      "display_name": "Furniture Supplier Inc",
      "ref": "VEND-001",
      "vat": "US123456789",
      "email": "contact@furnituresupplier.com",
      "phone": "+1-555-0123",
      "mobile": "+1-555-0124",
      "website": "https://furnituresupplier.com",
      "street": "123 Industrial Blvd",
      "street2": "Building A",
      "city": "New York",
      "state_id": {
        "id": 1,
        "name": "New York",
        "code": "NY"
      },
      "zip": "10001",
      "country_id": {
        "id": 1,
        "name": "United States",
        "code": "US"
      },
      "supplier_rank": 1,
      "active": true,
      "image_url": "/web/image/res.partner/1/image_1920",
      "products": [
        {
          "id": 1,
          "name": "Office Chair",
          "product_code": "VEND-CHAIR-001",
          "price": 120.00,
          "min_qty": 10.0,
          "delay": 7
        },
        {
          "id": 2,
          "name": "Desk",
          "product_code": "VEND-DESK-001",
          "price": 250.00,
          "min_qty": 5.0,
          "delay": 14
        }
      ]
    }
  ],
  "error": null,
  "count": 1
}
```

### Field Descriptions

#### Vendor Fields
- **id**: Vendor partner ID
- **name**: Vendor company name
- **display_name**: Full display name
- **ref**: Internal reference code
- **vat**: VAT/Tax identification number
- **email**: Primary email address
- **phone**: Primary phone number
- **mobile**: Mobile phone number
- **website**: Company website URL
- **street**: Street address line 1
- **street2**: Street address line 2
- **city**: City name
- **state_id**: State/province object (id, name, code)
- **zip**: ZIP/postal code
- **country_id**: Country object (id, name, code)
- **supplier_rank**: Supplier ranking (higher = more preferred)
- **active**: Whether vendor is active
- **image_url**: URL to vendor logo (if available)

#### Products Array
Each product supplied by the vendor includes:
- **id**: Product ID
- **name**: Product name
- **product_code**: Vendor's product code
- **price**: Price from this vendor
- **min_qty**: Minimum order quantity
- **delay**: Delivery delay in days

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized (invalid/missing API key) |
| 500 | Internal server error |

### Error Response Format

```json
{
  "status": "error",
  "data": null,
  "error": "Error message here",
  "count": 0
}
```

### Common Errors

#### 401 Unauthorized
```json
{
  "status": "error",
  "data": null,
  "error": "Invalid or missing API key",
  "count": 0
}
```

**Solution:** Check that your API key is correct and the API configuration is active.

#### 500 Internal Server Error
```json
{
  "status": "error",
  "data": null,
  "error": "Internal server error: <details>",
  "count": 0
}
```

**Solution:** Check server logs and contact system administrator.

## Rate Limiting

Currently, there are no rate limits imposed. However, it's recommended to:
- Implement reasonable delays between requests
- Use pagination for large datasets
- Cache responses when possible

## Best Practices

### 1. Pagination
Always use pagination for large datasets:
```
GET /api/v1/products?api_key=xxx&limit=50&offset=0
GET /api/v1/products?api_key=xxx&limit=50&offset=50
```

### 2. Error Handling
Always check the `status` field in responses:
```python
response = requests.get(url)
data = response.json()
if data['status'] == 'error':
    print(f"Error: {data['error']}")
else:
    process_data(data['data'])
```

### 3. API Key Security
- Never commit API keys to version control
- Use environment variables for API keys
- Rotate API keys regularly
- Use different keys for different environments

### 4. Caching
Cache API responses when appropriate to reduce server load:
```python
import time
from functools import lru_cache

@lru_cache(maxsize=100)
def get_products_cached(api_key, limit, offset):
    # Cache for 5 minutes
    return get_products(api_key, limit, offset)
```

### 5. Retry Logic
Implement retry logic for transient failures:
```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
```

## POS Orders API

### Endpoint
```
POST /api/v1/pos/orders
```

### Description
Create a Point of Sale order from external API by sending JSON data.

### Request Body

```json
{
  "api_key": "your-api-key",
  "session_id": 1,
  "partner_id": 1,
  "lines": [
    {
      "product_id": 1,
      "qty": 2.0,
      "price_unit": 100.0,
      "discount": 10.0
    }
  ],
  "payments": [
    {
      "payment_method_id": 1,
      "amount": 180.0
    }
  ],
  "date_order": "2024-01-15 10:30:00",
  "note": "Order from external API",
  "to_invoice": false
}
```

### Response Example

```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "Order 00001",
    "pos_reference": "00001",
    "amount_total": 180.0,
    "amount_paid": 180.0,
    "state": "paid",
    "date_order": "2024-01-15 10:30:00"
  },
  "error": null,
  "count": 1
}
```

For complete POS Order API documentation, see [POS_ORDER_API.md](POS_ORDER_API.md).

## POS Order Webhook API

### Endpoint
```
POST /api/v1/webhook/pos-order
```

### Description
Webhook endpoint to create and confirm POS orders from external systems. This endpoint automatically:
- Creates the POS order
- Confirms the order (marks as paid)
- Generates inventory consumption (picking)
- Creates accounting payment entries

### Authentication
API key can be provided in:
- Request header: `X-API-Key: your-api-key`
- Request body: `{"api_key": "your-api-key", ...}`

### Request Body Format

```json
{
  "OrderID": 639,
  "AmountDiscount": 0.0,
  "AmountPaid": "92.0",
  "AmountTotal": 80.0,
  "BalanceAmount": 0.0,
  "GrandTotal": 92.0,
  "Tax": 12.0,
  "TaxPercent": 15.0,
  "OrderStatus": 103,
  "PaymentMode": 1,
  "CheckoutDetails": [
    {
      "AmountPaid": 92.0,
      "CardNumber": "",
      "CardType": "Cash",
      "PaymentMode": 1,
      "ReferenceID": ""
    }
  ],
  "OrderItems": [
    {
      "AlternateName": "",
      "Cost": 15.0,
      "DiscountAmount": 0.0,
      "ItemID": 0,
      "ItemName": "P1",
      "OrderDetailID": 1956104,
      "OrderDetailPackages": [
        {
          "AlternateName": "",
          "AlternativeName": "",
          "Cost": 0.0,
          "CurrentStock": 0.0,
          "Discount": 0.0,
          "DiscoutType": "",
          "ItemID": 175741,
          "ItemName": "I1",
          "Name": "I1",
          "PackageDetailID": 0,
          "PackageID": 0,
          "Price": 20.0,
          "Quantity": 2.0,
          "StatusID": 1
        }
      ],
      "OrderID": 639,
      "PackageID": 3246,
      "Price": 80.0,
      "Quantity": 1.0
    }
  ]
}
```

### Field Descriptions

#### Root Level Fields
- **OrderID** (required): External order identifier
- **AmountDiscount** (optional): Total discount amount
- **AmountPaid** (required): Total amount paid (string or number)
- **AmountTotal** (required): Subtotal before tax
- **BalanceAmount** (optional): Remaining balance
- **GrandTotal** (required): Total including tax
- **Tax** (optional): Tax amount
- **TaxPercent** (optional): Tax percentage
- **OrderStatus** (optional): Order status code
- **PaymentMode** (optional): Payment mode identifier

#### OrderItems Array
Each order item contains:
- **ItemID** (optional): Product ID (if it's an Odoo product ID)
- **ItemName** (required): Product name (used to find product if ItemID is 0)
- **Price** (required): Unit price
- **Quantity** (required): Quantity ordered
- **DiscountAmount** (optional): Discount amount for this item
- **Cost** (optional): Cost of the item
- **PackageID** (optional): Package identifier
- **OrderDetailPackages** (optional): Array of component items that need to be consumed from inventory

#### OrderDetailPackages Array
Component items within an order item:
- **ItemID** (optional): Component product ID
- **ItemName** (optional): Component product name
- **Quantity** (required): Quantity to consume
- **Price** (optional): Component price
- **Cost** (optional): Component cost

#### CheckoutDetails Array
Payment information:
- **AmountPaid** (required): Payment amount
- **CardType** (optional): Payment type (e.g., "Cash", "Card")
- **PaymentMode** (optional): Payment mode identifier
- **ReferenceID** (optional): Payment reference
- **CardNumber** (optional): Card number (if applicable)

### Data Validation

The webhook performs the following validations:
1. **Total Consistency**: Validates that calculated totals match provided totals
2. **Payment Consistency**: Ensures payment amounts match AmountPaid
3. **Product Existence**: Verifies all products exist in Odoo
4. **Payment Method**: Validates payment methods are available

### Response Example

#### Success Response
```json
{
  "status": "success",
  "data": {
    "id": 123,
    "name": "Order 00001",
    "pos_reference": "00001",
    "amount_total": 92.0,
    "amount_paid": 92.0,
    "amount_tax": 12.0,
    "state": "paid",
    "date_order": "2024-01-15 10:30:00",
    "external_order_id": 639
  },
  "error": null,
  "count": 1
}
```

#### Error Response
```json
{
  "status": "error",
  "data": null,
  "error": "Data inconsistency: Calculated total (92.0) does not match GrandTotal (90.0)",
  "count": 0
}
```

### Error Codes

| Status Code | Description |
|-------------|-------------|
| 400 | Bad Request - Invalid data or missing required fields |
| 401 | Unauthorized - Invalid or missing API key |
| 404 | Not Found - Product or payment method not found |
| 500 | Internal Server Error - Server-side error |

### Common Errors

#### Product Not Found
```json
{
  "status": "error",
  "data": null,
  "error": "Product not found: ItemName=\"P1\", ItemID=0",
  "count": 0
}
```

**Solution:** Ensure products exist in Odoo with matching names or IDs, and are available in POS.

#### No Open POS Session
```json
{
  "status": "error",
  "data": null,
  "error": "No open POS session found. Please open a POS session first.",
  "count": 0
}
```

**Solution:** Open a POS session in Odoo before sending webhook requests.

#### Data Inconsistency
```json
{
  "status": "error",
  "data": null,
  "error": "Data inconsistency: Calculated total (92.0) does not match GrandTotal (90.0)",
  "count": 0
}
```

**Solution:** Verify that AmountTotal, Tax, and GrandTotal are correctly calculated in your system.

### Usage Example

#### cURL Example
```bash
curl -X POST "http://your-odoo-instance.com/api/v1/webhook/pos-order" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "OrderID": 639,
    "AmountPaid": "92.0",
    "AmountTotal": 80.0,
    "GrandTotal": 92.0,
    "Tax": 12.0,
    "TaxPercent": 15.0,
    "OrderItems": [
      {
        "ItemName": "P1",
        "Price": 80.0,
        "Quantity": 1.0
      }
    ],
    "CheckoutDetails": [
      {
        "AmountPaid": 92.0,
        "CardType": "Cash",
        "PaymentMode": 1
      }
    ]
  }'
```

#### Python Example
```python
import requests
import json

url = "http://your-odoo-instance.com/api/v1/webhook/pos-order"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key"
}

data = {
    "OrderID": 639,
    "AmountPaid": "92.0",
    "AmountTotal": 80.0,
    "GrandTotal": 92.0,
    "Tax": 12.0,
    "TaxPercent": 15.0,
    "OrderItems": [
        {
            "ItemName": "P1",
            "Price": 80.0,
            "Quantity": 1.0,
            "OrderDetailPackages": [
                {
                    "ItemName": "I1",
                    "Quantity": 2.0,
                    "Price": 20.0
                }
            ]
        }
    ],
    "CheckoutDetails": [
        {
            "AmountPaid": 92.0,
            "CardType": "Cash",
            "PaymentMode": 1
        }
    ]
}

response = requests.post(url, headers=headers, data=json.dumps(data))
result = response.json()

if result['status'] == 'success':
    print(f"Order created: {result['data']['name']}")
else:
    print(f"Error: {result['error']}")
```

### Notes

1. **Product Matching**: Products are matched by:
   - ItemID (if > 0 and exists in Odoo)
   - ItemName (exact match first, then case-insensitive)

2. **Payment Methods**: Payment methods are matched by:
   - CardType name (e.g., "Cash")
   - PaymentMode (1 = Cash by default)
   - Falls back to first available payment method

3. **Inventory Consumption**: OrderDetailPackages are logged but not automatically consumed. If you need automatic consumption, you may need to extend the webhook to create additional order lines or stock moves.

4. **Tax Calculation**: Taxes are calculated based on product tax settings and fiscal position. The TaxPercent in the request is used for validation only.

5. **Order Confirmation**: Orders are automatically confirmed (marked as paid) and inventory consumption is generated via `_create_order_picking()`.

## Support

For technical support or questions:
1. Check the module README.md
2. Review Odoo logs for errors
3. Contact your system administrator

