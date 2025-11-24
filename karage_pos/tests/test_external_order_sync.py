# -*- coding: utf-8 -*-

from unittest.mock import Mock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestExternalOrderSync(TransactionCase):
    """Test External Order Sync model"""

    def setUp(self):
        super(TestExternalOrderSync, self).setUp()
        self.company = self.env.company
        self.currency = self.env.ref("base.USD")

        # Clean up any existing POS sessions from previous tests
        try:
            self.env["pos.session"].sudo().search([]).unlink()
        except Exception:
            pass

        # Create journal for payment method
        self.cash_journal = self.env["account.journal"].create(
            {
                "name": "Cash",
                "type": "cash",
                "code": "CASH",
                "company_id": self.company.id,
            }
        )

        # Create POS payment method
        self.cash_payment_method = self.env["pos.payment.method"].create(
            {
                "name": "Cash",
                "journal_id": self.cash_journal.id,
                "is_cash_count": True,
            }
        )

        # Create POS config
        self.pos_config = self.env["pos.config"].create(
            {
                "name": "Test POS Config",
                "payment_method_ids": [(6, 0, [self.cash_payment_method.id])],
                "company_id": self.company.id,
                "journal_id": self.cash_journal.id,
            }
        )
        try:
            self.pos_config.pricelist_id = self.env.ref("product.list0")
        except ValueError:
            # Create a default pricelist if not found
            self.pricelist = self.env["product.pricelist"].create(
                {"name": "Default Pricelist", "currency_id": self.currency.id}
            )
            self.pos_config.pricelist_id = self.pricelist

        # Create product
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "product",
                "sale_ok": True,
                "available_in_pos": True,
                "list_price": 100.0,
            }
        )

        # Create external order sync
        self.sync_config = self.env["external.order.sync"].create(
            {
                "name": "Test Sync",
                "external_api_url": "https://example.com/api/orders",
                "external_api_key": "test_api_key",
                "pos_config_id": self.pos_config.id,
                "auto_create_session": True,
                "active": True,
            }
        )

    def tearDown(self):
        super(TestExternalOrderSync, self).tearDown()
        # Delete any POS sessions created during tests to avoid conflicts
        try:
            sessions = self.env["pos.session"].sudo().search([])
            sessions.unlink()
        except Exception:
            # Ignore errors if sessions can't be deleted (e.g., reconciled entries or aborted transaction)
            pass

    def test_create_external_order_sync(self):
        """Test creating external order sync"""
        sync = self.env["external.order.sync"].create(
            {
                "name": "New Sync",
                "external_api_url": "https://test.com/api",
                "external_api_key": "key123",
                "pos_config_id": self.pos_config.id,
            }
        )
        self.assertEqual(sync.name, "New Sync")
        self.assertEqual(sync.external_api_url, "https://test.com/api")
        self.assertTrue(sync.auto_create_session)
        self.assertEqual(sync.sync_interval, 15)

    def test_get_or_create_pos_session_existing(self):
        """Test getting existing POS session"""
        # Create and open session
        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        result = self.sync_config._get_or_create_pos_session()
        self.assertEqual(result.id, session.id)

    def test_get_or_create_pos_session_create_new(self):
        """Test creating new POS session when auto_create is enabled"""
        # Ensure no session exists
        self.env["pos.session"].search(
            [("config_id", "=", self.pos_config.id)]
        ).unlink()

        result = self.sync_config._get_or_create_pos_session()
        self.assertTrue(result.exists())
        self.assertEqual(result.config_id.id, self.pos_config.id)
        self.assertEqual(result.state, "opened")

    def test_get_or_create_pos_session_disabled(self):
        """Test error when no session and auto_create is disabled"""
        self.sync_config.auto_create_session = False
        self.env["pos.session"].search(
            [("config_id", "=", self.pos_config.id)]
        ).unlink()

        with self.assertRaises(UserError):
            self.sync_config._get_or_create_pos_session()

    @patch("requests.get")
    def test_fetch_orders_from_external_success(self, mock_get):
        """Test fetching orders from external API successfully"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "OrderID": 1,
                "OrderItems": [
                    {"ItemName": "Test Product", "Price": 100, "Quantity": 1}
                ],
                "CheckoutDetails": [{"PaymentMode": 1, "AmountPaid": 100}],
                "AmountTotal": 100,
                "AmountPaid": 100,
            }
        ]
        mock_get.return_value = mock_response

        orders = self.sync_config._fetch_orders_from_external()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["OrderID"], 1)
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_fetch_orders_from_external_array_format(self, mock_get):
        """Test fetching orders in array format"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"OrderID": 1, "OrderItems": [], "CheckoutDetails": []},
            {"OrderID": 2, "OrderItems": [], "CheckoutDetails": []},
        ]
        mock_get.return_value = mock_response

        orders = self.sync_config._fetch_orders_from_external()
        self.assertEqual(len(orders), 2)

    @patch("requests.get")
    def test_fetch_orders_from_external_object_format(self, mock_get):
        """Test fetching orders in object format"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orders": [{"OrderID": 1, "OrderItems": [], "CheckoutDetails": []}]
        }
        mock_get.return_value = mock_response

        orders = self.sync_config._fetch_orders_from_external()
        self.assertEqual(len(orders), 1)

    @patch("requests.get")
    def test_fetch_orders_from_external_single_order(self, mock_get):
        """Test fetching single order object"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "OrderID": 1,
            "OrderItems": [],
            "CheckoutDetails": [],
        }
        mock_get.return_value = mock_response

        orders = self.sync_config._fetch_orders_from_external()
        self.assertEqual(len(orders), 1)

    @patch("requests.get")
    def test_fetch_orders_from_external_error(self, mock_get):
        """Test handling API error"""
        mock_get.side_effect = Exception("Connection error")

        with self.assertRaises(UserError):
            self.sync_config._fetch_orders_from_external()

    @patch("requests.get")
    def test_fetch_orders_from_external_http_error(self, mock_get):
        """Test handling HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_get.return_value = mock_response

        with self.assertRaises(UserError):
            self.sync_config._fetch_orders_from_external()

    def test_process_external_order_success(self):
        """Test processing external order successfully"""
        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Test Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                    "DiscountAmount": 0.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 100.0,
                    "CardType": "Cash",
                }
            ],
        }

        pos_order = self.sync_config._process_external_order(order_data)
        self.assertTrue(pos_order)
        self.assertEqual(pos_order.state, "paid")
        self.assertEqual(len(pos_order.lines), 1)

    def test_process_external_order_no_items(self):
        """Test processing order with no items"""
        order_data = {
            "OrderID": 123,
            "OrderItems": [],
            "CheckoutDetails": [],
        }

        result = self.sync_config._process_external_order(order_data)
        self.assertFalse(result)

    def test_process_external_order_product_not_found(self):
        """Test processing order with product not found"""
        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Non-existent Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 100.0,
                }
            ],
        }

        result = self.sync_config._process_external_order(order_data)
        self.assertFalse(result)

    def test_process_external_order_no_payment_methods(self):
        """Test processing order when no payment methods"""
        self.pos_config.payment_method_ids = [(5, 0, 0)]

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Test Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 100.0,
                }
            ],
        }

        with self.assertRaises(UserError):
            self.sync_config._process_external_order(order_data)

    def test_process_external_order_missing_journal(self):
        """Test processing order when payment method has no journal"""
        self.cash_payment_method.journal_id = False

        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Test Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 100.0,
                }
            ],
        }

        with self.assertRaises(UserError):
            self.sync_config._process_external_order(order_data)

    def test_process_external_order_payment_mode_mapping(self):
        """Test processing order with different payment modes"""
        # Create additional payment methods
        payment_modes = {
            2: "Card",
            3: "Credit",
            5: "Tabby",
        }

        payment_methods = [self.cash_payment_method]
        for mode, name in payment_modes.items():
            journal = self.env["account.journal"].create(
                {
                    "name": name,
                    "type": "bank",
                    "code": name.upper()[:4],
                    "company_id": self.company.id,
                }
            )
            pm = self.env["pos.payment.method"].create(
                {
                    "name": name,
                    "journal_id": journal.id,
                }
            )
            payment_methods.append(pm)

        self.pos_config.payment_method_ids = [(6, 0, [pm.id for pm in payment_methods])]

        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        # Test each payment mode
        for mode in [1, 2, 3, 5]:
            order_data = {
                "OrderID": 100 + mode,
                "OrderItems": [
                    {
                        "ItemName": "Test Product",
                        "Price": 100.0,
                        "Quantity": 1.0,
                    }
                ],
                "CheckoutDetails": [
                    {
                        "PaymentMode": mode,
                        "AmountPaid": 100.0,
                    }
                ],
            }

            pos_order = self.sync_config._process_external_order(order_data)
            self.assertTrue(pos_order, f"PaymentMode {mode} failed")

    def test_process_external_order_invalid_payment_mode(self):
        """Test processing order with invalid payment mode"""
        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Test Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 99,  # Invalid
                    "AmountPaid": 100.0,
                }
            ],
        }

        with self.assertRaises(UserError):
            self.sync_config._process_external_order(order_data)

    def test_process_external_order_with_discount(self):
        """Test processing order with discount"""
        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Test Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                    "DiscountAmount": 10.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 90.0,
                }
            ],
        }

        pos_order = self.sync_config._process_external_order(order_data)
        self.assertTrue(pos_order)
        self.assertEqual(pos_order.lines[0].discount, 10.0)

    def test_process_external_order_multiple_items(self):
        """Test processing order with multiple items"""
        product2 = self.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "product",
                "sale_ok": True,
                "available_in_pos": True,
                "list_price": 50.0,
            }
        )

        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Test Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                },
                {
                    "ItemName": "Test Product 2",
                    "Price": 50.0,
                    "Quantity": 2.0,
                },
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 200.0,
                }
            ],
        }

        pos_order = self.sync_config._process_external_order(order_data)
        self.assertTrue(pos_order)
        self.assertEqual(len(pos_order.lines), 2)

    def test_process_external_order_multiple_payments(self):
        """Test processing order with multiple payments"""
        card_journal = self.env["account.journal"].create(
            {
                "name": "Card",
                "type": "bank",
                "code": "CARD",
                "company_id": self.company.id,
            }
        )
        card_payment_method = self.env["pos.payment.method"].create(
            {
                "name": "Card",
                "journal_id": card_journal.id,
            }
        )
        self.pos_config.payment_method_ids = [
            (6, 0, [self.cash_payment_method.id, card_payment_method.id])
        ]

        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemName": "Test Product",
                    "Price": 100.0,
                    "Quantity": 1.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 50.0,
                },
                {
                    "PaymentMode": 2,
                    "AmountPaid": 50.0,
                },
            ],
        }

        pos_order = self.sync_config._process_external_order(order_data)
        self.assertTrue(pos_order)
        self.assertEqual(len(pos_order.payment_ids), 2)

    def test_process_external_order_product_by_id(self):
        """Test processing order finding product by ItemID"""
        session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.env.user.id,
            }
        )
        session.action_pos_session_open()

        order_data = {
            "OrderID": 123,
            "OrderItems": [
                {
                    "ItemID": self.product.id,
                    "ItemName": "Different Name",
                    "Price": 100.0,
                    "Quantity": 1.0,
                }
            ],
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": 100.0,
                }
            ],
        }

        pos_order = self.sync_config._process_external_order(order_data)
        self.assertTrue(pos_order)
        self.assertEqual(pos_order.lines[0].product_id.id, self.product.id)

    @patch(
        "odoo.addons.karage_pos.models.external_order_sync.ExternalOrderSync._fetch_orders_from_external"
    )
    @patch(
        "odoo.addons.karage_pos.models.external_order_sync.ExternalOrderSync._process_external_order"
    )
    def test_sync_orders_success(self, mock_process, mock_fetch):
        """Test syncing orders successfully"""
        mock_fetch.return_value = [
            {"OrderID": 1, "OrderItems": [], "CheckoutDetails": []},
            {"OrderID": 2, "OrderItems": [], "CheckoutDetails": []},
        ]
        mock_process.return_value = Mock(id=1)

        self.sync_config.sync_orders()

        self.assertEqual(mock_fetch.call_count, 1)
        self.assertEqual(mock_process.call_count, 2)
        self.assertEqual(self.sync_config.last_sync_status, "success")

    @patch(
        "odoo.addons.karage_pos.models.external_order_sync.ExternalOrderSync._fetch_orders_from_external"
    )
    def test_sync_orders_no_orders(self, mock_fetch):
        """Test syncing when no orders returned"""
        mock_fetch.return_value = []

        self.sync_config.sync_orders()

        self.assertEqual(self.sync_config.last_sync_status, "no_orders")

    @patch(
        "odoo.addons.karage_pos.models.external_order_sync.ExternalOrderSync._fetch_orders_from_external"
    )
    def test_sync_orders_error(self, mock_fetch):
        """Test syncing when error occurs"""
        mock_fetch.side_effect = UserError("Test error")

        self.sync_config.sync_orders()

        self.assertEqual(self.sync_config.last_sync_status, "error")
        self.assertIn("Test error", self.sync_config.last_sync_message)
