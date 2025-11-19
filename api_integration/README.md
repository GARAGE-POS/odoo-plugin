# API Integration Module

Odoo module providing REST API endpoints to push data for Unit of Measures, Products, and Vendors.

## Features

- **RESTful API Endpoints**: Clean, standardized REST API
- **JSON Format**: All responses in JSON format
- **API Key Authentication**: Secure API key-based authentication
- **Comprehensive Data**: Full product, vendor, and UoM information
- **Error Handling**: Proper error responses and logging
- **Documentation**: Complete API documentation with examples

## Installation

1. Copy the `api_integration` folder to your Odoo `custom_addons` directory
2. Update the apps list in Odoo
3. Install the "API Integration" module
4. Go to **Settings → API Configuration** to create an API key

## Configuration

### Creating an API Key

1. Navigate to **Settings → API Configuration**
2. Click **Create** to create a new API configuration
3. Enter a name and description
4. The API key will be automatically generated
5. Copy and save the API key securely

### Regenerating API Key

If you need to regenerate an API key:
1. Open the API configuration
2. Click **Regenerate Key** button
3. Save the new key

## API Endpoints

### Base URL
```
http://your-odoo-instance.com
```

### Authentication
All endpoints require an `api_key` parameter in the query string.

### Endpoints

#### 1. Health Check
**GET** `/api/v1/health`

Check if the API is running.

**Response:**
```json
{
  "status": "success",
  "data": {
    "message": "API is running",
    "version": "1.0"
  },
  "error": null,
  "count": 1
}
```

#### 2. Get Unit of Measures
**GET** `/api/v1/uom?api_key=YOUR_API_KEY`

**Parameters:**
- `api_key` (required): Your API key
- `limit` (optional): Maximum number of records (default: all)
- `offset` (optional): Number of records to skip (default: 0)

**Example:**
```
GET /api/v1/uom?api_key=abc123&limit=10&offset=0
```

**Response:**
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
    }
  ],
  "error": null,
  "count": 1
}
```

#### 3. Get Products
**GET** `/api/v1/products?api_key=YOUR_API_KEY`

**Parameters:**
- `api_key` (required): Your API key
- `limit` (optional): Maximum number of records (default: all)
- `offset` (optional): Number of records to skip (default: 0)
- `active_only` (optional): Return only active products (default: true)

**Example:**
```
GET /api/v1/products?api_key=abc123&limit=50&offset=0&active_only=true
```

**Response:**
See [Products JSON Format](#products-json-format) section below.

#### 4. Get Vendors
**GET** `/api/v1/vendors?api_key=YOUR_API_KEY`

**Parameters:**
- `api_key` (required): Your API key
- `limit` (optional): Maximum number of records (default: all)
- `offset` (optional): Number of records to skip (default: 0)
- `active_only` (optional): Return only active vendors (default: true)

**Example:**
```
GET /api/v1/vendors?api_key=abc123&limit=20&offset=0&active_only=true
```

**Response:**
See [Vendors JSON Format](#vendors-json-format) section below.

#### 5. Create POS Order
**POST** `/api/v1/pos/orders`

Create a Point of Sale order from external API.

**Parameters:**
- `api_key` (required): Your API key
- `session_id` (required): ID of an open POS session
- `lines` (required): Array of order line items
- `payments` (required): Array of payment methods and amounts
- `partner_id` (optional): Customer/partner ID
- `date_order` (optional): Order date/time
- `note` (optional): Order notes
- `to_invoice` (optional): Whether to create invoice (default: false)

**Example:**
```json
POST /api/v1/pos/orders
{
  "api_key": "abc123",
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
  ]
}
```

**Response:**
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

For complete documentation, see [POS_ORDER_API.md](POS_ORDER_API.md).

## JSON Format Documentation

### Standard Response Format

All API responses follow this structure:

```json
{
  "status": "success" | "error",
  "data": <response_data>,
  "error": <error_message_or_null>,
  "count": <number_of_items>
}
```

### Unit of Measures JSON Format

```json
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
}
```

**Field Descriptions:**
- `id`: Unique identifier
- `name`: Unit of measure name
- `category_id`: UoM category (id and name)
- `factor`: Conversion factor to reference unit
- `factor_inv`: Inverse conversion factor
- `rounding`: Rounding precision
- `uom_type`: Type (reference, bigger, smaller)
- `active`: Whether the UoM is active

### Products JSON Format

```json
{
  "id": 1,
  "name": "Product Name",
  "description": "Product description",
  "description_purchase": "Purchase description",
  "description_sale": "Sales description",
  "type": "storable",
  "categ_id": {
    "id": 1,
    "name": "Category Name"
  },
  "categories": [
    {
      "id": 1,
      "name": "Category Name"
    }
  ],
  "list_price": 100.0,
  "standard_price": 80.0,
  "uom_id": {
    "id": 1,
    "name": "Units"
  },
  "uom_po_id": {
    "id": 1,
    "name": "Units"
  },
  "barcode": "1234567890123",
  "default_code": "PROD-001",
  "sale_ok": true,
  "purchase_ok": true,
  "active": true,
  "weight": 1.5,
  "volume": 0.5,
  "image_url": "/web/image/product.template/1/image_1920",
  "variants": [
    {
      "id": 1,
      "default_code": "PROD-001-V1",
      "barcode": "1234567890124",
      "weight": 1.5,
      "volume": 0.5
    }
  ],
  "suppliers": [
    {
      "id": 1,
      "name": "Vendor Name",
      "price": 75.0,
      "currency_id": {
        "id": 1,
        "name": "USD"
      },
      "min_qty": 1.0,
      "delay": 7
    }
  ]
}
```

**Field Descriptions:**
- `id`: Product template ID
- `name`: Product name
- `description`: Internal description
- `description_purchase`: Purchase description
- `description_sale`: Sales description
- `type`: Product type (consu, service, storable)
- `categ_id`: Main category
- `categories`: All categories (array)
- `list_price`: Sale price
- `standard_price`: Cost price
- `uom_id`: Unit of measure for sales
- `uom_po_id`: Unit of measure for purchases
- `barcode`: Product barcode
- `default_code`: Internal reference
- `sale_ok`: Can be sold
- `purchase_ok`: Can be purchased
- `active`: Whether product is active
- `weight`: Product weight
- `volume`: Product volume
- `image_url`: URL to product image (if available)
- `variants`: Product variants array
- `suppliers`: Supplier information array

### Vendors JSON Format

```json
{
  "id": 1,
  "name": "Vendor Company Name",
  "display_name": "Vendor Company Name",
  "ref": "VEND-001",
  "vat": "VAT123456",
  "email": "vendor@example.com",
  "phone": "+1234567890",
  "mobile": "+1234567891",
  "website": "https://vendor.com",
  "street": "123 Main St",
  "street2": "Suite 100",
  "city": "City Name",
  "state_id": {
    "id": 1,
    "name": "State Name",
    "code": "ST"
  },
  "zip": "12345",
  "country_id": {
    "id": 1,
    "name": "Country Name",
    "code": "US"
  },
  "supplier_rank": 1,
  "active": true,
  "image_url": "/web/image/res.partner/1/image_1920",
  "products": [
    {
      "id": 1,
      "name": "Product Name",
      "product_code": "VEND-PROD-001",
      "price": 75.0,
      "min_qty": 1.0,
      "delay": 7
    }
  ]
}
```

**Field Descriptions:**
- `id`: Vendor partner ID
- `name`: Vendor name
- `display_name`: Full display name
- `ref`: Internal reference
- `vat`: VAT number
- `email`: Email address
- `phone`: Phone number
- `mobile`: Mobile number
- `website`: Website URL
- `street`: Street address
- `street2`: Additional address line
- `city`: City
- `state_id`: State/province (id, name, code)
- `zip`: ZIP/postal code
- `country_id`: Country (id, name, code)
- `supplier_rank`: Supplier ranking (higher = preferred)
- `active`: Whether vendor is active
- `image_url`: URL to vendor logo (if available)
- `products`: Products supplied by this vendor

## Error Responses

### 401 Unauthorized
```json
{
  "status": "error",
  "data": null,
  "error": "Invalid or missing API key",
  "count": 0
}
```

### 500 Internal Server Error
```json
{
  "status": "error",
  "data": null,
  "error": "Internal server error: <error details>",
  "count": 0
}
```

## Usage Examples

### cURL Examples

#### Get Unit of Measures
```bash
curl "http://your-odoo-instance.com/api/v1/uom?api_key=YOUR_API_KEY"
```

#### Get Products (with pagination)
```bash
curl "http://your-odoo-instance.com/api/v1/products?api_key=YOUR_API_KEY&limit=10&offset=0"
```

#### Get Vendors
```bash
curl "http://your-odoo-instance.com/api/v1/vendors?api_key=YOUR_API_KEY&active_only=true"
```

### Python Example

```python
import requests

API_BASE_URL = "http://your-odoo-instance.com"
API_KEY = "your-api-key-here"

# Get products
response = requests.get(
    f"{API_BASE_URL}/api/v1/products",
    params={
        "api_key": API_KEY,
        "limit": 50,
        "offset": 0,
        "active_only": "true"
    }
)

if response.status_code == 200:
    data = response.json()
    products = data.get("data", [])
    print(f"Retrieved {len(products)} products")
    for product in products:
        print(f"Product: {product['name']} - Price: {product['list_price']}")
else:
    print(f"Error: {response.status_code} - {response.json()}")
```

### JavaScript Example

```javascript
const API_BASE_URL = "http://your-odoo-instance.com";
const API_KEY = "your-api-key-here";

// Get vendors
fetch(`${API_BASE_URL}/api/v1/vendors?api_key=${API_KEY}&limit=20`)
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      const vendors = data.data;
      console.log(`Retrieved ${vendors.length} vendors`);
      vendors.forEach(vendor => {
        console.log(`Vendor: ${vendor.name} - Email: ${vendor.email}`);
      });
    } else {
      console.error('Error:', data.error);
    }
  })
  .catch(error => console.error('Request failed:', error));
```

## Security

- API keys are required for all endpoints
- API keys are stored securely in the database
- Only active API configurations can be used
- All API access is logged
- CORS is enabled for cross-origin requests

## Support

For issues or questions, please contact your system administrator or refer to the Odoo documentation.

## License

LGPL-3

