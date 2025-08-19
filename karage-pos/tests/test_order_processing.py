import json
from odoo.tests import TransactionCase, HttpCase
from odoo.exceptions import ValidationError


class TestOrderService(TransactionCase):
    """Test the Karage order processing service"""
    
    def setUp(self):
        super().setUp()
        self.order_service = self.env['karage.order.service']
        self.product_sync = self.env['karage.product.sync']
        
        # Sample order data based on the provided JSON
        self.sample_order_data = {
            "CreditCustomerID": 0,
            "CustomerContact": "",
            "DiscountCode": "",
            "AmountTotal": 25,
            "LocationID": 404,
            "CheckoutDate": "10-08-2025 05:16:43 PM",
            "CustomerID": 0,
            "Remark": "",
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

    def test_order_validation_missing_fields(self):
        """Test order validation with missing required fields"""
        # Test missing LocationID
        invalid_data = {}
        result = self.order_service.process_order(invalid_data)
        
        self.assertFalse(result.get('success'))
        self.assertIn('Missing required fields', result.get('error', ''))

    def test_order_validation_empty_order_details(self):
        """Test order validation with empty order details"""
        invalid_data = {
            "LocationID": 404,
            "OrderDetails": []
        }
        result = self.order_service.process_order(invalid_data)
        
        self.assertFalse(result.get('success'))
        self.assertIn('at least one item', result.get('error', ''))

    def test_successful_order_processing(self):
        """Test complete successful order processing"""
        result = self.order_service.process_order(self.sample_order_data)
        
        self.assertTrue(result.get('success'))
        self.assertIn('sale_order_id', result)
        self.assertIn('sale_order_name', result)
        
        # Verify sale order was created
        sale_order_id = result.get('sale_order_id')
        sale_order = self.env['sale.order'].browse(sale_order_id)
        
        self.assertTrue(sale_order.exists())
        self.assertEqual(sale_order.state, 'sale')  # Should be confirmed
        self.assertTrue(len(sale_order.order_line) > 0)

    def test_customer_creation(self):
        """Test customer creation logic"""
        # Test with customer name
        order_data = self.sample_order_data.copy()
        order_data['CustomerName'] = 'Test Customer'
        order_data['CustomerID'] = 12345
        order_data['CustomerContact'] = '1234567890'
        
        result = self.order_service.process_order(order_data)
        self.assertTrue(result.get('success'))
        
        # Verify customer was created
        customer = self.env['res.partner'].search([('ref', '=', '12345')])
        self.assertTrue(customer.exists())
        self.assertEqual(customer.name, 'Test Customer')
        self.assertEqual(customer.phone, '1234567890')

    def test_product_creation(self):
        """Test product creation from order details"""
        result = self.order_service.process_order(self.sample_order_data)
        self.assertTrue(result.get('success'))
        
        # Verify product was created
        product = self.env['product.product'].search([('default_code', '=', '170388')])
        self.assertTrue(product.exists())
        self.assertEqual(product.name, 'Fuchs Oil 5W30 Syn Sn ')
        self.assertEqual(product.list_price, 25)
        self.assertEqual(product.standard_price, 20)

    def test_product_category_creation(self):
        """Test product category creation"""
        result = self.order_service.process_order(self.sample_order_data)
        self.assertTrue(result.get('success'))
        
        # Verify category was created
        category = self.env['product.category'].search([('name', '=', 'oil')])
        self.assertTrue(category.exists())


class TestProductSync(TransactionCase):
    """Test the product synchronization service"""
    
    def setUp(self):
        super().setUp()
        self.product_sync = self.env['karage.product.sync']
        
        # Create a test product
        self.test_product = self.env['product.product'].create({
            'name': 'Test Oil Product',
            'default_code': '12345',
            'type': 'product',
            'list_price': 50.0,
            'standard_price': 30.0,
        })

    def test_stock_location_creation(self):
        """Test creation of stock locations for Karage locations"""
        result = self.product_sync.sync_product_stock(12345, 404, 1)
        
        self.assertTrue(result.get('success'))
        
        # Verify location was created
        location = self.env['stock.location'].search([('name', '=', 'Karage Location 404')])
        self.assertTrue(location.exists())
        self.assertEqual(location.usage, 'internal')

    def test_stock_movement_creation(self):
        """Test that stock movements are created correctly"""
        initial_qty = self.test_product.qty_available
        
        result = self.product_sync.sync_product_stock(12345, 404, 2)
        self.assertTrue(result.get('success'))
        
        # Check that stock moves were created
        stock_moves = self.env['stock.move'].search([
            ('product_id', '=', self.test_product.id),
            ('origin', '=', 'Karage POS')
        ])
        self.assertTrue(len(stock_moves) > 0)

    def test_bulk_product_sync(self):
        """Test bulk synchronization of multiple products"""
        order_details = [
            {
                'ItemID': 12345,
                'Quantity': 2,
                'Name': 'Test Product 1'
            },
            {
                'ItemID': 67890,
                'Quantity': 1,
                'Name': 'Test Product 2'
            }
        ]
        
        result = self.product_sync.bulk_sync_products(order_details, 404)
        
        self.assertTrue(result.get('success', False) or len(result.get('errors', [])) == 0)
        self.assertEqual(result.get('total_items'), 2)


class TestOrderControllerHTTP(HttpCase):
    """HTTP tests for the updated order controller"""
    
    def test_complete_order_processing_endpoint(self):
        """Test the complete order processing via HTTP endpoint"""
        order_data = {
            "LocationID": 404,
            "CustomerName": "Test HTTP Customer",
            "CustomerID": 999,
            "AmountTotal": 100,
            "OrderDetails": [{
                "ItemID": 888999,
                "Name": "HTTP Test Product",
                "Quantity": 2,
                "Price": 50,
                "Cost": 30,
                "itemType": "test"
            }],
            "OrderCheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": 100,
                "CardType": "Cash"
            }]
        }
        
        response = self.url_open(
            '/api/karage/handleOrder',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertTrue(response_data.get('success'))
        self.assertIn('sale_order_id', response_data)
        self.assertIn('log_id', response_data)

    def test_order_processing_with_errors(self):
        """Test order processing with invalid data"""
        invalid_order_data = {
            "LocationID": 404,
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