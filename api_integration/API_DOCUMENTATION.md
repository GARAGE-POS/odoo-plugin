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

## Support

For technical support or questions:
1. Check the module README.md
2. Review Odoo logs for errors
3. Contact your system administrator

