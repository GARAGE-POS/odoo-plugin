# External Order Sync Guide

This guide explains how to set up automatic order synchronization from external systems to Odoo POS.

## Overview

The External Order Sync feature allows you to:
- Automatically fetch orders from an external system via API
- Create POS orders in Odoo without manual intervention
- Automatically confirm orders with payments
- Generate inventory consumption (pickings)
- Run on a scheduled basis (cron job)

**No POS session needs to be manually opened** - the system will automatically create and manage sessions.

## Setup Instructions

### Step 1: Configure External Order Sync

1. Go to **Settings → External Order Sync**
2. Click **Create** to create a new sync configuration
3. Fill in the following fields:

   - **Name**: A descriptive name (e.g., "Main Store Orders")
   - **Active**: Enable/disable this sync configuration
   - **External API URL**: The URL of your external system's API endpoint
     - Example: `https://external-system.com/api/orders`
     - Should return JSON array of orders in the format specified below
   - **External API Key**: API key for authenticating with external system
   - **POS Configuration**: Select which POS configuration to use for orders
   - **Auto Create Session**: Enable to automatically create POS sessions if none is open
   - **Sync Interval**: Interval in minutes between syncs (default: 15 minutes)

4. Click **Save**

### Step 2: Test the Configuration

1. Click **Sync Now** button to test the sync immediately
2. Check the **Sync Status** tab to see the result
3. Verify that orders are created in **Point of Sale → Orders**

### Step 3: Verify Scheduled Action

The system automatically creates a scheduled action (cron job) that runs every 15 minutes.

To verify or modify:
1. Go to **Settings → Technical → Automation → Scheduled Actions**
2. Find "Sync External Orders"
3. You can modify the interval or activate/deactivate it

## External API Format

Your external system API should return orders in the following JSON format:

### Single Order Format

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
      "ItemID": 0,
      "ItemName": "Product Name",
      "Price": 80.0,
      "Quantity": 1.0,
      "DiscountAmount": 0.0,
      "OrderDetailPackages": [
        {
          "ItemID": 175741,
          "ItemName": "Component Item",
          "Price": 20.0,
          "Quantity": 2.0
        }
      ]
    }
  ]
}
```

### Multiple Orders Format

Your API can return an array of orders:

```json
[
  {
    "OrderID": 639,
    "OrderItems": [...],
    "CheckoutDetails": [...]
  },
  {
    "OrderID": 640,
    "OrderItems": [...],
    "CheckoutDetails": [...]
  }
]
```

### API Response Options

The system supports multiple response formats:

1. **Array of orders**: `[{order1}, {order2}]`
2. **Object with orders array**: `{"orders": [{order1}, {order2}]}`
3. **Single order object**: `{order1}`

## Required Fields

### Minimum Required Fields

- `OrderID`: Unique order identifier
- `AmountPaid`: Total amount paid (string or number)
- `AmountTotal`: Subtotal before tax
- `GrandTotal`: Total including tax
- `OrderItems`: Array of order items
  - `ItemName`: Product name (must exist in Odoo)
  - `Price`: Unit price
  - `Quantity`: Quantity ordered
- `CheckoutDetails`: Array of payment details
  - `AmountPaid`: Payment amount
  - `CardType`: Payment type (e.g., "Cash", "Card")
  - `PaymentMode`: Payment mode identifier

## Product Matching

Products are matched by:
1. **ItemID** (if > 0 and exists as Odoo product ID)
2. **ItemName** (exact match first, then case-insensitive)

**Requirements:**
- Product must exist in Odoo
- Product must be `sale_ok = True`
- Product must be `available_in_pos = True`

## Payment Method Matching

Payment methods are matched by:
1. **CardType** name (e.g., "Cash" matches cash payment methods)
2. **PaymentMode** (1 = Cash by default)
3. Falls back to first available payment method

## Automatic Session Management

If **Auto Create Session** is enabled:
- System automatically creates a POS session if none is open
- Session is created with system user (admin)
- Session is automatically opened
- Orders are created in this session

If **Auto Create Session** is disabled:
- System requires an existing open POS session
- If no session is found, sync will fail with error

## How It Works

1. **Scheduled Action** runs every 15 minutes (configurable)
2. **Fetches Orders** from external API
3. **For each order:**
   - Gets or creates POS session
   - Finds products by name or ID
   - Creates POS order with lines and payments
   - Confirms order (marks as paid)
   - Generates inventory consumption (picking)
4. **Updates sync status** with results

## Monitoring

### Check Sync Status

1. Go to **Settings → External Order Sync**
2. View **Last Sync Date**, **Last Sync Status**, and **Last Sync Message**

### Status Values

- **Success**: All orders processed successfully
- **No Orders**: No orders found to sync
- **Error**: Error occurred during sync

### Check Logs

Check Odoo logs for detailed information:
- Location: `odoo-community.log`
- Search for: "External Order Sync" or "sync_orders"

## Troubleshooting

### Issue: "No open POS session found"

**Solution:**
- Enable "Auto Create Session" in sync configuration
- Or manually open a POS session

### Issue: "Product not found"

**Solution:**
- Verify product name matches exactly in Odoo
- Ensure product is available in POS
- Check product is active and can be sold

### Issue: "Failed to fetch orders from external system"

**Solution:**
- Verify External API URL is correct
- Check External API Key is valid
- Verify external system is accessible
- Check network connectivity
- Review external API response format

### Issue: Orders not being created

**Solution:**
- Check sync is active
- Verify scheduled action is active
- Check last sync status and message
- Review Odoo logs for errors
- Test with "Sync Now" button

### Issue: Sync not running automatically

**Solution:**
- Go to **Settings → Technical → Automation → Scheduled Actions**
- Find "Sync External Orders"
- Verify it's active
- Check next run date
- Manually trigger if needed

## API Authentication

The system sends the API key in the request header:

```
Authorization: Bearer YOUR_API_KEY
```

Or alternatively (depending on your external system):

```
X-API-Key: YOUR_API_KEY
```

You can modify the authentication method in the `_fetch_orders_from_external` method if needed.

## Advanced Configuration

### Custom API Parameters

You can modify the `_fetch_orders_from_external` method to:
- Add custom query parameters
- Filter orders by date range
- Add custom headers
- Handle pagination

### Custom Order Processing

You can extend the `_process_external_order` method to:
- Add custom validation
- Handle special product types
- Add custom order notes
- Link to customers/partners

## Best Practices

1. **Start with Manual Sync**: Use "Sync Now" to test before enabling automatic sync
2. **Monitor First Runs**: Check logs and status after first few automatic syncs
3. **Set Appropriate Interval**: Don't sync too frequently (15 minutes is recommended)
4. **Handle Errors**: Monitor error status and fix issues promptly
5. **Product Naming**: Use consistent product names between systems
6. **API Rate Limits**: Be aware of external API rate limits

## Support

For issues:
1. Check sync status and last sync message
2. Review Odoo logs
3. Test with "Sync Now" button
4. Verify external API is accessible
5. Check product and payment method configurations

