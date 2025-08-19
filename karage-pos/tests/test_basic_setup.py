"""
Basic setup test to verify core functionality before comprehensive testing
"""

from odoo.tests import TransactionCase


class TestBasicSetup(TransactionCase):
    """Basic tests to ensure the module is working correctly"""

    def setUp(self):
        super().setUp()
        
    def test_01_module_installation(self):
        """Test that the module is properly installed"""
        # Check that our models exist
        self.assertTrue(hasattr(self.env, 'karage.request.logger'), "Request logger model should exist")
        
        # Check POS order extension
        pos_order = self.env['pos.order']
        self.assertTrue(hasattr(pos_order, 'process_karage_order'), "POS order should have karage method")
        
    def test_02_create_simple_product(self):
        """Test creating a simple product"""
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'default_code': 'TEST001',
            'type': 'consu',
            'is_storable': True,
            'list_price': 10.0,
            'standard_price': 8.0,
        })
        
        self.assertEqual(product.name, 'Test Product')
        self.assertEqual(product.default_code, 'TEST001')
        
        return product
        
    def test_03_create_pos_config(self):
        """Test creating a POS configuration"""
        
        # Create basic journals first
        cash_journal = self.env['account.journal'].create({
            'name': 'Test Cash',
            'code': 'TCH',
            'type': 'cash',
            'company_id': self.env.company.id,
        })
        
        sales_journal = self.env['account.journal'].create({
            'name': 'Test Sales',
            'code': 'TSL',
            'type': 'sale',
            'company_id': self.env.company.id,
        })
        
        # Create payment method
        payment_method = self.env['pos.payment.method'].create({
            'name': 'Test Cash Method',
            'journal_id': cash_journal.id,
            'is_cash_count': True,
            'company_id': self.env.company.id,
        })
        
        # Create pricelist
        pricelist = self.env['product.pricelist'].create({
            'name': 'Test Pricelist',
            'currency_id': self.env.company.currency_id.id,
        })
        
        # Get stock location
        stock_location = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        # Get picking type
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        # Create POS config
        pos_config = self.env['pos.config'].create({
            'name': 'Test Karage POS',
            'journal_id': sales_journal.id,
            'pricelist_id': pricelist.id,
            'stock_location_id': stock_location.id,
            'picking_type_id': picking_type.id,
            'payment_method_ids': [(6, 0, [payment_method.id])],
            'karage_location_id': 999,
            'company_id': self.env.company.id,
        })
        
        self.assertEqual(pos_config.karage_location_id, 999)
        return pos_config
        
    def test_04_simple_order_processing(self):
        """Test basic order processing"""
        
        # Create required data
        product = self.test_02_create_simple_product()
        pos_config = self.test_03_create_pos_config()
        
        # Add inventory
        self.env['stock.quant']._update_available_quantity(
            product, 
            pos_config.stock_location_id, 
            5.0
        )
        
        # Create simple order data
        order_data = {
            "LocationID": 999,
            "CustomerName": "Test Customer",
            "OrderDetails": [{
                "ItemID": int(product.default_code.replace('TEST', '')),
                "Name": product.name,
                "Quantity": 1,
                "Price": product.list_price,
                "Cost": product.standard_price,
                "itemType": "test"
            }],
            "OrderCheckoutDetails": [{
                "CardType": "Cash",
                "AmountPaid": 10.0,
            }],
            "OrderTakerID": "TEST001",
        }
        
        # Process order
        try:
            result = self.env['pos.order'].process_karage_order(order_data)
            self.assertTrue(result.get('success', False), f"Order should succeed: {result}")
        except Exception as e:
            self.fail(f"Order processing failed with exception: {str(e)}")
            
        return result