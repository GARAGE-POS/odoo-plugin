# -*- coding: utf-8 -*-

import json
from odoo.tests import HttpCase, tagged, TransactionCase
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestAPIControllerWebhook(HttpCase):
    """Test webhook endpoint for POS order creation"""

    def setUp(self):
        super(TestAPIControllerWebhook, self).setUp()
        # Create API config
        self.api_config = self.env['api.config'].create({
            'name': 'Test API Config',
            'active': True,
        })
        self.api_key = self.api_config.api_key
        
        # Create company
        self.company = self.env.company
        
        # Create currency
        self.currency = self.env.ref('base.USD')
        
        # Create journal for payment method
        self.cash_journal = self.env['account.journal'].create({
            'name': 'Cash',
            'type': 'cash',
            'code': 'CASH',
            'company_id': self.company.id,
        })
        
        # Create POS payment method
        self.cash_payment_method = self.env['pos.payment.method'].create({
            'name': 'Cash',
            'journal_id': self.cash_journal.id,
            'is_cash_count': True,
        })
        
        # Create POS config
        self.pos_config = self.env['pos.config'].create({
            'name': 'Test POS Config',
            'payment_method_ids': [(6, 0, [self.cash_payment_method.id])],
            'company_id': self.company.id,
        })
        
        # Create product
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
            'sale_ok': True,
            'available_in_pos': True,
            'list_price': 100.0,
        })
        
        # Create POS session
        self.pos_session = self.env['pos.session'].create({
            'config_id': self.pos_config.id,
            'user_id': self.env.user.id,
        })
        self.pos_session.action_pos_session_open()

    def test_webhook_get_request(self):
        """Test GET request returns endpoint info"""
        response = self.url_open('/api/v1/webhook/pos-order')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['endpoint'], '/api/v1/webhook/pos-order')

    def test_webhook_options_request(self):
        """Test OPTIONS request for CORS"""
        response = self.opener.options(
            self.base_url() + '/api/v1/webhook/pos-order',
            headers={'Origin': 'https://example.com'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Access-Control-Allow-Origin', response.headers)

    def test_webhook_missing_api_key(self):
        """Test webhook with missing API key"""
        order_data = {
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Invalid or missing API key', data['error'])

    def test_webhook_invalid_api_key(self):
        """Test webhook with invalid API key"""
        order_data = {
            'api_key': 'invalid_key',
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 401)

    def test_webhook_missing_required_fields(self):
        """Test webhook with missing required fields"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Missing required fields', data['error'])

    def test_webhook_invalid_json(self):
        """Test webhook with invalid JSON"""
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data='invalid json',
            headers={'Content-Type': 'application/json', 'X-API-Key': self.api_key}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Invalid JSON format', data['error'])

    def test_webhook_no_request_body(self):
        """Test webhook with no request body"""
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data='',
            headers={'Content-Type': 'application/json', 'X-API-Key': self.api_key}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Request body is required', data['error'])

    def test_webhook_no_pos_session(self):
        """Test webhook when no POS session is open"""
        # Close the session
        self.pos_session.action_pos_session_closing_control()
        self.pos_session.action_pos_session_close()
        
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('No open POS session found', data['error'])

    def test_webhook_no_payment_methods(self):
        """Test webhook when no payment methods configured"""
        # Remove payment methods
        self.pos_config.payment_method_ids = [(5, 0, 0)]
        
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('No payment methods configured', data['error'])

    def test_webhook_missing_journal(self):
        """Test webhook when payment method has no journal"""
        # Remove journal from payment method
        self.cash_payment_method.journal_id = False
        
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Journal not found for payment method', data['error'])

    def test_webhook_product_not_found(self):
        """Test webhook when product is not found"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Non-existent Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('Product not found', data['error'])

    def test_webhook_payment_mode_mapping(self):
        """Test webhook with different payment modes"""
        # Create additional payment methods for different modes
        card_journal = self.env['account.journal'].create({
            'name': 'Card',
            'type': 'bank',
            'code': 'CARD',
            'company_id': self.company.id,
        })
        card_payment_method = self.env['pos.payment.method'].create({
            'name': 'Card',
            'journal_id': card_journal.id,
        })
        self.pos_config.payment_method_ids = [(6, 0, [self.cash_payment_method.id, card_payment_method.id])]
        
        # Test PaymentMode = 2 (Card)
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 2, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_webhook_payment_mode_not_found(self):
        """Test webhook with invalid payment mode"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 99, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('PaymentMode must be', data['error'])

    def test_webhook_data_inconsistency(self):
        """Test webhook with data inconsistency"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 200,  # Inconsistent
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Data inconsistency', data['error'])

    def test_webhook_payment_inconsistency(self):
        """Test webhook with payment amount inconsistency"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 50}],
            'AmountTotal': 100,
            'AmountPaid': 100,  # Different from CheckoutDetails
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('Payment inconsistency', data['error'])

    def test_webhook_no_order_lines(self):
        """Test webhook with no valid order lines"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [],  # Empty items
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('No valid order lines created', data['error'])

    def test_webhook_no_payment_lines(self):
        """Test webhook with no valid payment lines"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 0}],  # Zero amount
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('No valid payment lines created', data['error'])

    def test_webhook_successful_order_creation(self):
        """Test successful webhook order creation"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 123,
            'OrderItems': [
                {
                    'ItemName': 'Test Product',
                    'ItemID': self.product.id,
                    'Price': 100.0,
                    'Quantity': 1.0,
                    'DiscountAmount': 0.0,
                }
            ],
            'CheckoutDetails': [
                {
                    'PaymentMode': 1,
                    'AmountPaid': 100.0,
                    'CardType': 'Cash',
                }
            ],
            'AmountTotal': 100.0,
            'AmountPaid': 100.0,
            'GrandTotal': 100.0,
            'Tax': 0.0,
            'TaxPercent': 0.0,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertIsNotNone(data['data']['id'])
        self.assertEqual(data['data']['external_order_id'], 123)
        
        # Verify POS order was created
        pos_order = self.env['pos.order'].browse(data['data']['id'])
        self.assertTrue(pos_order.exists())
        self.assertEqual(pos_order.state, 'paid')

    def test_webhook_with_discount(self):
        """Test webhook with discount"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 124,
            'OrderItems': [
                {
                    'ItemName': 'Test Product',
                    'Price': 100.0,
                    'Quantity': 1.0,
                    'DiscountAmount': 10.0,
                }
            ],
            'CheckoutDetails': [
                {
                    'PaymentMode': 1,
                    'AmountPaid': 90.0,
                }
            ],
            'AmountTotal': 90.0,
            'AmountPaid': 90.0,
            'GrandTotal': 90.0,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_webhook_with_tax(self):
        """Test webhook with tax"""
        # Create tax
        tax = self.env['account.tax'].create({
            'name': 'Test Tax 15%',
            'amount': 15.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })
        self.product.taxes_id = [(6, 0, [tax.id])]
        
        order_data = {
            'api_key': self.api_key,
            'OrderID': 125,
            'OrderItems': [
                {
                    'ItemName': 'Test Product',
                    'Price': 100.0,
                    'Quantity': 1.0,
                    'DiscountAmount': 0.0,
                }
            ],
            'CheckoutDetails': [
                {
                    'PaymentMode': 1,
                    'AmountPaid': 115.0,
                }
            ],
            'AmountTotal': 100.0,
            'AmountPaid': 115.0,
            'GrandTotal': 115.0,
            'Tax': 15.0,
            'TaxPercent': 15.0,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_webhook_all_payment_modes(self):
        """Test webhook with all payment modes"""
        # Create journals and payment methods for all modes
        payment_modes = {
            2: 'Card',
            3: 'Credit',
            5: 'Tabby',
            6: 'Tamara',
            7: 'StcPay',
            8: 'Bank Transfer',
        }
        
        payment_methods = [self.cash_payment_method]
        for mode, name in payment_modes.items():
            journal = self.env['account.journal'].create({
                'name': name,
                'type': 'bank' if mode != 1 else 'cash',
                'code': name.upper()[:4],
                'company_id': self.company.id,
            })
            pm = self.env['pos.payment.method'].create({
                'name': name,
                'journal_id': journal.id,
            })
            payment_methods.append(pm)
        
        self.pos_config.payment_method_ids = [(6, 0, [pm.id for pm in payment_methods])]
        
        # Test each payment mode
        for mode in [1, 2, 3, 5, 6, 7, 8]:
            order_data = {
                'api_key': self.api_key,
                'OrderID': 100 + mode,
                'OrderItems': [
                    {
                        'ItemName': 'Test Product',
                        'Price': 100.0,
                        'Quantity': 1.0,
                    }
                ],
                'CheckoutDetails': [
                    {
                        'PaymentMode': mode,
                        'AmountPaid': 100.0,
                    }
                ],
                'AmountTotal': 100.0,
                'AmountPaid': 100.0,
                'GrandTotal': 100.0,
            }
            response = self.url_open(
                '/api/v1/webhook/pos-order',
                data=json.dumps(order_data),
                headers={'Content-Type': 'application/json'}
            )
            self.assertEqual(response.status_code, 200, f'PaymentMode {mode} failed')
            data = json.loads(response.content)
            self.assertEqual(data['status'], 'success')

    def test_webhook_api_key_in_header(self):
        """Test webhook with API key in header"""
        order_data = {
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json', 'X-API-Key': self.api_key}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_webhook_product_by_id(self):
        """Test webhook finding product by ItemID"""
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [
                {
                    'ItemID': self.product.id,
                    'ItemName': 'Different Name',
                    'Price': 100.0,
                    'Quantity': 1.0,
                }
            ],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 100}],
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

    def test_webhook_multiple_items(self):
        """Test webhook with multiple order items"""
        product2 = self.env['product.product'].create({
            'name': 'Test Product 2',
            'type': 'product',
            'sale_ok': True,
            'available_in_pos': True,
            'list_price': 50.0,
        })
        
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [
                {
                    'ItemName': 'Test Product',
                    'Price': 100.0,
                    'Quantity': 1.0,
                },
                {
                    'ItemName': 'Test Product 2',
                    'Price': 50.0,
                    'Quantity': 2.0,
                }
            ],
            'CheckoutDetails': [{'PaymentMode': 1, 'AmountPaid': 200}],
            'AmountTotal': 200,
            'AmountPaid': 200,
            'GrandTotal': 200,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        pos_order = self.env['pos.order'].browse(data['data']['id'])
        self.assertEqual(len(pos_order.lines), 2)

    def test_webhook_multiple_payments(self):
        """Test webhook with multiple payment methods"""
        card_journal = self.env['account.journal'].create({
            'name': 'Card',
            'type': 'bank',
            'code': 'CARD',
            'company_id': self.company.id,
        })
        card_payment_method = self.env['pos.payment.method'].create({
            'name': 'Card',
            'journal_id': card_journal.id,
        })
        self.pos_config.payment_method_ids = [(6, 0, [self.cash_payment_method.id, card_payment_method.id])]
        
        order_data = {
            'api_key': self.api_key,
            'OrderID': 1,
            'OrderItems': [{'ItemName': 'Test Product', 'Price': 100, 'Quantity': 1}],
            'CheckoutDetails': [
                {'PaymentMode': 1, 'AmountPaid': 50},
                {'PaymentMode': 2, 'AmountPaid': 50},
            ],
            'AmountTotal': 100,
            'AmountPaid': 100,
            'GrandTotal': 100,
        }
        response = self.url_open(
            '/api/v1/webhook/pos-order',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        
        pos_order = self.env['pos.order'].browse(data['data']['id'])
        self.assertEqual(len(pos_order.payment_ids), 2)

