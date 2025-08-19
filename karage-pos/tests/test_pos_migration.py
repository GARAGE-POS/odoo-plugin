import json
from odoo.tests import TransactionCase, HttpCase
from odoo.exceptions import ValidationError


class TestPosOrderProcessing(TransactionCase):
    """Test the new POS-based order processing"""
    
    def setUp(self):
        super().setUp()
        self.pos_order_model = self.env['pos.order']
        
        # Sample order data from Karage POS
        self.sample_order_data = {
            "CreditCustomerID": 0,
            "CustomerContact": "",
            "DiscountCode": "",
            "AmountTotal": 25,
            "LocationID": 404,
            "CheckoutDate": "10-08-2025 05:16:43 PM",
            "CustomerID": 0,
            "Remark": "Test order for POS migration",
            "OrderDetails": [{
                "itemType": "oil",
                "ItemID": 170388,
                "checkQty": 0,
                "AlternateName": "زيت فوكس 5W30 Syn Sn ",
                "Name": "Fuchs Oil 5W30 Syn Sn ",
                "localStock": -169,
                "PackageID": 0,
                "IsInventoryItem": True,
                "UniqueID": 1907401772308368892,
                "OrderDetailID": 0,
                "DiscountAmount": 0,
                "OldQuantity": 0,
                "Cost": 20,
                "CurrentStock": -168,
                "Mode": "Add",
                "OrderDetailPackages": [],
                "ItemTypeValue": "10000",
                "Price": 25,
                "Status": 201,
                "Quantity": 1
            }],
            "OrderCheckoutDetails": [{
                "PaymentMode": 1,
                "AmountDiscount": 0,
                "CardNumber": "",
                "AmountPaid": 18.75,
                "CardType": "Cash",
                "CardHolderName": ""
            }],
            "OrderStatus": 103,
            "AmountPaid": 18.75,
            "DiscountPercent": 0,
            "HolderName": "",
            "PartialPayment": 0,
            "CustomerName": "",
            "GrandTotal": 18.75,
            "AmountDiscount": 6.25,
            "TaxPercent": 0,
            "IsPartialPaid": False,
            "ServiceCharges": 0,
            "Tax": 0,
            "BalanceAmount": 0,
            "PaymentMode": 1,
            "OrderTakerID": "2487"
        }

    def test_pos_order_validation_missing_fields(self):
        """Test POS order validation with missing required fields"""
        # Test missing LocationID
        invalid_data = {}
        result = self.pos_order_model.process_karage_order(invalid_data)
        
        self.assertFalse(result.get('success'))
        self.assertIn('Missing required fields', result.get('error', ''))

    def test_pos_order_validation_empty_order_details(self):
        """Test POS order validation with empty order details"""
        invalid_data = {
            "LocationID": 404,
            "OrderDetails": []
        }
        result = self.pos_order_model.process_karage_order(invalid_data)
        
        self.assertFalse(result.get('success'))
        self.assertIn('at least one item', result.get('error', ''))

    def test_successful_pos_order_processing(self):
        """Test complete successful POS order processing"""
        result = self.pos_order_model.process_karage_order(self.sample_order_data)
        
        self.assertTrue(result.get('success'), f"Order processing failed: {result.get('error')}")
        self.assertIn('pos_order_id', result)
        self.assertIn('pos_order_name', result)
        self.assertIn('session_id', result)
        self.assertEqual(result.get('api_version'), None)  # Set by controller, not model
        
        # Verify POS order was created
        pos_order_id = result.get('pos_order_id')
        pos_order = self.env['pos.order'].browse(pos_order_id)
        
        self.assertTrue(pos_order.exists())
        self.assertEqual(pos_order.karage_location_id, 404)
        self.assertEqual(pos_order.karage_order_id, "2487")
        self.assertTrue(len(pos_order.lines) > 0)
        
        # Verify session was created/used
        session_id = result.get('session_id')
        session = self.env['pos.session'].browse(session_id)
        self.assertTrue(session.exists())
        self.assertEqual(session.karage_location_id, 404)

    def test_pos_config_auto_creation(self):
        """Test automatic POS configuration creation for new locations"""
        # Use a new location ID that doesn't exist
        order_data = self.sample_order_data.copy()
        order_data['LocationID'] = 999
        
        result = self.pos_order_model.process_karage_order(order_data)
        
        self.assertTrue(result.get('success'))
        
        # Verify POS config was created
        pos_config = self.env['pos.config'].search([('karage_location_id', '=', 999)])
        self.assertTrue(pos_config.exists())
        self.assertEqual(pos_config.name, 'Karage Location 999')

    def test_customer_creation_pos_workflow(self):
        """Test customer creation in POS workflow"""
        # Test with customer name
        order_data = self.sample_order_data.copy()
        order_data['CustomerName'] = 'POS Test Customer'
        order_data['CustomerID'] = 54321
        order_data['CustomerContact'] = '9876543210'
        
        result = self.pos_order_model.process_karage_order(order_data)
        self.assertTrue(result.get('success'))
        
        # Verify customer was created
        customer = self.env['res.partner'].search([('ref', '=', '54321')])
        self.assertTrue(customer.exists())
        self.assertEqual(customer.name, 'POS Test Customer')
        self.assertEqual(customer.phone, '9876543210')
        
        # Verify order is linked to customer
        pos_order = self.env['pos.order'].browse(result['pos_order_id'])
        self.assertEqual(pos_order.partner_id, customer)

    def test_product_creation_pos_workflow(self):
        """Test product creation in POS workflow"""
        result = self.pos_order_model.process_karage_order(self.sample_order_data)
        self.assertTrue(result.get('success'))
        
        # Verify product was created
        product = self.env['product.product'].search([('default_code', '=', '170388')])
        self.assertTrue(product.exists())
        self.assertEqual(product.name, 'Fuchs Oil 5W30 Syn Sn ')
        self.assertEqual(product.list_price, 25)
        self.assertEqual(product.standard_price, 20)
        self.assertTrue(product.available_in_pos)

    def test_payment_processing_pos_workflow(self):
        """Test payment processing in POS workflow"""
        result = self.pos_order_model.process_karage_order(self.sample_order_data)
        self.assertTrue(result.get('success'))
        
        # Verify POS payment was created
        pos_order = self.env['pos.order'].browse(result['pos_order_id'])
        payments = pos_order.payment_ids
        
        self.assertTrue(len(payments) > 0)
        payment = payments[0]
        self.assertEqual(payment.amount, 18.75)
        self.assertEqual(payment.card_type, 'Cash')

    def test_request_logging_pos_workflow(self):
        """Test that requests are logged in POS workflow"""
        initial_log_count = self.env['karage.request.logger'].search_count([])
        
        result = self.pos_order_model.process_karage_order(self.sample_order_data)
        self.assertTrue(result.get('success'))
        
        # Verify request was logged (done in the model)
        final_log_count = self.env['karage.request.logger'].search_count([])
        self.assertEqual(final_log_count, initial_log_count + 1)


class TestPosConfigManagement(TransactionCase):
    """Test POS configuration management"""
    
    def test_karage_location_uniqueness(self):
        """Test that Karage Location IDs must be unique"""
        # Create first config
        config1 = self.env['pos.config'].create({
            'name': 'Test Location 1',
            'karage_location_id': 123,
            'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
            'pricelist_id': self.env.ref('product.list0').id,
        })
        
        # Try to create second config with same location ID
        with self.assertRaises(ValidationError):
            self.env['pos.config'].create({
                'name': 'Test Location 2',
                'karage_location_id': 123,
                'journal_id': self.env['account.journal'].search([('type', '=', 'sale')], limit=1).id,
                'pricelist_id': self.env.ref('product.list0').id,
            })

    def test_session_management(self):
        """Test POS session management for Karage locations"""
        # Get config for a location
        pos_config = self.env['pos.config'].get_config_for_location(404)
        
        # Get session
        session = pos_config.get_karage_session()
        self.assertTrue(session.exists())
        self.assertIn(session.state, ['opening_control', 'opened'])
        
        # Getting session again should return the same one
        session2 = pos_config.get_karage_session()
        self.assertEqual(session.id, session2.id)


class TestKarageHttpEndpoint(HttpCase):
    """Test the HTTP endpoint with new POS workflow"""
    
    def test_pos_order_processing_endpoint(self):
        """Test the POS order processing via HTTP endpoint"""
        order_data = {
            "LocationID": 405,
            "CustomerName": "HTTP POS Test Customer",
            "CustomerID": 888,
            "AmountTotal": 100,
            "OrderDetails": [{
                "ItemID": 777888,
                "Name": "HTTP POS Test Product",
                "Quantity": 2,
                "Price": 50,
                "Cost": 30,
                "itemType": "test_pos"
            }],
            "OrderCheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": 100,
                "CardType": "Cash"
            }],
            "OrderTakerID": "HTTP_TEST"
        }
        
        response = self.url_open(
            '/api/karage/handleOrder',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertTrue(response_data.get('success'), 
                       f"HTTP endpoint failed: {response_data.get('error')}")
        self.assertIn('pos_order_id', response_data)
        self.assertIn('session_id', response_data)
        self.assertIn('log_id', response_data)
        self.assertEqual(response_data.get('api_version'), '2.0')  # New version indicator

    def test_pos_endpoint_error_handling(self):
        """Test error handling in POS endpoint"""
        invalid_order_data = {
            "LocationID": 406,
            # Missing OrderDetails
        }
        
        response = self.url_open(
            '/api/karage/handleOrder',
            data=json.dumps(invalid_order_data),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertFalse(response_data.get('success'))
        self.assertIn('error', response_data)
        self.assertIn('log_id', response_data)
        self.assertEqual(response_data.get('api_version'), '2.0')