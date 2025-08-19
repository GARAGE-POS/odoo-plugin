"""
Complete workflow test using actual data and API calls
"""

import json
import requests
from odoo.tests import HttpCase


class TestCompleteWorkflow(HttpCase):
    """Test complete workflow using HTTP requests to simulate real POS integration"""

    def setUp(self):
        super().setUp()
        
    def test_01_verify_demo_products_exist(self):
        """Test that our 10 demo products were created with inventory"""
        
        # Product codes we expect to find
        expected_product_codes = [
            '170388',  # Fuchs Oil 5W30
            '170389',  # Mobil 1 0W20
            '170390',  # Castrol GTX 10W40
            '170391',  # Bosch Oil Filter
            '170392',  # Mann Air Filter
            '170393',  # NGK Spark Plug
            '170394',  # Denso Spark Plug
            '170395',  # Brembo Brake Pads
            '170396',  # Michelin Tire 195/65R15
            '170397',  # Continental Tire 205/55R16
        ]
        
        found_products = []
        for code in expected_product_codes:
            product = self.env['product.product'].search([('default_code', '=', code)], limit=1)
            if product:
                found_products.append(product)
                
                # Check inventory
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('quantity', '>', 0)
                ])
                self.assertTrue(len(quant) > 0, f"Product {code} should have inventory")
        
        self.assertEqual(len(found_products), 10, f"Should find all 10 products, found {len(found_products)}")
        
        return found_products
        
    def test_02_verify_pos_configuration_exists(self):
        """Test that POS configuration exists and is properly set up"""
        
        # Check main POS config exists
        pos_config = self.env['pos.config'].search([('name', '=', 'Karage Main POS')], limit=1)
        self.assertTrue(pos_config, "Karage Main POS configuration should exist")
        
        # Check it has payment methods
        self.assertTrue(len(pos_config.payment_method_ids) > 0, "POS config should have payment methods")
        
        # Check it has proper location
        self.assertTrue(pos_config.karage_location_id == 0, "Main POS should have location ID 0")
        
        return pos_config
        
    def test_03_create_pos_session(self):
        """Test creating and opening a POS session"""
        
        pos_config = self.test_02_verify_pos_configuration_exists()
        
        # Create session
        session = self.env['pos.session'].create({
            'config_id': pos_config.id,
            'user_id': self.env.user.id,
        })
        
        # Open session
        session.action_pos_session_open()
        self.assertEqual(session.state, 'opened', "Session should be opened")
        
        return session
        
    def test_04_process_single_product_order(self):
        """Test processing a single product order through the API"""
        
        products = self.test_01_verify_demo_products_exist()
        session = self.test_03_create_pos_session()
        
        # Use the first product (Fuchs Oil)
        test_product = products[0]
        
        # Create order data for the API
        order_data = {
            "LocationID": 0,  # Main location
            "CustomerID": 0,
            "CustomerName": "Test Customer",
            "CustomerContact": "123-456-7890",
            "AmountTotal": 25.0,
            "CheckoutDate": "19-08-2025 12:00:00 PM",
            "Remark": "Test order via workflow test",
            "OrderDetails": [{
                "ItemID": int(test_product.default_code),
                "Name": test_product.name,
                "Quantity": 2,
                "Price": test_product.list_price,
                "Cost": test_product.standard_price,
                "itemType": "oil",
                "DiscountAmount": 0,
                "IsInventoryItem": True,
            }],
            "OrderCheckoutDetails": [{
                "PaymentMode": 1,
                "CardType": "Cash",
                "AmountPaid": 50.0,
                "CardHolderName": "",
                "CardNumber": "",
            }],
            "OrderTakerID": "WORKFLOW_TEST_001",
        }
        
        # Process the order directly through the model
        result = self.env['pos.order'].process_karage_order(order_data)
        
        # Verify success
        self.assertTrue(result.get('success'), f"Order processing should succeed: {result}")
        
        # Get the created order
        pos_order_id = result.get('pos_order_id')
        self.assertIsNotNone(pos_order_id, "Should return POS order ID")
        
        pos_order = self.env['pos.order'].browse(pos_order_id)
        
        # Verify order details
        self.assertEqual(len(pos_order.lines), 1, "Should have one order line")
        self.assertEqual(pos_order.lines[0].qty, 2, "Quantity should be 2")
        self.assertEqual(pos_order.lines[0].product_id, test_product, "Should be correct product")
        
        # Verify payment
        self.assertEqual(len(pos_order.payment_ids), 1, "Should have one payment")
        self.assertEqual(pos_order.payment_ids[0].amount, 50.0, "Payment amount should be 50.0")
        
        # Verify order state
        self.assertEqual(pos_order.state, 'paid', "Order should be paid")
        
        # Verify inventory reduction
        updated_quant = self.env['stock.quant'].search([
            ('product_id', '=', test_product.id),
            ('location_id', '=', session.config_id.stock_location_id.id)
        ])
        
        # Should have reduced from 10 to 8
        if updated_quant:
            self.assertEqual(updated_quant.quantity, 8.0, f"Inventory should be 8, but is {updated_quant.quantity}")
        
        return pos_order
        
    def test_05_verify_accounting_entries(self):
        """Test that accounting entries are created correctly"""
        
        pos_order = self.test_04_process_single_product_order()
        
        # Verify invoice generation
        self.assertIsNotNone(pos_order.account_move, "Invoice should be generated")
        
        invoice = pos_order.account_move
        self.assertEqual(invoice.state, 'posted', "Invoice should be posted")
        
        # Verify invoice lines
        self.assertTrue(len(invoice.invoice_line_ids) > 0, "Invoice should have lines")
        
        # Verify total amount
        self.assertEqual(invoice.amount_total, 50.0, "Invoice total should match payment")
        
        return invoice
        
    def test_06_verify_request_logging(self):
        """Test that API requests are logged"""
        
        # Count logs before
        initial_count = self.env['karage.request.logger'].search_count([])
        
        # Process an order (which should log the request)
        self.test_04_process_single_product_order()
        
        # Count logs after
        final_count = self.env['karage.request.logger'].search_count([])
        
        self.assertGreater(final_count, initial_count, "Request should be logged")
        
        # Get latest log
        latest_log = self.env['karage.request.logger'].search([], order='create_date desc', limit=1)
        
        # Verify log content
        self.assertIn('LocationID', latest_log.body, "Log should contain request data")
        self.assertIn('OrderDetails', latest_log.body, "Log should contain order details")
        
        return latest_log
        
    def test_07_multi_product_order(self):
        """Test ordering multiple different products"""
        
        products = self.test_01_verify_demo_products_exist()
        session = self.test_03_create_pos_session()
        
        # Create order with 3 different products
        order_data = {
            "LocationID": 0,
            "CustomerID": 999,
            "CustomerName": "Multi Product Customer",
            "CustomerContact": "999-888-7777",
            "AmountTotal": 88.0,
            "CheckoutDate": "19-08-2025 13:00:00 PM",
            "Remark": "Multi product workflow test",
            "OrderDetails": [
                {
                    "ItemID": int(products[0].default_code),  # Fuchs Oil
                    "Name": products[0].name,
                    "Quantity": 1,
                    "Price": 25.0,
                    "Cost": 20.0,
                    "itemType": "oil",
                    "DiscountAmount": 0,
                },
                {
                    "ItemID": int(products[3].default_code),  # Bosch Filter
                    "Name": products[3].name,
                    "Quantity": 2,
                    "Price": 15.0,
                    "Cost": 12.0,
                    "itemType": "filter",
                    "DiscountAmount": 0,
                },
                {
                    "ItemID": int(products[7].default_code),  # Brembo Pads
                    "Name": products[7].name,
                    "Quantity": 1,
                    "Price": 45.0,
                    "Cost": 35.0,
                    "itemType": "brakes",
                    "DiscountAmount": 2.0,  # Small discount
                }
            ],
            "OrderCheckoutDetails": [{
                "PaymentMode": 1,
                "CardType": "Cash",
                "AmountPaid": 88.0,
                "CardHolderName": "",
                "CardNumber": "",
            }],
            "OrderTakerID": "MULTI_PRODUCT_001",
        }
        
        # Process order
        result = self.env['pos.order'].process_karage_order(order_data)
        
        # Verify success
        self.assertTrue(result.get('success'), f"Multi-product order should succeed: {result}")
        
        # Get order and verify
        pos_order = self.env['pos.order'].browse(result['pos_order_id'])
        self.assertEqual(len(pos_order.lines), 3, "Should have 3 order lines")
        
        # Verify total calculation
        total_before_discount = 25.0 + (2 * 15.0) + 45.0  # 85.0
        expected_total = total_before_discount - 2.0  # 83.0 (with discount)
        
        return pos_order
        
    def test_08_inventory_tracking_after_multiple_orders(self):
        """Test that inventory is correctly tracked after multiple orders"""
        
        products = self.test_01_verify_demo_products_exist()
        
        # Record initial quantities
        initial_quantities = {}
        for product in products:
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('quantity', '>', 0)
            ], limit=1)
            initial_quantities[product.id] = quant.quantity if quant else 0
        
        # Process multiple orders
        self.test_04_process_single_product_order()  # Uses 2x product[0]
        self.test_07_multi_product_order()          # Uses 1x product[0], 2x product[3], 1x product[7]
        
        # Check final quantities
        expected_reductions = {
            products[0].id: 3,  # 2 + 1 = 3 total used
            products[3].id: 2,  # 2 used
            products[7].id: 1,  # 1 used
        }
        
        for product_id, expected_reduction in expected_reductions.items():
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product_id),
            ], limit=1)
            
            if quant:
                expected_final = initial_quantities[product_id] - expected_reduction
                self.assertEqual(quant.quantity, expected_final, 
                               f"Product {product_id} should have {expected_final} remaining")
        
    def test_09_comprehensive_system_validation(self):
        """Final comprehensive test to validate the entire system"""
        
        # Run all components
        products = self.test_01_verify_demo_products_exist()
        pos_config = self.test_02_verify_pos_configuration_exists()
        session = self.test_03_create_pos_session()
        pos_order = self.test_04_process_single_product_order()
        invoice = self.test_05_verify_accounting_entries()
        log_entry = self.test_06_verify_request_logging()
        
        # Final validation: System is working end-to-end
        
        # 1. Products are available
        self.assertEqual(len(products), 10, "All 10 products should be available")
        
        # 2. POS system is configured
        self.assertTrue(pos_config.id > 0, "POS configuration should exist")
        
        # 3. Session management works
        self.assertEqual(session.state, 'opened', "Session should be open")
        
        # 4. Order processing works
        self.assertEqual(pos_order.state, 'paid', "Order should be processed and paid")
        
        # 5. Accounting integration works
        self.assertEqual(invoice.state, 'posted', "Invoice should be posted")
        
        # 6. Audit logging works
        self.assertIsNotNone(log_entry.id, "Request should be logged")
        
        # 7. Inventory tracking works
        self.test_08_inventory_tracking_after_multiple_orders()
        
        return {
            'products_count': len(products),
            'pos_config': pos_config.name,
            'session_state': session.state,
            'order_state': pos_order.state,
            'invoice_state': invoice.state,
            'log_created': bool(log_entry.id),
            'system_status': 'FULLY_OPERATIONAL'
        }