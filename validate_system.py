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
        
        # Product data
        products_data = [
            {'name': 'Fuchs Oil 5W30 Syn SN', 'code': '170388', 'price': 25.0, 'cost': 20.0},
            {'name': 'Mobil 1 0W20 Full Synthetic', 'code': '170389', 'price': 30.0, 'cost': 24.0},
            {'name': 'Castrol GTX 10W40', 'code': '170390', 'price': 22.0, 'cost': 18.0},
            {'name': 'Bosch Oil Filter', 'code': '170391', 'price': 15.0, 'cost': 12.0},
            {'name': 'Mann Air Filter', 'code': '170392', 'price': 18.0, 'cost': 14.0},
            {'name': 'NGK Spark Plug', 'code': '170393', 'price': 8.0, 'cost': 6.0},
            {'name': 'Denso Spark Plug', 'code': '170394', 'price': 10.0, 'cost': 7.5},
            {'name': 'Brembo Brake Pads', 'code': '170395', 'price': 45.0, 'cost': 35.0},
            {'name': 'Michelin Tire 195/65R15', 'code': '170396', 'price': 85.0, 'cost': 65.0},
            {'name': 'Continental Tire 205/55R16', 'code': '170397', 'price': 95.0, 'cost': 75.0},
        ]
        
        created_products = []
        for product_data in products_data:
            # Check if product exists
            existing = env['product.product'].search([('default_code', '=', product_data['code'])], limit=1)
            if existing:
                print(f'Product {product_data["code"]} already exists: {existing.name}')
                product = existing
            else:
                print(f'Creating product: {product_data["name"]}')
                product = env['product.product'].create({
                    'name': product_data['name'],
                    'default_code': product_data['code'],
                    'type': 'consu',  # Consumable - the available type in this Odoo version
                    'list_price': product_data['price'],
                    'standard_price': product_data['cost'],
                    'available_in_pos': True,
                })
            
            created_products.append(product)
        
        # Commit the transaction
        cr.commit()
        
        print(f'\n✅ Successfully created {len(created_products)} products')
        
        # Verify final state
        all_products = env['product.product'].search([('default_code', 'like', '1703%')])
        print(f'\nFinal verification: {len(all_products)} Karage products in system')
        for product in all_products:
            print(f'  - {product.default_code}: {product.name} (${product.list_price})')
        
        # Now let's test the order processing workflow
        print(f'\n🧪 Testing order processing workflow...')
        if all_products:
            test_product = all_products[0]
            order_data = {
                'LocationID': 0,
                'CustomerName': 'System Test Customer',
                'CustomerContact': '123-456-7890',
                'AmountTotal': test_product.list_price,
                'CheckoutDate': '19-08-2025 12:00:00 PM',
                'Remark': 'System validation test',
                'OrderDetails': [{
                    'ItemID': int(test_product.default_code),
                    'Name': test_product.name,
                    'Quantity': 1,
                    'Price': test_product.list_price,
                    'Cost': test_product.standard_price,
                    'itemType': 'test',
                    'DiscountAmount': 0,
                    'IsInventoryItem': True,
                }],
                'OrderCheckoutDetails': [{
                    'PaymentMode': 1,
                    'CardType': 'Cash',
                    'AmountPaid': test_product.list_price,
                    'CardHolderName': '',
                    'CardNumber': '',
                }],
                'OrderTakerID': 'SYSTEM_VALIDATION',
            }
            
            try:
                # First check if we can find POS configuration
                pos_config = env['pos.config'].get_config_for_location(0)
                print(f'✅ POS Configuration found: {pos_config.name}')
                
                # Test the order processing
                result = env['pos.order'].process_karage_order(order_data)
                if result.get('success'):
                    pos_order_id = result.get('pos_order_id')
                    pos_order = env['pos.order'].browse(pos_order_id)
                    print(f'✅ Order processing successful!')
                    print(f'  - Order ID: {pos_order_id}')
                    print(f'  - Order Name: {pos_order.name}')
                    print(f'  - Order State: {pos_order.state}')
                    print(f'  - Order Lines: {len(pos_order.lines)}')
                    print(f'  - Total Amount: ${pos_order.amount_total}')
                    if pos_order.account_move:
                        print(f'  - Invoice: {pos_order.account_move.name} ({pos_order.account_move.state})')
                    else:
                        print(f'  - Invoice: Not generated')
                else:
                    print(f'❌ Order processing failed: {result.get("error")}')
                    
            except Exception as e:
                print(f'❌ Order processing exception: {e}')
                import traceback
                traceback.print_exc()
        
        print(f'\n🎯 System validation complete!')
        print(f'📊 Summary:')
        print(f'   - Products created: {len(all_products)}')
        try:
            print(f'   - Order processing: {"Working" if result.get("success") else "Failed"}')
            print(f'   - System status: {"OPERATIONAL" if result.get("success") else "NEEDS ATTENTION"}')
        except:
            print(f'   - Order processing: Failed to test')
            print(f'   - System status: NEEDS ATTENTION')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()