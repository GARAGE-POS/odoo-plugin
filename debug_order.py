#!/usr/bin/env python3

import sys
sys.path.append('/usr/lib/python3/dist-packages')
import odoo
from odoo import api, SUPERUSER_ID
from odoo.tools import config

# Initialize Odoo configuration
config.parse_config(['--addons-path=/mnt/extra-addons', '--database=odoo'])

try:
    # Create environment
    registry = odoo.registry('odoo')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Get a test product
        test_product = env['product.product'].search([('default_code', '=', '170388')], limit=1)
        
        order_data = {
            'LocationID': 0,
            'CustomerName': 'Debug Test Customer',
            'CustomerContact': '123-456-7890',
            'AmountTotal': 25.0,
            'CheckoutDate': '19-08-2025 12:00:00 PM',
            'Remark': 'Debug test',
            'OrderDetails': [{
                'ItemID': 170388,
                'Name': 'Fuchs Oil 5W30 Syn SN',
                'Quantity': 1,
                'Price': 25.0,
                'Cost': 20.0,
                'itemType': 'oil',
                'DiscountAmount': 0,
                'IsInventoryItem': True,
            }],
            'OrderCheckoutDetails': [{
                'PaymentMode': 1,
                'CardType': 'Cash',
                'AmountPaid': 25.0,
                'CardHolderName': '',
                'CardNumber': '',
            }],
            'OrderTakerID': 'DEBUG_TEST',
        }
        
        print(f"Order data keys: {order_data.keys()}")
        print(f"LocationID value: {order_data.get('LocationID')}")
        print(f"LocationID type: {type(order_data.get('LocationID'))}")
        print(f"OrderDetails: {len(order_data.get('OrderDetails', []))} items")
        
        # Test validation manually
        pos_order_model = env['pos.order']
        try:
            pos_order_model._validate_karage_order_data(order_data)
            print("✅ Validation passed")
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            
        # Try processing
        try:
            result = pos_order_model.process_karage_order(order_data)
            print(f"Process result: {result}")
        except Exception as e:
            print(f"Processing failed: {e}")
            import traceback
            traceback.print_exc()
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()