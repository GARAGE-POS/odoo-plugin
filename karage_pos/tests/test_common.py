# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class KaragePosTestCommon(TransactionCase):
    """Common test class for Karage POS module"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test company
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Company",
            }
        )

        # Create test user
        cls.user = cls.env["res.users"].create(
            {
                "name": "Test User",
                "login": "test_user",
                "email": "test@example.com",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

        # Create test products
        cls.product1 = cls.env["product.product"].create(
            {
                "name": "Test Product 1",
                "type": "product",
                "sale_ok": True,
                "available_in_pos": True,
                "list_price": 100.0,
            }
        )

        cls.product2 = cls.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "product",
                "sale_ok": True,
                "available_in_pos": True,
                "list_price": 50.0,
            }
        )

        # Create account for payment methods
        cls.account_receivable = cls.env["account.account"].create(
            {
                "name": "Test Receivable",
                "code": "TEST_REC",
                "account_type": "asset_receivable",
                "company_id": cls.company.id,
            }
        )

        cls.account_cash = cls.env["account.account"].create(
            {
                "name": "Test Cash",
                "code": "TEST_CASH",
                "account_type": "asset_cash",
                "company_id": cls.company.id,
            }
        )

        # Create payment journals
        cls.journal_cash = cls.env["account.journal"].create(
            {
                "name": "Cash",
                "type": "cash",
                "code": "CASH",
                "company_id": cls.company.id,
                "default_account_id": cls.account_cash.id,
            }
        )

        cls.journal_card = cls.env["account.journal"].create(
            {
                "name": "Card",
                "type": "bank",
                "code": "CARD",
                "company_id": cls.company.id,
                "default_account_id": cls.account_receivable.id,
            }
        )

        # Create POS config
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "Test POS",
                "company_id": cls.company.id,
                "pricelist_id": cls.env["product.pricelist"]
                .create(
                    {
                        "name": "Test Pricelist",
                        "company_id": cls.company.id,
                    }
                )
                .id,
            }
        )

        # Create payment methods
        cls.payment_method_cash = cls.env["pos.payment.method"].create(
            {
                "name": "Cash",
                "journal_id": cls.journal_cash.id,
                "is_cash_count": True,
            }
        )

        cls.payment_method_card = cls.env["pos.payment.method"].create(
            {
                "name": "Card",
                "journal_id": cls.journal_card.id,
            }
        )

        cls.pos_config.write(
            {
                "payment_method_ids": [
                    (6, 0, [cls.payment_method_cash.id, cls.payment_method_card.id])
                ],
            }
        )

        # Create POS session
        cls.pos_session = cls.env["pos.session"].create(
            {
                "config_id": cls.pos_config.id,
                "user_id": cls.user.id,
            }
        )
        cls.pos_session.action_pos_session_open()

        # Create Karage POS config
        cls.karage_config = cls.env["karage.pos.config"].create(
            {
                "name": "Test Config",
                "api_key": "test_api_key_12345",
                "active": True,
                "odoo_url": "http://localhost:8069",
                "webhook_endpoint": "/api/v1/webhook/pos-order",
            }
        )

        # Sample webhook data
        cls.sample_webhook_data = {
            "OrderID": 12345,
            "AmountDiscount": 0.0,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "BalanceAmount": 0.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderStatus": 103,
            "PaymentMode": 1,
            "CheckoutDetails": [
                {
                    "PaymentMode": 1,
                    "AmountPaid": "100.0",
                    "CardType": "Cash",
                    "ReferenceID": "REF123",
                }
            ],
            "OrderItems": [
                {
                    "ItemID": cls.product1.id,
                    "ItemName": cls.product1.name,
                    "Price": 100.0,
                    "Quantity": 1.0,
                    "DiscountAmount": 0.0,
                }
            ],
        }
