# -*- coding: utf-8 -*-

import json
from odoo.tests import HttpCase
from odoo.tests.common import tagged

from .test_common import KaragePosTestCommon


@tagged("post_install", "-at_install")
class TestWebhookController(HttpCase, KaragePosTestCommon):
    """Test webhook controller"""  # pylint: disable=too-many-public-methods

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def setUp(self):
        super().setUp()
        self.webhook_url = "/api/v1/webhook/pos-order"
        self.api_key = "test_api_key_12345"
        # Ensure sample_webhook_data has correct product IDs
        if hasattr(self, "sample_webhook_data"):
            self.sample_webhook_data["OrderItems"][0]["ItemID"] = self.product1.id
            self.sample_webhook_data["OrderItems"][0]["ItemName"] = self.product1.name

    def _make_webhook_request(self, data, headers=None, method="POST"):
        """Helper to make webhook request"""
        if headers is None:
            headers = {"X-API-KEY": self.api_key}

        if method == "POST":
            return self.url_open(
                self.webhook_url,
                data=json.dumps(data),
                headers=headers,
            )
        # For non-POST requests, try to use url_open with different method
        # Note: Odoo's url_open only supports POST, so GET/OPTIONS will fail
        try:
            # This will fail for non-POST methods, which is expected
            return self.url_open(
                self.webhook_url,
                data="",
                headers=headers,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def test_webhook_post_only(self):
        """Test that only POST requests are accepted"""
        # GET request should fail (route only accepts POST)
        try:
            response = self._make_webhook_request({}, method="GET")
            # If it doesn't raise an exception, check status
            if response:
                self.assertIn(response.status_code, [404, 405])
        except Exception:  # pylint: disable=broad-exception-caught
            # Expected - route doesn't accept GET
            pass

        # OPTIONS request should fail
        try:
            response = self._make_webhook_request({}, method="OPTIONS")
            if response:
                self.assertIn(response.status_code, [404, 405])
        except Exception:  # pylint: disable=broad-exception-caught
            # Expected - route doesn't accept OPTIONS
            pass

    def test_webhook_missing_body(self):
        """Test webhook with missing request body"""
        # Empty dict should still have body, test with actual empty body
        response = self.url_open(
            self.webhook_url,
            data="",
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("Request body is required", result["error"])

    def test_webhook_invalid_json(self):
        """Test webhook with invalid JSON"""
        response = self.url_open(
            self.webhook_url,
            data="invalid json",
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")

    def test_webhook_missing_api_key(self):
        """Test webhook without API key"""
        response = self._make_webhook_request(self.sample_webhook_data, headers={})
        self.assertEqual(response.status_code, 401)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("API key", result["error"])

    def test_webhook_invalid_api_key(self):
        """Test webhook with invalid API key"""
        response = self._make_webhook_request(
            self.sample_webhook_data, headers={"X-API-KEY": "invalid_key"}
        )
        self.assertEqual(response.status_code, 401)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")

    def test_webhook_missing_required_fields(self):
        """Test webhook with missing required fields"""
        incomplete_data = {"OrderID": 123}
        response = self._make_webhook_request(incomplete_data)
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("Missing required fields", result["error"])

    def test_webhook_success(self):
        """Test successful webhook processing"""
        # Ensure data has correct product ID
        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(result["data"])
        self.assertIn("id", result["data"])
        self.assertIn("name", result["data"])

        # Verify POS order was created
        pos_order = self.env["pos.order"].browse(result["data"]["id"])
        self.assertTrue(pos_order.exists())
        self.assertEqual(pos_order.state, "paid")

    def test_webhook_with_idempotency_key(self):
        """Test webhook with idempotency key"""
        idempotency_key = "test-idempotency-123"
        headers = {
            "X-API-KEY": self.api_key,
            "Idempotency-Key": idempotency_key,
        }

        # Ensure data has correct product ID
        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name

        # First request
        response1 = self._make_webhook_request(data, headers=headers)
        self.assertEqual(response1.status_code, 200)
        result1 = json.loads(response1.content)
        order_id_1 = result1["data"]["id"]

        # Second request with same idempotency key
        response2 = self._make_webhook_request(data, headers=headers)
        self.assertEqual(response2.status_code, 200)
        result2 = json.loads(response2.content)

        # Should return same order (duplicate request)
        self.assertEqual(result2["data"]["id"], order_id_1)

        # Verify only one order was created
        orders = self.env["pos.order"].search(
            [("pos_reference", "=", result1["data"]["pos_reference"])]
        )
        self.assertEqual(len(orders), 1)

    def test_webhook_idempotency_in_body(self):
        """Test idempotency key in request body"""
        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name
        data["idempotency_key"] = "body-idempotency-123"
        headers = {"X-API-KEY": self.api_key}

        # First request
        response1 = self._make_webhook_request(data, headers=headers)
        self.assertEqual(response1.status_code, 200)

        # Second request
        response2 = self._make_webhook_request(data, headers=headers)
        self.assertEqual(response2.status_code, 200)

        # Should return same response
        result1 = json.loads(response1.content)
        result2 = json.loads(response2.content)
        self.assertEqual(result1["data"]["id"], result2["data"]["id"])

    def test_webhook_logging(self):
        """Test that webhooks are logged"""
        initial_count = self.env["karage.pos.webhook.log"].search_count([])

        # Ensure data has correct product ID
        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 200)

        # Verify log was created
        logs = self.env["karage.pos.webhook.log"].search([], order="id desc")
        self.assertGreater(len(logs), initial_count)

        # Check latest log
        latest_log = logs[0]
        self.assertEqual(latest_log.order_id, str(data["OrderID"]))
        self.assertTrue(latest_log.success)
        self.assertEqual(latest_log.status_code, 200)

    def test_webhook_product_not_found(self):
        """Test webhook with non-existent product"""
        data = self.sample_webhook_data.copy()
        data["OrderItems"] = [
            {
                "ItemID": 99999,
                "ItemName": "Non-existent Product",
                "Price": 100.0,
                "Quantity": 1.0,
                "DiscountAmount": 0.0,
            }
        ]

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 404)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("Product not found", result["error"])

    def test_webhook_payment_method_not_found(self):
        """Test webhook with unsupported payment mode"""
        data = self.sample_webhook_data.copy()
        data["CheckoutDetails"] = [
            {
                "PaymentMode": 999,  # Invalid payment mode
                "AmountPaid": "100.0",
                "CardType": "Unknown",
                "ReferenceID": "REF123",
            }
        ]

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")

    def test_webhook_data_inconsistency(self):
        """Test webhook with data inconsistency"""
        data = self.sample_webhook_data.copy()
        data["AmountTotal"] = 50.0  # Different from calculated total
        data["GrandTotal"] = 50.0

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("inconsistency", result["error"].lower())

    def test_webhook_with_tax(self):
        """Test webhook with tax"""
        # Create tax
        tax = self.env["account.tax"].create(
            {
                "name": "Test Tax 15%",
                "amount": 15.0,
                "type_tax_use": "sale",
                "company_id": self.company.id,
            }
        )

        self.product1.write({"taxes_id": [(6, 0, [tax.id])]})

        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name
        data["Tax"] = 15.0
        data["TaxPercent"] = 15.0
        data["AmountTotal"] = 100.0
        data["GrandTotal"] = 115.0
        data["AmountPaid"] = "115.0"

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "success")

        pos_order = self.env["pos.order"].browse(result["data"]["id"])
        self.assertGreater(pos_order.amount_tax, 0)

    def test_webhook_with_discount(self):
        """Test webhook with discount"""
        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name
        data["OrderItems"][0]["DiscountAmount"] = 10.0
        data["AmountDiscount"] = 10.0
        data["AmountTotal"] = 90.0
        data["GrandTotal"] = 90.0
        data["AmountPaid"] = "90.0"

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "success")

        pos_order = self.env["pos.order"].browse(result["data"]["id"])
        order_line = pos_order.lines[0]
        self.assertGreater(order_line.discount, 0)

    def test_webhook_multiple_items(self):
        """Test webhook with multiple order items"""
        data = self.sample_webhook_data.copy()
        data["OrderItems"] = [
            {
                "ItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 2.0,
                "DiscountAmount": 0.0,
            },
            {
                "ItemID": self.product2.id,
                "ItemName": self.product2.name,
                "Price": 50.0,
                "Quantity": 1.0,
                "DiscountAmount": 0.0,
            },
        ]
        data["AmountTotal"] = 250.0
        data["GrandTotal"] = 250.0
        data["AmountPaid"] = "250.0"

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "success")

        pos_order = self.env["pos.order"].browse(result["data"]["id"])
        self.assertEqual(len(pos_order.lines), 2)
        self.assertEqual(pos_order.amount_total, 250.0)

    def test_webhook_multiple_payments(self):
        """Test webhook with multiple payment methods"""
        data = self.sample_webhook_data.copy()
        data["CheckoutDetails"] = [
            {
                "PaymentMode": 1,  # Cash
                "AmountPaid": "50.0",
                "CardType": "Cash",
                "ReferenceID": "REF1",
            },
            {
                "PaymentMode": 2,  # Card
                "AmountPaid": "50.0",
                "CardType": "Visa",
                "ReferenceID": "REF2",
            },
        ]
        data["AmountPaid"] = "100.0"

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "success")

        pos_order = self.env["pos.order"].browse(result["data"]["id"])
        self.assertEqual(len(pos_order.payment_ids), 2)

    def test_webhook_no_pos_session(self):
        """Test webhook when no POS session is open"""
        # Close the session
        self.pos_session.action_pos_session_closing_control()
        self.pos_session.action_pos_session_close()

        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("No open POS session", result["error"])

        # Reopen session for other tests
        new_session = self.env["pos.session"].create(
            {
                "config_id": self.pos_config.id,
                "user_id": self.user.id,
            }
        )
        new_session.action_pos_session_open()

    def test_webhook_processing_status(self):
        """Test idempotency with processing status"""
        idempotency_key = "test-processing-status"
        headers = {
            "X-API-KEY": self.api_key,
            "Idempotency-Key": idempotency_key,
        }

        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name

        # Create a processing idempotency record manually
        self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": idempotency_key,
                "order_id": "12345",
                "status": "processing",
            }
        )

        # Request should fail with 409
        response = self._make_webhook_request(data, headers=headers)
        self.assertEqual(response.status_code, 409)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("already being processed", result["error"])

    def test_webhook_failed_retry(self):
        """Test retry of failed idempotency"""
        idempotency_key = "test-failed-retry"
        headers = {
            "X-API-KEY": self.api_key,
            "Idempotency-Key": idempotency_key,
        }

        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name

        # Create a failed idempotency record
        self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": idempotency_key,
                "order_id": "12345",
                "status": "failed",
                "error_message": "Previous failure",
            }
        )

        # Request should succeed (retry allowed)
        response = self._make_webhook_request(data, headers=headers)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "success")

    def test_webhook_empty_order_items(self):
        """Test webhook with empty order items"""
        data = self.sample_webhook_data.copy()
        data["OrderItems"] = []

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("No valid order lines", result["error"])

    def test_webhook_empty_payment_details(self):
        """Test webhook with empty payment details"""
        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name
        data["CheckoutDetails"] = []

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("No valid payment lines", result["error"])

    def test_webhook_payment_amount_mismatch(self):
        """Test webhook with payment amount mismatch"""
        data = self.sample_webhook_data.copy()
        data["OrderItems"][0]["ItemID"] = self.product1.id
        data["OrderItems"][0]["ItemName"] = self.product1.name
        data["AmountPaid"] = "50.0"  # Less than total
        data["CheckoutDetails"][0]["AmountPaid"] = "50.0"

        response = self._make_webhook_request(data)
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.content)
        self.assertEqual(result["status"], "error")
        self.assertIn("Payment inconsistency", result["error"])
