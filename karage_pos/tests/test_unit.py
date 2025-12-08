# -*- coding: utf-8 -*-
"""
Unit tests for Karage POS module.

These tests directly call methods instead of making HTTP requests,
which allows coverage tools to track code execution properly.
"""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from .test_common import KaragePosTestCommon


class MockRequest:
    """Mock Odoo HTTP request object"""

    def __init__(self, env, data=None, headers=None):
        self.env = env
        self._data = data or {}
        self._headers = headers or {}
        self.httprequest = MagicMock()
        self.httprequest.data = json.dumps(self._data).encode('utf-8') if self._data else b''
        self.httprequest.headers = MagicMock()
        self.httprequest.headers.get = lambda key, default=None: self._headers.get(key, default)
        self.httprequest.remote_addr = "127.0.0.1"
        self.httprequest.method = "POST"

    def make_response(self, data, headers=None, status=200):
        """Mock make_response method"""
        return MagicMock(data=data, headers=headers, status_code=status)

    def update_env(self, user=None):
        """Mock update_env method"""
        if user:
            self.env = self.env(user=user)


@tagged("post_install", "-at_install", "api_controller_unit")
class TestAPIControllerUnit(TransactionCase, KaragePosTestCommon):
    """Unit tests for API controller methods"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def setUp(self):
        super().setUp()
        # Import controller class
        from odoo.addons.karage_pos.controllers.api_controller import APIController
        self.controller = APIController()

    def _create_mock_request(self, data=None, headers=None):
        """Create a mock request object"""
        return MockRequest(self.env, data, headers)

    # ========== Tests for _get_header_or_body ==========

    def test_get_header_or_body_from_header(self):
        """Test extracting value from headers"""
        mock_request = self._create_mock_request(
            data={},
            headers={"X-API-KEY": "test-key-123"}
        )

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            result = self.controller._get_header_or_body({}, "X-API-KEY", "api_key")
            self.assertEqual(result, "test-key-123")

    def test_get_header_or_body_from_body(self):
        """Test extracting value from request body"""
        mock_request = self._create_mock_request(
            data={"api_key": "body-key-456"},
            headers={}
        )

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            result = self.controller._get_header_or_body(
                {"api_key": "body-key-456"}, "X-API-KEY", "api_key"
            )
            self.assertEqual(result, "body-key-456")

    def test_get_header_or_body_header_priority(self):
        """Test headers take priority over body"""
        mock_request = self._create_mock_request(
            data={"api_key": "body-key"},
            headers={"X-API-KEY": "header-key"}
        )

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            result = self.controller._get_header_or_body(
                {"api_key": "body-key"}, "X-API-KEY", "api_key"
            )
            self.assertEqual(result, "header-key")

    def test_get_header_or_body_none(self):
        """Test returns None when key not found"""
        mock_request = self._create_mock_request(data={}, headers={})

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            result = self.controller._get_header_or_body({}, "X-API-KEY", "api_key")
            self.assertIsNone(result)

    def test_get_header_or_body_multiple_keys(self):
        """Test with multiple possible keys"""
        mock_request = self._create_mock_request(
            data={"IdempotencyKey": "idem-123"},
            headers={}
        )

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            result = self.controller._get_header_or_body(
                {"IdempotencyKey": "idem-123"},
                "Idempotency-Key", "X-Idempotency-Key", "idempotency_key", "IdempotencyKey"
            )
            self.assertEqual(result, "idem-123")

    # ========== Tests for _parse_request_body ==========

    def test_parse_request_body_valid_json(self):
        """Test parsing valid JSON body"""
        mock_request = self._create_mock_request(
            data={"OrderID": 123, "AmountTotal": 100.0}
        )

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            data, error = self.controller._parse_request_body()
            self.assertIsNone(error)
            self.assertEqual(data["OrderID"], 123)

    def test_parse_request_body_empty(self):
        """Test parsing empty body"""
        mock_request = self._create_mock_request()
        mock_request.httprequest.data = b''

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            data, error = self.controller._parse_request_body()
            self.assertIsNone(data)
            self.assertIn("Request body is required", error)

    def test_parse_request_body_invalid_json(self):
        """Test parsing invalid JSON"""
        mock_request = self._create_mock_request()
        mock_request.httprequest.data = b'not valid json'

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            data, error = self.controller._parse_request_body()
            self.assertIsNone(data)
            self.assertIn("Invalid JSON format", error)

    def test_parse_request_body_unicode_error(self):
        """Test parsing body with unicode error"""
        mock_request = self._create_mock_request()
        mock_request.httprequest.data = b'\xff\xfe'

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            data, error = self.controller._parse_request_body()
            self.assertIsNone(data)
            self.assertIn("Invalid JSON format", error)

    # ========== Tests for _json_response ==========

    def test_json_response_success(self):
        """Test success JSON response"""
        mock_request = self._create_mock_request()

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller._json_response({"id": 1, "name": "test"})

        self.assertEqual(response.status_code, 200)

    def test_json_response_error(self):
        """Test error JSON response"""
        mock_request = self._create_mock_request()

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller._json_response(None, status=400, error="Bad request")

        self.assertEqual(response.status_code, 400)

    def test_json_response_with_list_data(self):
        """Test JSON response with list data"""
        mock_request = self._create_mock_request()

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller._json_response([{"id": 1}, {"id": 2}])

        self.assertEqual(response.status_code, 200)

    # ========== Tests for _authenticate_api_key ==========

    def test_authenticate_api_key_missing(self):
        """Test authentication with missing API key"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            success, error = self.controller._authenticate_api_key(None)

        self.assertFalse(success)
        self.assertIn("Invalid or missing API key", error)

    def test_authenticate_api_key_empty(self):
        """Test authentication with empty API key"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            success, error = self.controller._authenticate_api_key("")

        self.assertFalse(success)
        self.assertIn("Invalid or missing API key", error)

    def test_authenticate_api_key_invalid(self):
        """Test authentication with invalid API key"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            success, error = self.controller._authenticate_api_key("invalid-key")

        self.assertFalse(success)
        self.assertIn("Invalid or missing API key", error)

    # ========== Tests for _create_webhook_log ==========

    def test_create_webhook_log_success(self):
        """Test creating webhook log"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env
        mock_request.httprequest.remote_addr = "192.168.1.1"
        mock_request.httprequest.headers.get = lambda k, d=None: "TestAgent/1.0" if k == "User-Agent" else d
        mock_request.httprequest.method = "POST"

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            log = self.controller._create_webhook_log({"OrderID": 123}, str(uuid.uuid4()))

        self.assertTrue(log.exists() if log else False)

    def test_create_webhook_log_exception(self):
        """Test webhook log creation handles exceptions"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        # Create a log with the same idempotency key first
        duplicate_key = str(uuid.uuid4())
        self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": duplicate_key,
        })

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            # Should handle the duplicate key error gracefully
            log = self.controller._create_webhook_log({"OrderID": 456}, duplicate_key)

        # Should return None when there's an error
        self.assertIsNone(log)

    # ========== Tests for _update_log ==========

    def test_update_log_success(self):
        """Test updating webhook log"""
        log = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "status": "pending",
            "idempotency_key": str(uuid.uuid4()),
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            self.controller._update_log(
                log, 200, "Success", success=True, start_time=datetime.now().timestamp() - 1
            )

        self.assertEqual(log.status_code, 200)
        self.assertTrue(log.success)

    def test_update_log_none(self):
        """Test updating None log (no-op)"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            # Should not raise an error
            self.controller._update_log(None, 200, "Success")

    def test_update_log_with_pos_order(self):
        """Test updating log with POS order reference"""
        log = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "status": "pending",
            "idempotency_key": str(uuid.uuid4()),
        })

        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "lines": [(0, 0, {
                "product_id": self.product1.id,
                "qty": 1,
                "price_unit": 100.0,
                "price_subtotal": 100.0,
                "price_subtotal_incl": 100.0,
            })],
            "payment_ids": [(0, 0, {
                "payment_method_id": self.payment_method_cash.id,
                "amount": 100.0,
            })],
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            self.controller._update_log(log, 200, "Success", success=True, pos_order=pos_order)

        self.assertEqual(log.pos_order_id.id, pos_order.id)

    # ========== Tests for _error_response ==========

    def test_error_response_basic(self):
        """Test basic error response"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller._error_response(400, "Bad request")

        self.assertEqual(response.status_code, 400)

    def test_error_response_with_webhook_log(self):
        """Test error response updates webhook log"""
        log = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "status": "pending",
            "idempotency_key": str(uuid.uuid4()),
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller._error_response(
                400, "Bad request", webhook_log=log, start_time=datetime.now().timestamp()
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(log.status_code, 400)
        self.assertFalse(log.success)

    def test_error_response_with_idempotency_record(self):
        """Test error response marks idempotency as failed"""
        idem_record = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "status": "processing",
            "idempotency_key": "test-idem-error",
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            self.controller._error_response(
                500, "Internal error", idempotency_record=idem_record
            )

        self.assertEqual(idem_record.status, "failed")

    # ========== Tests for _calculate_totals ==========

    def test_calculate_totals_simple(self):
        """Test calculating totals without tax"""
        order_items = [
            {"Price": 100.0, "Quantity": 2, "DiscountAmount": 0.0},
            {"Price": 50.0, "Quantity": 1, "DiscountAmount": 0.0},
        ]

        total, tax = self.controller._calculate_totals(order_items, 0, 0)

        self.assertEqual(total, 250.0)
        self.assertEqual(tax, 0)

    def test_calculate_totals_with_tax_percent(self):
        """Test calculating totals with tax percentage"""
        order_items = [
            {"Price": 100.0, "Quantity": 1, "DiscountAmount": 0.0},
        ]

        total, tax = self.controller._calculate_totals(order_items, 15.0, 0)

        self.assertEqual(total, 115.0)
        self.assertEqual(tax, 15.0)

    def test_calculate_totals_with_flat_tax(self):
        """Test calculating totals with flat tax amount"""
        order_items = [
            {"Price": 100.0, "Quantity": 1, "DiscountAmount": 0.0},
        ]

        total, tax = self.controller._calculate_totals(order_items, 0, 10.0)

        self.assertEqual(total, 110.0)
        self.assertEqual(tax, 10.0)

    def test_calculate_totals_with_discount(self):
        """Test calculating totals with discount"""
        order_items = [
            {"Price": 100.0, "Quantity": 2, "DiscountAmount": 20.0},
        ]

        total, tax = self.controller._calculate_totals(order_items, 0, 0)

        self.assertEqual(total, 180.0)  # (100*2) - 20

    # ========== Tests for _find_product_by_id ==========

    def test_find_product_by_odoo_item_id(self):
        """Test finding product by OdooItemID"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            product, method = self.controller._find_product_by_id(
                self.product1.id, 0, "", self.pos_session
            )

        self.assertEqual(product.id, self.product1.id)
        self.assertEqual(method, "OdooItemID")

    def test_find_product_by_item_id(self):
        """Test finding product by ItemID (legacy)"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            product, method = self.controller._find_product_by_id(
                0, self.product1.id, "", self.pos_session
            )

        self.assertEqual(product.id, self.product1.id)
        self.assertEqual(method, "ItemID")

    def test_find_product_by_name_exact(self):
        """Test finding product by exact name match"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            product, method = self.controller._find_product_by_id(
                0, 0, self.product1.name, self.pos_session
            )

        self.assertEqual(product.id, self.product1.id)
        self.assertEqual(method, "ItemName (exact)")

    def test_find_product_by_name_fuzzy(self):
        """Test finding product by fuzzy name match"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            product, method = self.controller._find_product_by_id(
                0, 0, "Test Product", self.pos_session  # Partial match
            )

        self.assertIsNotNone(product)
        self.assertEqual(method, "ItemName (fuzzy)")

    def test_find_product_not_found(self):
        """Test product not found"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            product, method = self.controller._find_product_by_id(
                99999, 99999, "NonExistent Product XYZ", self.pos_session
            )

        self.assertIsNone(product)
        self.assertIsNone(method)

    def test_find_product_odoo_item_id_not_exists(self):
        """Test when OdooItemID doesn't exist, falls back"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            product, method = self.controller._find_product_by_id(
                99999, self.product1.id, "", self.pos_session
            )

        self.assertEqual(product.id, self.product1.id)
        self.assertEqual(method, "ItemID")

    # ========== Tests for _validate_product_for_pos ==========

    def test_validate_product_for_pos_valid(self):
        """Test validating a valid POS product"""
        error = self.controller._validate_product_for_pos(self.product1, self.pos_session)
        self.assertIsNone(error)

    def test_validate_product_for_pos_none(self):
        """Test validating None product"""
        error = self.controller._validate_product_for_pos(None, self.pos_session)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 404)

    def test_validate_product_for_pos_inactive(self):
        """Test validating inactive product"""
        inactive_product = self.env["product.product"].create({
            "name": "Inactive",
            "active": False,
            "sale_ok": True,
            "available_in_pos": True,
        })

        error = self.controller._validate_product_for_pos(inactive_product, self.pos_session)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 400)
        self.assertIn("not active", error["message"])

    def test_validate_product_for_pos_not_saleable(self):
        """Test validating non-saleable product"""
        non_sale_product = self.env["product.product"].create({
            "name": "Not for Sale",
            "sale_ok": False,
            "available_in_pos": True,
        })

        error = self.controller._validate_product_for_pos(non_sale_product, self.pos_session)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 400)
        self.assertIn("not available for sale", error["message"])

    def test_validate_product_for_pos_not_in_pos(self):
        """Test validating product not available in POS"""
        not_pos_product = self.env["product.product"].create({
            "name": "Not in POS",
            "sale_ok": True,
            "available_in_pos": False,
        })

        error = self.controller._validate_product_for_pos(not_pos_product, self.pos_session)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 400)
        self.assertIn("not available in POS", error["message"])

    def test_validate_product_for_pos_wrong_company(self):
        """Test validating product from wrong company"""
        other_company = self.env["res.company"].create({"name": "Other Company"})
        other_company_product = self.env["product.product"].create({
            "name": "Other Company Product",
            "sale_ok": True,
            "available_in_pos": True,
            "company_id": other_company.id,
        })

        error = self.controller._validate_product_for_pos(other_company_product, self.pos_session)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 400)
        self.assertIn("different company", error["message"])

    # ========== Tests for _get_or_create_external_session ==========

    def test_get_or_create_external_session_existing(self):
        """Test getting existing session"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            session = self.controller._get_or_create_external_session()

        self.assertIsNotNone(session)
        self.assertIn(session.state, ["opened", "opening_control"])

    def test_get_or_create_external_session_creates_new(self):
        """Test creating new session when none exists"""
        # Close all existing sessions
        self.env["pos.session"].search([
            ("state", "in", ["opened", "opening_control"])
        ]).write({"state": "closed", "stop_at": fields.Datetime.now()})

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            session = self.controller._get_or_create_external_session()

        self.assertIsNotNone(session)

    # ========== Tests for _check_idempotency ==========

    def test_check_idempotency_no_key(self):
        """Test idempotency check without key"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                None, "123", None, datetime.now().timestamp()
            )

        self.assertTrue(should_process)
        self.assertIsNone(result)

    def test_check_idempotency_new_request(self):
        """Test idempotency check with new key"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        unique_key = str(uuid.uuid4())
        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                unique_key, "123", None, datetime.now().timestamp()
            )

        self.assertTrue(should_process)
        self.assertIsNotNone(result)

    def test_check_idempotency_completed(self):
        """Test idempotency check with completed request"""
        # Create completed record
        completed_key = str(uuid.uuid4())
        self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": completed_key,
            "status": "completed",
            "response_data": '{"id": 1}',
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                completed_key, "123", None, datetime.now().timestamp()
            )

        self.assertFalse(should_process)

    def test_check_idempotency_processing(self):
        """Test idempotency check with processing request"""
        # Create processing record
        processing_key = str(uuid.uuid4())
        self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": processing_key,
            "status": "processing",
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                processing_key, "123", None, datetime.now().timestamp()
            )

        self.assertFalse(should_process)

    def test_check_idempotency_failed_retry(self):
        """Test idempotency check allows retry of failed request"""
        # Create failed record
        failed_key = str(uuid.uuid4())
        self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": failed_key,
            "status": "failed",
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                failed_key, "123", None, datetime.now().timestamp()
            )

        self.assertTrue(should_process)

    def test_check_idempotency_stuck_processing_timeout(self):
        """Test idempotency allows retry of stuck processing request"""
        # Set short timeout
        self.env["ir.config_parameter"].sudo().set_param(
            "karage_pos.idempotency_processing_timeout", "0"  # 0 minutes = immediate timeout
        )

        # Create old processing record
        stuck_key = str(uuid.uuid4())
        old_record = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": stuck_key,
            "status": "processing",
        })
        # Manually set create_date to the past
        old_date = datetime.now() - timedelta(minutes=10)
        self.env.cr.execute(
            "UPDATE karage_pos_webhook_log SET create_date = %s WHERE id = %s",
            (old_date.strftime("%Y-%m-%d %H:%M:%S"), old_record.id)
        )

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                stuck_key, "123", None, datetime.now().timestamp()
            )

        self.assertTrue(should_process)

    # ========== Tests for _prepare_order_lines ==========

    def test_prepare_order_lines_success(self):
        """Test preparing order lines successfully"""
        order_items = [{
            "OdooItemID": self.product1.id,
            "ItemID": 0,
            "ItemName": self.product1.name,
            "Price": 100.0,
            "Quantity": 2,
            "DiscountAmount": 0.0,
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_order_lines(order_items, self.pos_session)

        self.assertIsNone(error)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0][2]["product_id"], self.product1.id)
        self.assertEqual(lines[0][2]["qty"], 2)

    def test_prepare_order_lines_with_discount(self):
        """Test preparing order lines with discount"""
        order_items = [{
            "OdooItemID": self.product1.id,
            "ItemID": 0,
            "ItemName": self.product1.name,
            "Price": 100.0,
            "Quantity": 1,
            "DiscountAmount": 10.0,
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_order_lines(order_items, self.pos_session)

        self.assertIsNone(error)
        self.assertEqual(lines[0][2]["discount"], 10.0)  # 10% discount

    def test_prepare_order_lines_product_not_found(self):
        """Test preparing order lines with missing product"""
        order_items = [{
            "OdooItemID": 99999,
            "ItemID": 99999,
            "ItemName": "NonExistent",
            "Price": 100.0,
            "Quantity": 1,
            "DiscountAmount": 0.0,
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_order_lines(order_items, self.pos_session)

        self.assertIsNone(lines)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 404)

    def test_prepare_order_lines_empty(self):
        """Test preparing empty order lines"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_order_lines([], self.pos_session)

        self.assertIsNone(lines)
        self.assertIsNotNone(error)
        self.assertIn("No valid order lines", error["message"])

    # ========== Tests for _prepare_payment_lines ==========

    def test_prepare_payment_lines_cash(self):
        """Test preparing cash payment lines"""
        checkout_details = [{
            "PaymentMode": 1,  # Cash
            "AmountPaid": "100.0",
            "CardType": "Cash",
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, self.pos_session, 100.0, 0.01
            )

        self.assertIsNone(error)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0][2]["amount"], 100.0)

    def test_prepare_payment_lines_card(self):
        """Test preparing card payment lines"""
        checkout_details = [{
            "PaymentMode": 2,  # Card
            "AmountPaid": "100.0",
            "CardType": "Card",
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, self.pos_session, 100.0, 0.01
            )

        self.assertIsNone(error)
        self.assertEqual(len(lines), 1)

    def test_prepare_payment_lines_multiple(self):
        """Test preparing multiple payment lines"""
        checkout_details = [
            {"PaymentMode": 1, "AmountPaid": "50.0", "CardType": "Cash"},
            {"PaymentMode": 2, "AmountPaid": "50.0", "CardType": "Card"},
        ]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, self.pos_session, 100.0, 0.01
            )

        self.assertIsNone(error)
        self.assertEqual(len(lines), 2)

    def test_prepare_payment_lines_zero_skipped(self):
        """Test zero amount payments are skipped"""
        checkout_details = [
            {"PaymentMode": 1, "AmountPaid": "0.0", "CardType": "Cash"},
            {"PaymentMode": 1, "AmountPaid": "100.0", "CardType": "Cash"},
        ]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, self.pos_session, 100.0, 0.01
            )

        self.assertIsNone(error)
        self.assertEqual(len(lines), 1)  # Only one valid payment

    def test_prepare_payment_lines_empty(self):
        """Test preparing empty payment lines"""
        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                [], self.pos_session, 100.0, 0.01
            )

        self.assertIsNone(lines)
        self.assertIsNotNone(error)
        self.assertIn("No valid payment lines", error["message"])

    def test_prepare_payment_lines_mismatch(self):
        """Test payment amount mismatch"""
        checkout_details = [{
            "PaymentMode": 1,
            "AmountPaid": "50.0",  # Less than expected
            "CardType": "Cash",
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, self.pos_session, 100.0, 0.01
            )

        self.assertIsNone(lines)
        self.assertIsNotNone(error)
        self.assertIn("Payment inconsistency", error["message"])

    def test_prepare_payment_lines_method_not_found(self):
        """Test payment method not found"""
        checkout_details = [{
            "PaymentMode": 999,  # Unknown mode
            "AmountPaid": "100.0",
            "CardType": "UnknownType",
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, self.pos_session, 100.0, 0.01
            )

        self.assertIsNone(lines)
        self.assertIsNotNone(error)
        self.assertIn("No payment method found", error["message"])

    def test_prepare_payment_lines_with_comma_separator(self):
        """Test amount with comma as thousands separator"""
        checkout_details = [{
            "PaymentMode": 1,
            "AmountPaid": "1,000.0",  # Comma separator
            "CardType": "Cash",
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, self.pos_session, 1000.0, 0.01
            )

        self.assertIsNone(error)
        self.assertEqual(lines[0][2]["amount"], 1000.0)

    # ========== Tests for _process_bulk_orders ==========

    def test_process_bulk_orders_success(self):
        """Test processing bulk orders successfully"""
        orders_data = [{
            "OrderID": 7001,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            results = self.controller._process_bulk_orders(orders_data)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")

    def test_process_bulk_orders_missing_fields(self):
        """Test processing bulk order with missing fields"""
        orders_data = [{
            "OrderID": 7002,
            # Missing required fields
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            results = self.controller._process_bulk_orders(orders_data)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("Missing required fields", results[0]["error"])

    def test_process_bulk_orders_mixed(self):
        """Test processing bulk orders with mixed success/failure"""
        orders_data = [
            {
                "OrderID": 7003,
                "OrderStatus": 103,
                "AmountPaid": "100.0",
                "AmountTotal": 100.0,
                "GrandTotal": 100.0,
                "Tax": 0.0,
                "TaxPercent": 0.0,
                "OrderItems": [{
                    "OdooItemID": self.product1.id,
                    "ItemName": self.product1.name,
                    "Price": 100.0,
                    "Quantity": 1,
                    "DiscountAmount": 0.0,
                }],
                "CheckoutDetails": [{
                    "PaymentMode": 1,
                    "AmountPaid": "100.0",
                    "CardType": "Cash",
                }],
            },
            {
                "OrderID": 7004,
                # Missing required fields - will fail
            },
        ]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            results = self.controller._process_bulk_orders(orders_data)

        self.assertEqual(len(results), 2)
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        self.assertEqual(success_count, 1)
        self.assertEqual(error_count, 1)


@tagged("post_install", "-at_install", "process_order")
class TestProcessPosOrder(TransactionCase, KaragePosTestCommon):
    """Unit tests for _process_pos_order method"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def setUp(self):
        super().setUp()
        from odoo.addons.karage_pos.controllers.api_controller import APIController
        self.controller = APIController()

    def _create_mock_request(self, data=None, headers=None):
        """Create a mock request object"""
        return MockRequest(self.env, data, headers)

    def test_process_pos_order_success(self):
        """Test successful POS order processing"""
        data = {
            "OrderID": 8001,
            "OrderStatus": 103,
            "OrderDate": "2025-11-27T10:00:00",
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "BalanceAmount": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemID": 0,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)
        self.assertEqual(pos_order.external_order_id, "8001")
        self.assertEqual(pos_order.external_order_source, "karage_pos_webhook")

    def test_process_pos_order_duplicate(self):
        """Test duplicate order detection"""
        # Create first order
        self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "8002",
            "external_order_source": "karage_pos_webhook",
            "lines": [(0, 0, {
                "product_id": self.product1.id,
                "qty": 1,
                "price_unit": 100.0,
                "price_subtotal": 100.0,
                "price_subtotal_incl": 100.0,
            })],
            "payment_ids": [(0, 0, {
                "payment_method_id": self.payment_method_cash.id,
                "amount": 100.0,
            })],
        })

        data = {
            "OrderID": 8002,  # Duplicate
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(pos_order)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 400)
        self.assertIn("Duplicate order", error["message"])

    def test_process_pos_order_invalid_status(self):
        """Test invalid order status"""
        self.env["ir.config_parameter"].sudo().set_param(
            "karage_pos.valid_order_statuses", "103"
        )

        data = {
            "OrderID": 8003,
            "OrderStatus": 104,  # Invalid status
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(pos_order)
        self.assertIsNotNone(error)
        self.assertIn("Invalid OrderStatus", error["message"])

    def test_process_pos_order_data_inconsistency(self):
        """Test data inconsistency validation"""
        data = {
            "OrderID": 8004,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 200.0,  # Inconsistent with items
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(pos_order)
        self.assertIsNotNone(error)
        self.assertIn("inconsistency", error["message"])

    def test_process_pos_order_payment_inconsistency(self):
        """Test payment amount inconsistency"""
        data = {
            "OrderID": 8005,
            "OrderStatus": 103,
            "AmountPaid": "50.0",  # Less than total
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "BalanceAmount": 100.0,  # High balance
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "50.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(pos_order)
        self.assertIsNotNone(error)
        self.assertIn("inconsistency", error["message"].lower())

    def test_process_pos_order_no_session(self):
        """Test order processing when no session available"""
        # Close all sessions
        self.env["pos.session"].search([
            ("state", "in", ["opened", "opening_control"])
        ]).write({"state": "closed", "stop_at": fields.Datetime.now()})

        # Delete all POS configs to prevent auto-creation
        self.env["pos.config"].search([]).write({"active": False})

        data = {
            "OrderID": 8006,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(pos_order)
        self.assertIsNotNone(error)
        self.assertIn("No POS configuration", error["message"])

        # Restore POS config
        self.env["pos.config"].search([("active", "=", False)]).write({"active": True})

    def test_process_pos_order_with_tax(self):
        """Test order with tax - webhook prices are tax-inclusive"""
        # Note: Webhook sends final (tax-inclusive) prices
        # Price in OrderItems is the tax-inclusive unit price
        # Tax/TaxPercent should be 0 when prices already include tax
        # (to avoid double-counting in validation)

        data = {
            "OrderID": 8007,
            "OrderStatus": 103,
            "AmountPaid": "115.0",
            "AmountTotal": 115.0,
            "GrandTotal": 115.0,
            "Tax": 0.0,  # 0 because tax is already in Price
            "TaxPercent": 0.0,  # 0 because prices already include tax
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 115.0,  # Tax-inclusive price (base 100 + 15 tax)
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "115.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)
        # Verify order was created with correct tax-inclusive total
        self.assertTrue(pos_order.exists())
        self.assertEqual(pos_order.amount_total, 115.0)

    def test_process_pos_order_with_discount(self):
        """Test order with discount"""
        data = {
            "OrderID": 8008,
            "OrderStatus": 103,
            "AmountPaid": "90.0",
            "AmountTotal": 90.0,
            "GrandTotal": 90.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 10.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "90.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)

    def test_process_pos_order_invalid_order_date(self):
        """Test order with invalid date falls back to current time"""
        data = {
            "OrderID": 8009,
            "OrderStatus": 103,
            "OrderDate": "invalid-date",
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)
        self.assertIsNotNone(pos_order.date_order)

    def test_process_pos_order_with_fiscal_position(self):
        """Test order with fiscal position"""
        fiscal_position = self.env["account.fiscal.position"].create({
            "name": "Test Fiscal Position",
        })
        self.pos_config.write({
            "default_fiscal_position_id": fiscal_position.id,
        })

        data = {
            "OrderID": 8010,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)

    def test_process_pos_order_multiple_items(self):
        """Test order with multiple items"""
        data = {
            "OrderID": 8011,
            "OrderStatus": 103,
            "AmountPaid": "150.0",
            "AmountTotal": 150.0,
            "GrandTotal": 150.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [
                {
                    "OdooItemID": self.product1.id,
                    "ItemName": self.product1.name,
                    "Price": 100.0,
                    "Quantity": 1,
                    "DiscountAmount": 0.0,
                },
                {
                    "OdooItemID": self.product2.id,
                    "ItemName": self.product2.name,
                    "Price": 50.0,
                    "Quantity": 1,
                    "DiscountAmount": 0.0,
                },
            ],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "150.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)
        self.assertEqual(len(pos_order.lines), 2)

    def test_process_pos_order_without_order_status(self):
        """Test order without OrderStatus (should pass)"""
        data = {
            "OrderID": 8012,
            # No OrderStatus
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)


@tagged("post_install", "-at_install")
class TestWebhookLogUnit(TransactionCase, KaragePosTestCommon):
    """Additional unit tests for webhook log model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()
        cls.WebhookLog = cls.env["karage.pos.webhook.log"]

    def test_create_log_with_empty_request_info(self):
        """Test create_log with None request_info"""
        log = self.WebhookLog.create_log(
            webhook_body={"OrderID": 1},
            request_info=None,
        )
        self.assertTrue(log.exists())
        self.assertFalse(log.ip_address)

    def test_get_or_create_log_race_condition(self):
        """Test get_or_create_log handles concurrent access"""
        idempotency_key = f"race-test-key-{uuid.uuid4()}"

        # First call
        record1, created1 = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            order_id="123",
        )

        # Second call with same key
        record2, created2 = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            order_id="123",
        )

        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(record1.id, record2.id)

    def test_update_log_result_all_fields(self):
        """Test update_log_result with all fields"""
        log = self.WebhookLog.create({"webhook_body": "{}"})

        log.update_log_result(
            status_code=200,
            response_message="Success",
            success=True,
            processing_time=1.5,
            response_data='{"id": 1}',
            error_message=None,
            status="completed",
        )

        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.processing_time, 1.5)
        self.assertEqual(log.response_data, '{"id": 1}')
        self.assertEqual(log.status, "completed")
        self.assertIsNotNone(log.processed_at)

    def test_cleanup_old_records_failed_status(self):
        """Test cleanup includes failed records"""
        old_date = datetime.now() - timedelta(days=40)

        old_failed = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "failed",
            "receive_date": old_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

        deleted_count = self.WebhookLog.cleanup_old_records(retention_days=30)

        self.assertGreaterEqual(deleted_count, 1)
        self.assertFalse(old_failed.exists())

    def test_cleanup_stuck_zero_count(self):
        """Test cleanup stuck returns 0 when no stuck records"""
        # Create recent processing record
        self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "processing",
        })

        # Use long timeout so record is not considered stuck
        count = self.WebhookLog.cleanup_stuck_processing_records(timeout_minutes=999)

        # Should not reset recent records
        self.assertEqual(count, 0)


@tagged("post_install", "-at_install", "-standard", "api_controller_coverage")
class TestAPIControllerCoverage(TransactionCase, KaragePosTestCommon):
    """Additional tests for 100% coverage of API controller

    Note: These tests are tagged with -standard to exclude from CI runs
    because they directly call controller methods which return MagicMock
    responses that Odoo's HTTP framework wrapper cannot handle.
    Run locally with: --test-tags=api_controller_coverage
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def setUp(self):
        super().setUp()
        from odoo.addons.karage_pos.controllers.api_controller import APIController
        self.controller = APIController()

    def _create_mock_request(self, data=None, headers=None, method="POST"):
        """Create a mock request object with configurable method"""
        mock_req = MockRequest(self.env, data, headers)
        mock_req.httprequest.method = method
        return mock_req

    # ========== Tests for webhook_pos_order method not allowed ==========

    def test_webhook_pos_order_method_not_allowed(self):
        """Test webhook_pos_order returns 405 for GET request"""
        mock_request = self._create_mock_request(method="GET")
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order()

        self.assertEqual(response.status_code, 405)

    # ========== Tests for webhook_pos_order exception handling ==========

    def test_webhook_pos_order_unexpected_exception(self):
        """Test webhook_pos_order handles unexpected exceptions"""
        mock_request = self._create_mock_request(
            data={"OrderID": 9001},
            headers={"X-API-KEY": "test-key"}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            with patch.object(self.controller, '_parse_request_body', side_effect=RuntimeError("Test error")):
                response = self.controller.webhook_pos_order()

        self.assertEqual(response.status_code, 500)

    # ========== Tests for idempotency record update exception ==========

    def test_webhook_pos_order_idempotency_update_exception(self):
        """Test webhook_pos_order handles idempotency update exception"""
        data = {
            "OrderID": 9002,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        # Create idempotency record
        idem_key = "test-idem-update-exception"
        idem_record = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": idem_key,
            "status": "processing",
        })

        mock_request = self._create_mock_request(
            data=data,
            headers={"X-API-KEY": self.api_key, "Idempotency-Key": idem_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            # Mock mark_completed to raise exception
            with patch.object(idem_record, 'mark_completed', side_effect=Exception("DB error")):
                # Need to mock get_or_create_log to return our record
                with patch.object(
                    self.env["karage.pos.webhook.log"].__class__, 'get_or_create_log',
                    return_value=(idem_record, True)
                ):
                    response = self.controller.webhook_pos_order()

        # Should still succeed - the exception is caught and logged
        self.assertEqual(response.status_code, 200)

    # ========== Tests for webhook_pos_order_bulk endpoint ==========

    def test_webhook_pos_order_bulk_method_not_allowed(self):
        """Test bulk endpoint returns 405 for GET request"""
        mock_request = self._create_mock_request(method="GET")
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 405)

    def test_webhook_pos_order_bulk_parse_error(self):
        """Test bulk endpoint handles parse errors"""
        mock_request = self._create_mock_request()
        mock_request.httprequest.data = b'not valid json'
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 400)

    def test_webhook_pos_order_bulk_auth_error(self):
        """Test bulk endpoint handles auth errors"""
        mock_request = self._create_mock_request(
            data={"orders": []},
            headers={"X-API-KEY": "invalid-key"}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 401)

    def test_webhook_pos_order_bulk_missing_orders_field(self):
        """Test bulk endpoint validates orders field"""
        mock_request = self._create_mock_request(
            data={"not_orders": []},
            headers={"X-API-KEY": self.api_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 400)

    def test_webhook_pos_order_bulk_orders_not_array(self):
        """Test bulk endpoint validates orders is array"""
        mock_request = self._create_mock_request(
            data={"orders": "not an array"},
            headers={"X-API-KEY": self.api_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 400)

    def test_webhook_pos_order_bulk_too_many_orders(self):
        """Test bulk endpoint enforces max orders limit"""
        # Set very low limit
        self.env["ir.config_parameter"].sudo().set_param(
            "karage_pos.bulk_sync_max_orders", "2"
        )

        mock_request = self._create_mock_request(
            data={"orders": [{}, {}, {}, {}]},  # 4 orders, limit is 2
            headers={"X-API-KEY": self.api_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 400)

    def test_webhook_pos_order_bulk_success(self):
        """Test bulk endpoint processes orders successfully"""
        orders_data = [{
            "OrderID": 9100,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }]

        mock_request = self._create_mock_request(
            data={"orders": orders_data},
            headers={"X-API-KEY": self.api_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 200)

    def test_webhook_pos_order_bulk_partial_success(self):
        """Test bulk endpoint returns 207 for partial success"""
        orders_data = [
            {
                "OrderID": 9101,
                "OrderStatus": 103,
                "AmountPaid": "100.0",
                "AmountTotal": 100.0,
                "GrandTotal": 100.0,
                "Tax": 0.0,
                "TaxPercent": 0.0,
                "OrderItems": [{
                    "OdooItemID": self.product1.id,
                    "ItemName": self.product1.name,
                    "Price": 100.0,
                    "Quantity": 1,
                    "DiscountAmount": 0.0,
                }],
                "CheckoutDetails": [{
                    "PaymentMode": 1,
                    "AmountPaid": "100.0",
                    "CardType": "Cash",
                }],
            },
            {
                "OrderID": 9102,
                # Missing required fields - will fail
            },
        ]

        mock_request = self._create_mock_request(
            data={"orders": orders_data},
            headers={"X-API-KEY": self.api_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        # Response is always 200 but contains partial_success status
        self.assertEqual(response.status_code, 200)

    def test_webhook_pos_order_bulk_all_fail(self):
        """Test bulk endpoint when all orders fail"""
        orders_data = [
            {"OrderID": 9103},  # Missing required fields
            {"OrderID": 9104},  # Missing required fields
        ]

        mock_request = self._create_mock_request(
            data={"orders": orders_data},
            headers={"X-API-KEY": self.api_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 200)  # Status in data

    def test_webhook_pos_order_bulk_exception(self):
        """Test bulk endpoint handles unexpected exception"""
        mock_request = self._create_mock_request(
            data={"orders": []},
            headers={"X-API-KEY": self.api_key}
        )
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            with patch.object(self.controller, '_process_bulk_orders', side_effect=RuntimeError("Test error")):
                response = self.controller.webhook_pos_order_bulk()

        self.assertEqual(response.status_code, 500)

    # ========== Tests for _process_bulk_orders exception handling ==========

    def test_process_bulk_orders_order_exception(self):
        """Test _process_bulk_orders handles per-order exceptions"""
        orders_data = [{
            "OrderID": 9200,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            with patch.object(self.controller, '_process_pos_order', side_effect=Exception("Order error")):
                results = self.controller._process_bulk_orders(orders_data)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("Order error", results[0]["error"])

    # ========== Tests for payment method validation ==========

    def test_process_pos_order_no_payment_methods(self):
        """Test _process_pos_order handles no payment methods"""
        # Remove all payment methods from the POS config
        self.pos_session.payment_method_ids.write({"active": False})

        data = {
            "OrderID": 9300,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(pos_order)
        self.assertIsNotNone(error)
        self.assertIn("No payment method", error["message"])

        # Restore payment methods
        self.env["pos.payment.method"].search([("active", "=", False)]).write({"active": True})

    def test_process_pos_order_payment_method_no_journal(self):
        """Test _process_pos_order handles payment method without journal"""
        # Create payment method without journal
        no_journal_method = self.env["pos.payment.method"].create({
            "name": "No Journal Method",
            "company_id": self.company.id,
            "is_cash_count": False,
        })
        self.pos_config.write({
            "payment_method_ids": [(4, no_journal_method.id)],
        })

        data = {
            "OrderID": 9301,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            pos_order, error = self.controller._process_pos_order(data)

        # Either returns error or succeeds with other payment method
        # Depends on implementation - checking it doesn't crash

    # ========== Tests for picking creation exception ==========

    def test_process_pos_order_picking_creation_exception(self):
        """Test _process_pos_order handles picking creation exception"""
        data = {
            "OrderID": 9400,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            # Mock _create_order_picking to raise exception
            with patch.object(
                self.env["pos.order"].__class__, '_create_order_picking',
                side_effect=Exception("Picking error")
            ):
                pos_order, error = self.controller._process_pos_order(data)

        # Should still succeed - picking error is logged but order is created
        self.assertIsNone(error)
        self.assertIsNotNone(pos_order)

    # ========== Tests for fallback POS config search ==========

    def test_get_or_create_external_session_fallback_search(self):
        """Test _get_or_create_external_session uses fallback config"""
        # Close all sessions and rename configs so they don't match external patterns
        self.env["pos.session"].search([
            ("state", "in", ["opened", "opening_control"])
        ]).write({"state": "closed", "stop_at": fields.Datetime.now()})

        # Rename all configs to not match external patterns
        self.env["pos.config"].search([]).write({"name": "Regular POS"})

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            session = self.controller._get_or_create_external_session()

        # Should still find a session using fallback
        self.assertIsNotNone(session)

    def test_get_or_create_external_session_existing_for_config(self):
        """Test _get_or_create_external_session finds existing session for config"""
        # Rename config to not match external patterns, but create open session
        self.pos_config.write({"name": "Regular POS"})

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            session = self.controller._get_or_create_external_session()

        self.assertIsNotNone(session)

    def test_get_or_create_external_session_creation_exception(self):
        """Test _get_or_create_external_session handles creation exception"""
        # Close all sessions
        self.env["pos.session"].search([
            ("state", "in", ["opened", "opening_control"])
        ]).write({"state": "closed", "stop_at": fields.Datetime.now()})

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            # Mock session creation to raise exception
            with patch.object(
                self.env["pos.session"].__class__, 'create',
                side_effect=Exception("Session creation error")
            ):
                session = self.controller._get_or_create_external_session()

        # Should return None when creation fails
        self.assertIsNone(session)

    # ========== Tests for idempotency edge cases ==========

    def test_check_idempotency_completed_invalid_cached_response(self):
        """Test idempotency with invalid cached response data"""
        # Create completed record with invalid JSON
        invalid_json_key = str(uuid.uuid4())
        self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": invalid_json_key,
            "status": "completed",
            "response_data": "not valid json",
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                invalid_json_key, "123", None, datetime.now().timestamp()
            )

        # Should return fallback response
        self.assertFalse(should_process)

    def test_check_idempotency_completed_no_cached_response(self):
        """Test idempotency with no cached response data"""
        # Create completed record without response_data
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "lines": [(0, 0, {
                "product_id": self.product1.id,
                "qty": 1,
                "price_unit": 100.0,
                "price_subtotal": 100.0,
                "price_subtotal_incl": 100.0,
            })],
            "payment_ids": [(0, 0, {
                "payment_method_id": self.payment_method_cash.id,
                "amount": 100.0,
            })],
        })

        no_cached_key = str(uuid.uuid4())
        self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": no_cached_key,
            "status": "completed",
            "response_data": None,
            "pos_order_id": pos_order.id,
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                no_cached_key, "123", None, datetime.now().timestamp()
            )

        # Should return fallback response
        self.assertFalse(should_process)

    # ========== Tests for _update_log exception handling ==========

    def test_update_log_exception(self):
        """Test _update_log handles exceptions gracefully"""
        log = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "status": "pending",
            "idempotency_key": str(uuid.uuid4()),
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            # Mock update_log_result to raise exception
            with patch.object(log, 'update_log_result', side_effect=Exception("DB error")):
                # Should not raise - just logs warning
                self.controller._update_log(log, 200, "Success")

    # ========== Tests for _error_response with idempotency exception ==========

    def test_error_response_idempotency_exception(self):
        """Test _error_response handles idempotency record exception"""
        idem_record = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "status": "processing",
            "idempotency_key": str(uuid.uuid4()),
        })

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            # Mock mark_failed to raise exception
            with patch.object(idem_record, 'mark_failed', side_effect=Exception("DB error")):
                response = self.controller._error_response(
                    500, "Internal error", idempotency_record=idem_record
                )

        self.assertEqual(response.status_code, 500)

    # ========== Tests for _prepare_payment_lines edge cases ==========

    def test_prepare_payment_lines_journal_not_found(self):
        """Test _prepare_payment_lines handles journal not found"""
        # Create payment method without journal
        no_journal_method = self.env["pos.payment.method"].create({
            "name": "Special Method",
            "company_id": self.company.id,
            "is_cash_count": False,
        })

        # Create a session with only this payment method
        test_config = self.env["pos.config"].create({
            "name": "Test Config No Journal",
            "journal_id": self.cash_journal.id,
            "payment_method_ids": [(6, 0, [no_journal_method.id])],
        })

        test_session = self.env["pos.session"].create({
            "config_id": test_config.id,
            "user_id": self.env.user.id,
        })

        checkout_details = [{
            "PaymentMode": 999,  # Unknown mode, will use method found
            "AmountPaid": "100.0",
            "CardType": "Special",
        }]

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            lines, error = self.controller._prepare_payment_lines(
                checkout_details, test_session, 100.0, 0.01
            )

        # Should return error since no payment method found
        self.assertIsNone(lines)
        self.assertIsNotNone(error)

    # ========== Additional edge case tests ==========

    def test_process_pos_order_general_exception(self):
        """Test _process_pos_order handles general exception"""
        data = {
            "OrderID": 9500,
            "OrderStatus": 103,
            "AmountPaid": "100.0",
            "AmountTotal": 100.0,
            "GrandTotal": 100.0,
            "Tax": 0.0,
            "TaxPercent": 0.0,
            "OrderItems": [{
                "OdooItemID": self.product1.id,
                "ItemName": self.product1.name,
                "Price": 100.0,
                "Quantity": 1,
                "DiscountAmount": 0.0,
            }],
            "CheckoutDetails": [{
                "PaymentMode": 1,
                "AmountPaid": "100.0",
                "CardType": "Cash",
            }],
        }

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            with patch.object(
                self.controller, '_get_or_create_external_session',
                side_effect=Exception("Unexpected error")
            ):
                pos_order, error = self.controller._process_pos_order(data)

        self.assertIsNone(pos_order)
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 500)

    def test_check_idempotency_processing_no_create_date(self):
        """Test idempotency processing without create_date"""
        # Create processing record and set create_date to None via SQL
        no_date_key = str(uuid.uuid4())
        record = self.env["karage.pos.webhook.log"].create({
            "webhook_body": "{}",
            "idempotency_key": no_date_key,
            "status": "processing",
        })
        self.env.cr.execute(
            "UPDATE karage_pos_webhook_log SET create_date = NULL WHERE id = %s",
            (record.id,)
        )

        mock_request = self._create_mock_request()
        mock_request.env = self.env

        with patch('odoo.addons.karage_pos.controllers.api_controller.request', mock_request):
            should_process, result = self.controller._check_idempotency(
                no_date_key, "123", None, datetime.now().timestamp()
            )

        # Should return processing error
        self.assertFalse(should_process)
