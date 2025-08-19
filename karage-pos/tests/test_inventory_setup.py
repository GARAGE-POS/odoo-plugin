"""
Test-Driven Development: Inventory Setup and Order Processing Tests

This module implements a test-driven approach for the Karage POS integration:
1. Create 10 test products with 10 items each in inventory
2. Test complete order workflow from API to accounting/inventory
3. Verify all system interactions work as expected
"""

import json
from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestInventorySetupAndWorkflow(TransactionCase):
    """Test complete workflow with proper inventory setup"""

    def setUp(self):
        super().setUp()
        
        # Create test data for comprehensive workflow testing
        self.company = self.env.company
        
        # Create test location for Karage POS
        self.test_location = self.env['stock.location'].create({
            'name': 'Karage Test Location',
            'usage': 'internal',
            'company_id': self.company.id,
        })
        
        # Create test payment methods
        self.cash_journal = self.env['account.journal'].create({
            'name': 'Test Cash Journal',
            'code': 'TCJ1',
            'type': 'cash',
            'company_id': self.company.id,
        })
        
        self.payment_method_cash = self.env['pos.payment.method'].create({
            'name': 'Test Cash',
            'is_cash_count': True,
            'cash_journal_id': self.cash_journal.id,
            'company_id': self.company.id,
        })
        
        # Create test POS configuration
        self.pos_config = self.env['pos.config'].create({
            'name': 'Test Karage POS',
            'location_id': self.test_location.id,
            'payment_method_ids': [(6, 0, [self.payment_method_cash.id])],
            'company_id': self.company.id,
            'karage_location_id': 404,  # Test LocationID
        })
        
        # Create test customer
        self.test_customer = self.env['res.partner'].create({
            'name': 'Test Customer',
            'is_company': False,
            'customer_rank': 1,
        })
        
    def test_01_create_test_products_with_inventory(self):
        """Test 1: Create 10 products with 10 items each in inventory"""
        
        # Test product data - realistic automotive products
        test_products_data = [
            {'name': 'Fuchs Oil 5W30 Syn SN', 'item_id': 170388, 'price': 25.0, 'cost': 20.0, 'category': 'oil'},
            {'name': 'Mobil 1 0W20 Full Synthetic', 'item_id': 170389, 'price': 30.0, 'cost': 24.0, 'category': 'oil'},
            {'name': 'Castrol GTX 10W40', 'item_id': 170390, 'price': 22.0, 'cost': 18.0, 'category': 'oil'},
            {'name': 'Bosch Oil Filter', 'item_id': 170391, 'price': 15.0, 'cost': 12.0, 'category': 'filter'},
            {'name': 'Mann Air Filter', 'item_id': 170392, 'price': 18.0, 'cost': 14.0, 'category': 'filter'},
            {'name': 'NGK Spark Plug', 'item_id': 170393, 'price': 8.0, 'cost': 6.0, 'category': 'ignition'},
            {'name': 'Denso Spark Plug', 'item_id': 170394, 'price': 10.0, 'cost': 7.5, 'category': 'ignition'},
            {'name': 'Brembo Brake Pads', 'item_id': 170395, 'price': 45.0, 'cost': 35.0, 'category': 'brakes'},
            {'name': 'Michelin Tire 195/65R15', 'item_id': 170396, 'price': 85.0, 'cost': 65.0, 'category': 'tire'},
            {'name': 'Continental Tire 205/55R16', 'item_id': 170397, 'price': 95.0, 'cost': 75.0, 'category': 'tire'},
        ]
        
        created_products = []
        
        for product_data in test_products_data:
            # Create product category if it doesn't exist
            category = self.env['product.category'].search([('name', '=', product_data['category'])], limit=1)
            if not category:
                category = self.env['product.category'].create({
                    'name': product_data['category'].title(),
                })
            
            # Create product
            product = self.env['product.product'].create({
                'name': product_data['name'],
                'default_code': str(product_data['item_id']),
                'type': 'consu',  # Consumable product
                'is_storable': True,  # Enable inventory tracking
                'list_price': product_data['price'],
                'standard_price': product_data['cost'],
                'categ_id': category.id,
                'available_in_pos': True,
            })
            
            created_products.append(product)
            
            # Add 10 units to inventory
            self.env['stock.quant']._update_available_quantity(
                product, 
                self.test_location, 
                10.0
            )
            
            # Verify inventory was created
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', '=', self.test_location.id)
            ])
            self.assertEqual(quant.quantity, 10.0, f"Inventory not set correctly for {product.name}")
        
        # Verify we created exactly 10 products
        self.assertEqual(len(created_products), 10, "Should have created exactly 10 products")
        
        # Store products for other tests
        self.test_products = created_products
        
        return created_products
    
    def test_02_pos_session_management(self):
        """Test 2: Verify POS session can be created and managed"""
        
        # Create POS session
        session = self.env['pos.session'].create({
            'config_id': self.pos_config.id,
            'user_id': self.env.user.id,
        })
        
        # Start session
        session.action_pos_session_open()
        self.assertEqual(session.state, 'opened', "Session should be in opened state")
        
        # Store session for other tests
        self.test_session = session
        
        return session
    
    def test_03_single_product_order_processing(self):
        """Test 3: Process a single product order through complete workflow"""
        
        # Setup: Create products and session
        products = self.test_01_create_test_products_with_inventory()
        session = self.test_02_pos_session_management()
        
        # Select first product for order
        test_product = products[0]
        
        # Create order data similar to real Karage POS request
        order_data = {
            "LocationID": 404,
            "CustomerID": 0,
            "CustomerName": "Test Customer",
            "CustomerContact": "123-456-7890",
            "AmountTotal": 25.0,
            "CheckoutDate": "19-08-2025 10:00:00 AM",
            "Remark": "Test order from automated tests",
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
            "OrderTakerID": "TEST_USER_001",
        }
        
        # Process the order
        pos_order_model = self.env['pos.order']
        result = pos_order_model.process_karage_order(order_data)
        
        # Verify processing was successful
        self.assertTrue(result.get('success'), f"Order processing failed: {result.get('error')}")
        self.assertIsNotNone(result.get('pos_order_id'), "POS Order ID should be returned")
        
        # Get the created POS order
        pos_order = self.env['pos.order'].browse(result['pos_order_id'])
        
        # Verify order details
        self.assertEqual(pos_order.karage_location_id, 404, "Karage Location ID not set correctly")
        self.assertEqual(len(pos_order.lines), 1, "Should have exactly one order line")
        self.assertEqual(pos_order.lines[0].qty, 2, "Order line quantity should be 2")
        self.assertEqual(pos_order.lines[0].product_id, test_product, "Wrong product in order line")
        
        # Verify payment was processed
        self.assertEqual(len(pos_order.payment_ids), 1, "Should have exactly one payment")
        self.assertEqual(pos_order.payment_ids[0].amount, 50.0, "Payment amount should be 50.0")
        
        # Verify inventory impact
        updated_quant = self.env['stock.quant'].search([
            ('product_id', '=', test_product.id),
            ('location_id', '=', self.test_location.id)
        ])
        self.assertEqual(updated_quant.quantity, 8.0, "Inventory should be reduced by 2 (10 - 2 = 8)")
        
        return pos_order
    
    def test_04_multi_product_order_processing(self):
        """Test 4: Process an order with multiple products"""
        
        # Setup: Create products and session
        products = self.test_01_create_test_products_with_inventory()
        session = self.test_02_pos_session_management()
        
        # Create order with 3 different products
        order_data = {
            "LocationID": 404,
            "CustomerID": 123,
            "CustomerName": "Multi Product Customer",
            "CustomerContact": "987-654-3210",
            "AmountTotal": 88.0,
            "CheckoutDate": "19-08-2025 11:00:00 AM",
            "Remark": "Multi-product test order",
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
                    "ItemID": int(products[3].default_code),  # Bosch Oil Filter
                    "Name": products[3].name,
                    "Quantity": 2,
                    "Price": 15.0,
                    "Cost": 12.0,
                    "itemType": "filter",
                    "DiscountAmount": 0,
                },
                {
                    "ItemID": int(products[7].default_code),  # Brembo Brake Pads
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
            "OrderTakerID": "TEST_USER_002",
        }
        
        # Process the order
        pos_order_model = self.env['pos.order']
        result = pos_order_model.process_karage_order(order_data)
        
        # Verify processing was successful
        self.assertTrue(result.get('success'), f"Multi-product order processing failed: {result.get('error')}")
        
        # Get the created POS order
        pos_order = self.env['pos.order'].browse(result['pos_order_id'])
        
        # Verify order has 3 lines
        self.assertEqual(len(pos_order.lines), 3, "Should have exactly three order lines")
        
        # Verify inventory impact for all products
        expected_quantities = [9.0, 8.0, 9.0]  # Original 10 minus quantities ordered
        test_products = [products[0], products[3], products[7]]
        
        for i, product in enumerate(test_products):
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', '=', self.test_location.id)
            ])
            self.assertEqual(quant.quantity, expected_quantities[i], 
                           f"Inventory for {product.name} should be {expected_quantities[i]}")
        
        return pos_order
    
    def test_05_invoice_generation_and_accounting(self):
        """Test 5: Verify invoice generation and accounting entries"""
        
        # Process an order first
        pos_order = self.test_03_single_product_order_processing()
        
        # Verify invoice was generated
        self.assertIsNotNone(pos_order.account_move, "Invoice should be generated")
        
        invoice = pos_order.account_move
        self.assertEqual(invoice.state, 'posted', "Invoice should be posted")
        self.assertEqual(invoice.amount_total, 50.0, "Invoice total should match payment amount")
        
        # Verify accounting entries exist
        self.assertTrue(len(invoice.line_ids) > 0, "Invoice should have accounting lines")
        
        return invoice
    
    def test_06_request_logging_and_audit(self):
        """Test 6: Verify all requests are properly logged for audit"""
        
        # Count existing logs
        initial_log_count = self.env['karage.request.logger'].search_count([])
        
        # Process an order (this should create a log entry)
        pos_order = self.test_03_single_product_order_processing()
        
        # Check that log entry was created
        final_log_count = self.env['karage.request.logger'].search_count([])
        self.assertGreater(final_log_count, initial_log_count, "Request should be logged")
        
        # Get the most recent log entry
        latest_log = self.env['karage.request.logger'].search([], order='create_date desc', limit=1)
        
        # Verify log contains proper data
        self.assertIsNotNone(latest_log.body, "Log should contain request body")
        self.assertIn('LocationID', latest_log.body, "Log should contain LocationID")
        
        return latest_log
    
    def test_07_error_handling_and_validation(self):
        """Test 7: Verify proper error handling for invalid requests"""
        
        # Test missing required fields
        invalid_order_data = {
            "CustomerName": "Test Customer",
            # Missing LocationID and OrderDetails
        }
        
        pos_order_model = self.env['pos.order']
        result = pos_order_model.process_karage_order(invalid_order_data)
        
        # Verify error handling
        self.assertFalse(result.get('success'), "Invalid order should fail")
        self.assertIn('error', result, "Error message should be provided")
        
        # Test empty order details
        empty_order_data = {
            "LocationID": 404,
            "OrderDetails": [],  # Empty order details
        }
        
        result = pos_order_model.process_karage_order(empty_order_data)
        self.assertFalse(result.get('success'), "Empty order should fail")
    
    def test_08_performance_and_bulk_processing(self):
        """Test 8: Verify system can handle multiple orders efficiently"""
        
        # Setup
        products = self.test_01_create_test_products_with_inventory()
        session = self.test_02_pos_session_management()
        
        # Process 5 orders in sequence
        successful_orders = 0
        
        for i in range(5):
            order_data = {
                "LocationID": 404,
                "CustomerID": i + 1000,
                "CustomerName": f"Bulk Test Customer {i+1}",
                "AmountTotal": 25.0,
                "CheckoutDate": f"19-08-2025 {10+i}:00:00 AM",
                "OrderDetails": [{
                    "ItemID": int(products[i % len(products)].default_code),
                    "Name": products[i % len(products)].name,
                    "Quantity": 1,
                    "Price": 25.0,
                    "Cost": 20.0,
                    "itemType": "test",
                }],
                "OrderCheckoutDetails": [{
                    "PaymentMode": 1,
                    "CardType": "Cash",
                    "AmountPaid": 25.0,
                }],
                "OrderTakerID": f"BULK_TEST_{i+1}",
            }
            
            result = self.env['pos.order'].process_karage_order(order_data)
            if result.get('success'):
                successful_orders += 1
        
        # Verify all orders processed successfully
        self.assertEqual(successful_orders, 5, "All 5 bulk orders should process successfully")
    
    def test_09_complete_workflow_integration(self):
        """Test 9: Complete end-to-end workflow validation"""
        
        # This test combines all previous tests into one complete workflow
        
        # Step 1: Setup inventory
        products = self.test_01_create_test_products_with_inventory()
        
        # Step 2: Create session
        session = self.test_02_pos_session_management()
        
        # Step 3: Process order
        pos_order = self.test_04_multi_product_order_processing()
        
        # Step 4: Verify invoice
        invoice = self.test_05_invoice_generation_and_accounting()
        
        # Step 5: Verify logging
        log_entry = self.test_06_request_logging_and_audit()
        
        # Step 6: Final validation - check all systems are consistent
        
        # Verify POS order is linked to invoice
        self.assertEqual(pos_order.account_move.id, invoice.id, "POS order should be linked to invoice")
        
        # Verify all inventory movements are recorded
        stock_moves = self.env['stock.move'].search([('product_id', 'in', [p.id for p in products])])
        self.assertGreater(len(stock_moves), 0, "Stock moves should be created")
        
        # Verify session contains the order
        self.assertIn(pos_order, session.order_ids, "Session should contain the processed order")
        
        return {
            'products': products,
            'session': session,
            'pos_order': pos_order,
            'invoice': invoice,
            'log_entry': log_entry,
        }