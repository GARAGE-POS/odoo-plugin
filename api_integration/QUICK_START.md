# API Integration - Quick Start Guide

## Installation

1. **Copy the module** to your Odoo `custom_addons` directory
2. **Update Apps List**: Go to Apps → Update Apps List
3. **Install Module**: Search for "API Integration" and click Install

## Getting Your API Key

1. **Navigate to Settings**: Settings → API Configuration
2. **Create Configuration**: Click Create button
3. **Fill Details**:
   - Name: e.g., "Production API Key"
   - Description: Optional description
   - Active: Check this box
4. **Save**: The API key will be automatically generated
5. **Copy API Key**: Copy the generated key (you won't be able to see it again without regenerating)

## Testing the API

### 1. Health Check

Test if the API is working:

```bash
curl "http://your-odoo-instance.com/api/v1/health"
```

Expected response:
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

### 2. Get Unit of Measures

```bash
curl "http://your-odoo-instance.com/api/v1/uom?api_key=YOUR_API_KEY"
```

### 3. Get Products

```bash
curl "http://your-odoo-instance.com/api/v1/products?api_key=YOUR_API_KEY&limit=5"
```

### 4. Get Vendors

```bash
curl "http://your-odoo-instance.com/api/v1/vendors?api_key=YOUR_API_KEY&limit=5"
```

## Common Use Cases

### Get All Active Products

```bash
curl "http://your-odoo-instance.com/api/v1/products?api_key=YOUR_API_KEY&active_only=true"
```

### Get Products with Pagination

```bash
# First 50 products
curl "http://your-odoo-instance.com/api/v1/products?api_key=YOUR_API_KEY&limit=50&offset=0"

# Next 50 products
curl "http://your-odoo-instance.com/api/v1/products?api_key=YOUR_API_KEY&limit=50&offset=50"
```

### Get All Vendors

```bash
curl "http://your-odoo-instance.com/api/v1/vendors?api_key=YOUR_API_KEY&active_only=true"
```

## Python Integration Example

```python
import requests

# Configuration
ODOO_URL = "http://your-odoo-instance.com"
API_KEY = "your-api-key-here"

# Get products
def get_products(limit=50, offset=0):
    url = f"{ODOO_URL}/api/v1/products"
    params = {
        "api_key": API_KEY,
        "limit": limit,
        "offset": offset,
        "active_only": "true"
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if data["status"] == "success":
            return data["data"]
        else:
            print(f"Error: {data['error']}")
            return []
    else:
        print(f"HTTP Error: {response.status_code}")
        return []

# Usage
products = get_products(limit=10)
for product in products:
    print(f"{product['name']}: ${product['list_price']}")
```

## JavaScript Integration Example

```javascript
const ODOO_URL = "http://your-odoo-instance.com";
const API_KEY = "your-api-key-here";

// Get vendors
async function getVendors(limit = 20) {
    const url = `${ODOO_URL}/api/v1/vendors`;
    const params = new URLSearchParams({
        api_key: API_KEY,
        limit: limit,
        active_only: "true"
    });
    
    try {
        const response = await fetch(`${url}?${params}`);
        const data = await response.json();
        
        if (data.status === "success") {
            return data.data;
        } else {
            console.error("Error:", data.error);
            return [];
        }
    } catch (error) {
        console.error("Request failed:", error);
        return [];
    }
}

// Usage
getVendors(10).then(vendors => {
    vendors.forEach(vendor => {
        console.log(`${vendor.name}: ${vendor.email}`);
    });
});
```

## Troubleshooting

### Error: "Invalid or missing API key"

- Check that you're including the `api_key` parameter
- Verify the API key is correct
- Ensure the API configuration is active in Odoo

### Error: "Internal server error"

- Check Odoo server logs
- Verify the module is properly installed
- Ensure required dependencies are installed

### No data returned

- Check that you have products/vendors/UoM in your Odoo database
- Try without the `active_only` parameter
- Check pagination parameters (limit/offset)

## Next Steps

- Read the full [README.md](README.md) for detailed information
- Check [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete API reference
- Review JSON format examples in the documentation

## Support

For issues or questions:
1. Check the documentation files
2. Review Odoo logs
3. Contact your system administrator


