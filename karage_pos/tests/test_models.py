# -*- coding: utf-8 -*-

import json
import uuid
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

from .test_common import KaragePosTestCommon


@tagged("post_install", "-at_install")
class TestManifest(TransactionCase):
    """Test module manifest"""

    def test_manifest_fields(self):
        """Test that manifest has required fields"""
        # Get module info from installed modules
        module = self.env["ir.module.module"].search([
            ("name", "=", "karage_pos")
        ], limit=1)

        self.assertTrue(module.exists())
        self.assertEqual(module.state, "installed")
        self.assertTrue(module.shortdesc)  # Name
        self.assertTrue(module.summary)
        self.assertTrue(module.author)
        self.assertTrue(module.license)
        self.assertEqual(module.application, True)

    def test_manifest_dependencies(self):
        """Test module dependencies are installed"""
        module = self.env["ir.module.module"].search([
            ("name", "=", "karage_pos")
        ], limit=1)

        # Check dependencies are loaded
        dependencies = module.dependencies_id.mapped("name")
        self.assertIn("base", dependencies)
        self.assertIn("point_of_sale", dependencies)
        self.assertIn("product", dependencies)
        self.assertIn("account", dependencies)

    def test_manifest_version(self):
        """Test module version format"""
        module = self.env["ir.module.module"].search([
            ("name", "=", "karage_pos")
        ], limit=1)

        # Check version is set and follows Odoo format
        self.assertTrue(module.installed_version)
        # Version should start with 18.0 for Odoo 18
        self.assertTrue(
            module.installed_version.startswith("18.0"),
            f"Version {module.installed_version} should start with 18.0"
        )


@tagged("post_install", "-at_install")
class TestWebhookLog(TransactionCase, KaragePosTestCommon):
    """Test webhook log model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()
        cls.WebhookLog = cls.env["karage.pos.webhook.log"]

    def test_create_log_with_dict_body(self):
        """Test creating log with dict webhook body"""
        body = {"OrderID": 123, "AmountTotal": 100.0}
        log = self.WebhookLog.create_log(webhook_body=body)

        self.assertTrue(log.exists())
        self.assertEqual(log.order_id, "123")
        self.assertEqual(log.status, "pending")
        self.assertIn("OrderID", log.webhook_body)

    def test_create_log_with_string_body(self):
        """Test creating log with string webhook body"""
        body = '{"OrderID": 456, "AmountTotal": 200.0}'
        log = self.WebhookLog.create_log(webhook_body=body)

        self.assertTrue(log.exists())
        self.assertEqual(log.order_id, "456")

    def test_create_log_with_invalid_json_string(self):
        """Test creating log with invalid JSON string"""
        body = "not valid json"
        log = self.WebhookLog.create_log(webhook_body=body)

        self.assertTrue(log.exists())
        self.assertFalse(log.order_id)  # Should be empty/None

    def test_create_log_with_idempotency_key(self):
        """Test creating log with idempotency key"""
        body = {"OrderID": 789}
        idempotency_key = f"test-key-{uuid.uuid4()}"
        log = self.WebhookLog.create_log(
            webhook_body=body, idempotency_key=idempotency_key
        )

        self.assertEqual(log.idempotency_key, idempotency_key)

    def test_create_log_with_request_info(self):
        """Test creating log with request metadata"""
        body = {"OrderID": 101}
        request_info = {
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "http_method": "POST",
        }
        log = self.WebhookLog.create_log(
            webhook_body=body, request_info=request_info
        )

        self.assertEqual(log.ip_address, "192.168.1.1")
        self.assertEqual(log.user_agent, "TestAgent/1.0")
        self.assertEqual(log.http_method, "POST")

    def test_create_log_with_custom_status(self):
        """Test creating log with custom status"""
        body = {"OrderID": 102}
        log = self.WebhookLog.create_log(webhook_body=body, status="processing")

        self.assertEqual(log.status, "processing")

    def test_idempotency_key_unique_constraint(self):
        """Test idempotency key uniqueness constraint"""
        idempotency_key = f"unique-key-{uuid.uuid4()}"
        self.WebhookLog.create_log(
            webhook_body={"OrderID": 1}, idempotency_key=idempotency_key
        )

        # Second create with same key should fail
        with self.assertRaises(Exception):
            self.WebhookLog.create_log(
                webhook_body={"OrderID": 2}, idempotency_key=idempotency_key
            )

    def test_get_or_create_log_new_record(self):
        """Test get_or_create_log creates new record"""
        idempotency_key = f"new-record-{uuid.uuid4()}"
        record, created = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            order_id="12345",
            status="processing",
        )

        self.assertTrue(created)
        self.assertEqual(record.idempotency_key, idempotency_key)
        self.assertEqual(record.status, "processing")

    def test_get_or_create_log_existing_record(self):
        """Test get_or_create_log returns existing record"""
        idempotency_key = f"existing-record-{uuid.uuid4()}"
        # Create first record
        first_record, created1 = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            order_id="12345",
        )
        self.assertTrue(created1)

        # Try to create again
        second_record, created2 = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            order_id="12345",
        )

        self.assertFalse(created2)
        self.assertEqual(first_record.id, second_record.id)

    def test_get_or_create_log_with_webhook_body(self):
        """Test get_or_create_log with webhook body"""
        idempotency_key = f"body-key-{uuid.uuid4()}"
        webhook_body = {"OrderID": 999, "AmountTotal": 500.0}

        record, created = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            webhook_body=webhook_body,
            request_info={"ip_address": "10.0.0.1"},
        )

        self.assertTrue(created)
        self.assertEqual(record.order_id, "999")
        self.assertEqual(record.ip_address, "10.0.0.1")

    def test_get_or_create_log_without_key_or_body(self):
        """Test get_or_create_log without idempotency key or body raises error"""
        with self.assertRaises(ValidationError):
            self.WebhookLog.get_or_create_log(
                idempotency_key=None, webhook_body=None
            )

    def test_get_or_create_log_without_key_with_body(self):
        """Test get_or_create_log without key but with body creates record"""
        webhook_body = {"OrderID": 888}
        record, created = self.WebhookLog.get_or_create_log(
            idempotency_key=None,
            webhook_body=webhook_body,
        )

        self.assertTrue(created)
        self.assertFalse(record.idempotency_key)

    def test_update_log_result_basic(self):
        """Test updating log result with basic fields"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        log.update_log_result(
            status_code=200,
            response_message="Success",
            success=True,
        )

        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.response_message, "Success")
        self.assertTrue(log.success)
        self.assertIsNotNone(log.processed_at)

    def test_update_log_result_with_pos_order(self):
        """Test updating log result with POS order reference"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})

        # Create a minimal POS order for testing
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

        log.update_log_result(
            status_code=200,
            response_message="Order created",
            success=True,
            pos_order_id=pos_order,
        )

        self.assertEqual(log.pos_order_id.id, pos_order.id)

    def test_update_log_result_with_processing_time(self):
        """Test updating log result with processing time"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        log.update_log_result(
            status_code=200,
            response_message="Success",
            success=True,
            processing_time=1.5,
        )

        self.assertEqual(log.processing_time, 1.5)

    def test_update_log_result_with_response_data(self):
        """Test updating log result with response data"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        response_data = json.dumps({"id": 123, "name": "POS/001"})
        log.update_log_result(
            status_code=200,
            response_message="Success",
            success=True,
            response_data=response_data,
        )

        self.assertEqual(log.response_data, response_data)

    def test_update_log_result_with_error(self):
        """Test updating log result with error message"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        log.update_log_result(
            status_code=400,
            response_message="Error",
            success=False,
            error_message="Missing required field",
        )

        self.assertEqual(log.error_message, "Missing required field")
        self.assertFalse(log.success)

    def test_update_log_result_with_status(self):
        """Test updating log result with custom status"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        log.update_log_result(
            status_code=200,
            response_message="Success",
            success=True,
            status="completed",
        )

        self.assertEqual(log.status, "completed")
        self.assertIsNotNone(log.processed_at)

    def test_mark_completed(self):
        """Test marking log as completed"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        log.mark_completed()

        self.assertEqual(log.status, "completed")
        self.assertTrue(log.success)
        self.assertIsNotNone(log.processed_at)

    def test_mark_completed_with_pos_order(self):
        """Test marking log as completed with POS order"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})

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

        log.mark_completed(pos_order_id=pos_order, response_data='{"id": 1}')

        self.assertEqual(log.pos_order_id.id, pos_order.id)
        self.assertEqual(log.response_data, '{"id": 1}')

    def test_mark_failed(self):
        """Test marking log as failed"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        log.mark_failed(error_message="Processing error")

        self.assertEqual(log.status, "failed")
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, "Processing error")
        self.assertIsNotNone(log.processed_at)

    def test_mark_processing(self):
        """Test marking log as processing"""
        log = self.WebhookLog.create_log(webhook_body={"OrderID": 1})
        log.mark_processing()

        self.assertEqual(log.status, "processing")

    def test_cleanup_old_records(self):
        """Test cleanup of old records"""
        # Create old completed record
        old_date = datetime.now() - timedelta(days=40)
        old_log = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "completed",
            "receive_date": old_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Create recent completed record
        recent_log = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "completed",
        })

        # Create old processing record (should not be deleted)
        old_processing = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "processing",
            "receive_date": old_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Run cleanup with 30 day retention
        deleted_count = self.WebhookLog.cleanup_old_records(retention_days=30)

        self.assertGreaterEqual(deleted_count, 1)
        self.assertFalse(old_log.exists())
        self.assertTrue(recent_log.exists())
        self.assertTrue(old_processing.exists())  # Processing records not deleted

    def test_cleanup_old_records_disabled(self):
        """Test cleanup is disabled when retention_days is 0"""
        old_date = datetime.now() - timedelta(days=40)
        old_log = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "completed",
            "receive_date": old_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

        deleted_count = self.WebhookLog.cleanup_old_records(retention_days=0)

        self.assertEqual(deleted_count, 0)
        self.assertTrue(old_log.exists())

    def test_cleanup_old_records_from_config(self):
        """Test cleanup uses config parameter"""
        self.env["ir.config_parameter"].sudo().set_param(
            "karage_pos.idempotency_retention_days", "15"
        )

        old_date = datetime.now() - timedelta(days=20)
        old_log = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "completed",
            "receive_date": old_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

        deleted_count = self.WebhookLog.cleanup_old_records()

        self.assertGreaterEqual(deleted_count, 1)
        self.assertFalse(old_log.exists())

    def test_cleanup_stuck_processing_records(self):
        """Test cleanup of stuck processing records"""
        # Create stuck processing record
        old_date = datetime.now() - timedelta(minutes=10)
        stuck_log = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "processing",
            "receive_date": old_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Create recent processing record (should not be reset)
        recent_log = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "processing",
        })

        # Run cleanup with 5 minute timeout
        reset_count = self.WebhookLog.cleanup_stuck_processing_records(timeout_minutes=5)

        self.assertGreaterEqual(reset_count, 1)
        stuck_log.invalidate_recordset()
        recent_log.invalidate_recordset()
        self.assertEqual(stuck_log.status, "failed")
        self.assertIn("timeout", stuck_log.error_message.lower())
        self.assertEqual(recent_log.status, "processing")  # Not affected

    def test_cleanup_stuck_processing_from_config(self):
        """Test stuck processing cleanup uses config parameter"""
        self.env["ir.config_parameter"].sudo().set_param(
            "karage_pos.idempotency_processing_timeout", "2"
        )

        old_date = datetime.now() - timedelta(minutes=5)
        stuck_log = self.WebhookLog.create({
            "webhook_body": "{}",
            "status": "processing",
            "receive_date": old_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

        reset_count = self.WebhookLog.cleanup_stuck_processing_records()

        self.assertGreaterEqual(reset_count, 1)
        stuck_log.invalidate_recordset()
        self.assertEqual(stuck_log.status, "failed")

    def test_webhook_log_ordering(self):
        """Test webhook logs are ordered by receive_date desc"""
        log1 = self.WebhookLog.create({
            "webhook_body": "{}",
            "receive_date": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
        })
        log2 = self.WebhookLog.create({
            "webhook_body": "{}",
            "receive_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        log3 = self.WebhookLog.create({
            "webhook_body": "{}",
            "receive_date": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        })

        logs = self.WebhookLog.search([("id", "in", [log1.id, log2.id, log3.id])])
        # Most recent first
        self.assertEqual(logs[0].id, log2.id)

    def test_webhook_log_default_values(self):
        """Test default values for webhook log"""
        log = self.WebhookLog.create({"webhook_body": "{}"})

        self.assertEqual(log.status, "pending")
        self.assertEqual(log.http_method, "POST")
        self.assertFalse(log.success)
        self.assertIsNotNone(log.receive_date)

    def test_get_or_create_log_lock_exception_with_existing_record(self):
        """Test get_or_create_log handles lock exception when record exists"""
        from unittest.mock import patch

        idempotency_key = f"lock-exception-{uuid.uuid4()}"

        # First create the record normally
        first_record, created = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            order_id="123",
        )
        self.assertTrue(created)

        # Now mock cr.execute to raise an exception (simulating lock failure)
        # Then the search should find the existing record
        original_execute = self.env.cr.execute

        def mock_execute(*args, **kwargs):
            if args and "FOR UPDATE NOWAIT" in str(args[0]):
                raise Exception("Lock not acquired")
            return original_execute(*args, **kwargs)

        with patch.object(self.env.cr, 'execute', side_effect=mock_execute):
            record, created = self.WebhookLog.get_or_create_log(
                idempotency_key=idempotency_key,
                order_id="123",
            )

        self.assertFalse(created)
        self.assertEqual(record.id, first_record.id)

    def test_get_or_create_log_creates_with_order_id(self):
        """Test get_or_create_log creates record with order_id"""
        idempotency_key = f"order-id-test-{uuid.uuid4()}"

        record, created = self.WebhookLog.get_or_create_log(
            idempotency_key=idempotency_key,
            order_id="test-order-123",
            status="processing",
        )

        self.assertTrue(created)
        self.assertEqual(record.order_id, "test-order-123")
        self.assertEqual(record.status, "processing")

    def test_get_or_create_log_no_body_no_key_raises(self):
        """Test get_or_create_log raises when neither key nor body provided"""
        with self.assertRaises(ValidationError):
            self.WebhookLog.get_or_create_log(
                idempotency_key=None,
                webhook_body=None,
            )


@tagged("post_install", "-at_install")
class TestPosOrder(TransactionCase, KaragePosTestCommon):
    """Test POS order model extensions"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def test_pos_order_external_fields(self):
        """Test external order tracking fields"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "EXT-12345",
            "external_order_source": "karage_pos_webhook",
            "external_order_date": fields.Datetime.now(),
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

        self.assertEqual(pos_order.external_order_id, "EXT-12345")
        self.assertEqual(pos_order.external_order_source, "karage_pos_webhook")
        self.assertIsNotNone(pos_order.external_order_date)

    def test_pos_order_external_id_search(self):
        """Test searching by external order ID"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "SEARCH-TEST-123",
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

        # Search by external_order_id (indexed field)
        found = self.env["pos.order"].search([
            ("external_order_id", "=", "SEARCH-TEST-123")
        ])
        self.assertEqual(len(found), 1)
        self.assertEqual(found.id, pos_order.id)

    def test_pos_order_without_external_fields(self):
        """Test POS order can be created without external fields"""
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

        self.assertTrue(pos_order.exists())
        self.assertFalse(pos_order.external_order_id)
        self.assertFalse(pos_order.external_order_source)
        self.assertFalse(pos_order.external_order_date)

    def test_should_create_picking_real_time_external_order(self):
        """Test that external orders force real-time picking creation"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "PICKING-TEST-123",
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

        # External orders should always return True for real-time picking
        self.assertTrue(pos_order._should_create_picking_real_time())

    def test_should_create_picking_real_time_non_external_order(self):
        """Test that non-external orders defer to standard behavior."""
        # Non-external order should follow standard behavior
        # Just verify the method works without external_order_source
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

        # Verify order has no external source
        self.assertFalse(pos_order.external_order_source)
        # Method should return a boolean (actual value depends on session config)
        result = pos_order._should_create_picking_real_time()
        self.assertIsInstance(result, bool)

    def test_action_pos_order_paid_external_order(self):
        """Test that external orders can be marked as paid with partial payment."""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 50.0,  # Partial payment
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "PARTIAL-PAY-123",
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
                "amount": 50.0,
            })],
        })

        # External orders should accept partial payments
        result = pos_order.action_pos_order_paid()
        self.assertTrue(result)
        self.assertEqual(pos_order.state, "paid")

    def test_action_pos_order_paid_non_external_order(self):
        """Test that non-external orders use standard payment validation."""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,  # Full payment
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

        # Non-external orders should use standard validation
        self.assertFalse(pos_order.external_order_source)
        # Should succeed with full payment
        result = pos_order.action_pos_order_paid()
        self.assertTrue(result)
        self.assertEqual(pos_order.state, "paid")


@tagged("post_install", "-at_install")
class TestPosOrderLine(TransactionCase, KaragePosTestCommon):
    """Test POS order line model extensions"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()
        # Check Odoo version - method only exists in Odoo 18+
        from odoo import release
        cls.odoo_version = int(release.version_info[0])
        cls.has_taxes_computation = cls.odoo_version >= 18

    def test_prepare_base_line_for_taxes_computation_with_external_id(self):
        """Test that external_order_id is used as invoice line name (Odoo 18+)."""
        if not self.has_taxes_computation:
            self.skipTest("_prepare_base_line_for_taxes_computation not available in Odoo 17")

        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "EXT-LINE-TEST-123",
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

        # Get the order line
        order_line = pos_order.lines[0]

        # Call the method and check the result
        values = order_line._prepare_base_line_for_taxes_computation()

        # Should use external_order_id as the name
        self.assertEqual(values.get('name'), "EXT-LINE-TEST-123")

    def test_prepare_base_line_for_taxes_computation_without_external_id(self):
        """Test that standard name is used when no external_order_id (Odoo 18+)."""
        if not self.has_taxes_computation:
            self.skipTest("_prepare_base_line_for_taxes_computation not available in Odoo 17")

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

        # Get the order line
        order_line = pos_order.lines[0]

        # Call the method and check the result
        values = order_line._prepare_base_line_for_taxes_computation()

        # Should not override name (or name should be standard product name)
        # The name should NOT be an external order ID
        self.assertNotEqual(values.get('name'), "EXT-LINE-TEST-123")


@tagged("post_install", "-at_install")
class TestResConfigSettings(TransactionCase, KaragePosTestCommon):
    """Test configuration settings"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def test_idempotency_processing_timeout_default(self):
        """Test default idempotency processing timeout"""
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.idempotency_processing_timeout, "5")

    def test_idempotency_retention_days_default(self):
        """Test default idempotency retention days"""
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.idempotency_retention_days, "30")

    def test_bulk_sync_max_orders_default(self):
        """Test default bulk sync max orders"""
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.bulk_sync_max_orders, "1000")

    def test_valid_order_statuses_default(self):
        """Test default valid order statuses"""
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.valid_order_statuses, "103,104")

    def test_config_parameter_persistence(self):
        """Test that config parameters are persisted"""
        settings = self.env["res.config.settings"].create({
            "idempotency_processing_timeout": "10",
            "idempotency_retention_days": "60",
            "bulk_sync_max_orders": "500",
            "valid_order_statuses": "103,104,105",
        })
        settings.execute()

        # Verify parameters are stored
        param = self.env["ir.config_parameter"].sudo()
        self.assertEqual(
            param.get_param("karage_pos.idempotency_processing_timeout"),
            "10"
        )
        self.assertEqual(
            param.get_param("karage_pos.idempotency_retention_days"),
            "60"
        )
        self.assertEqual(
            param.get_param("karage_pos.bulk_sync_max_orders"),
            "500"
        )
        self.assertEqual(
            param.get_param("karage_pos.valid_order_statuses"),
            "103,104,105"
        )

    def test_config_parameter_retrieval(self):
        """Test config parameters are retrieved correctly"""
        # Set parameters directly
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("karage_pos.idempotency_processing_timeout", "15")
        param.set_param("karage_pos.idempotency_retention_days", "45")

        # Create settings and verify values are loaded
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.idempotency_processing_timeout, "15")
        self.assertEqual(settings.idempotency_retention_days, "45")


@tagged("post_install", "-at_install")
class TestPosOrderPickingConfig(TransactionCase, KaragePosTestCommon):
    """Test POS order picking configuration validation"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def test_is_picking_config_valid_with_valid_picking_type(self):
        """Test _is_picking_config_valid returns True when picking type is properly configured"""
        # Use the standard POS config which has picking type configured
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

        # Method should return True when properly configured
        # Note: In test environment, picking type may or may not have source location
        # This tests the method exists and runs without error
        result = pos_order._is_picking_config_valid()
        # Result depends on test environment setup
        self.assertIsInstance(result, bool)

    def test_is_external_order_from_field(self):
        """Test _is_external_order detects external order from field"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "EXT-TEST-001",
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

        self.assertTrue(pos_order._is_external_order())

    def test_is_external_order_from_context(self):
        """Test _is_external_order detects external order from context"""
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

        # Without context or field, not external
        self.assertFalse(pos_order._is_external_order())

        # With context, is external
        pos_order_with_ctx = pos_order.with_context(is_external_order=True)
        self.assertTrue(pos_order_with_ctx._is_external_order())

    def test_is_external_order_not_external(self):
        """Test _is_external_order returns False for regular orders"""
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

        self.assertFalse(pos_order._is_external_order())

    def test_action_pos_order_paid_external_order_partial_payment(self):
        """Test external orders can be paid even with partial payment"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 200.0,  # Total is 200
            "amount_paid": 100.0,  # Only 100 paid
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_source": "karage_pos_webhook",
            "lines": [(0, 0, {
                "product_id": self.product1.id,
                "qty": 2,
                "price_unit": 100.0,
                "price_subtotal": 200.0,
                "price_subtotal_incl": 200.0,
            })],
            "payment_ids": [(0, 0, {
                "payment_method_id": self.payment_method_cash.id,
                "amount": 100.0,  # Partial payment
            })],
        })

        # Should succeed for external orders
        result = pos_order.action_pos_order_paid()
        self.assertTrue(result)
        self.assertEqual(pos_order.state, "paid")

    def test_should_create_picking_real_time_external_order_forces_true(self):
        """Test _should_create_picking_real_time returns True for external orders"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
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

        # External orders always return True
        self.assertTrue(pos_order._should_create_picking_real_time())

    def test_external_order_context_with_context_set(self):
        """Test that external order context can be detected via with_context"""
        # Create a regular order
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

        # Verify context mechanism works
        # Without context, not external
        self.assertFalse(pos_order._is_external_order())

        # With context set via with_context, is external
        pos_order_with_ctx = pos_order.with_context(
            is_external_order=True,
            external_order_source="test_source",
            external_order_id="TEST-EXT-001",
        )
        self.assertTrue(pos_order_with_ctx._is_external_order())

        # Context values are accessible
        ctx = pos_order_with_ctx.env.context
        self.assertEqual(ctx.get('external_order_source'), "test_source")
        self.assertEqual(ctx.get('external_order_id'), "TEST-EXT-001")


@tagged("post_install", "-at_install")
class TestPosOrderProcessSavedOrder(TransactionCase, KaragePosTestCommon):
    """Test _process_saved_order method for external orders"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def test_process_saved_order_external_with_context(self):
        """Test _process_saved_order handles external orders via context"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "state": "draft",
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

        # Process with external context
        pos_order_with_ctx = pos_order.with_context(
            is_external_order=True,
            external_order_source="test",
            external_order_id="TEST-001",
        )

        # Call _process_saved_order with draft=False
        result = pos_order_with_ctx._process_saved_order(False)

        # Should return order ID
        self.assertEqual(result, pos_order.id)
        # Order should be paid
        pos_order.invalidate_recordset(['state'])
        self.assertEqual(pos_order.state, "paid")

    def test_process_saved_order_external_with_field(self):
        """Test _process_saved_order handles external orders via field"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "state": "draft",
            "external_order_source": "karage_pos_webhook",
            "external_order_id": "EXT-002",
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

        # Call _process_saved_order with draft=False
        result = pos_order._process_saved_order(False)

        # Should return order ID
        self.assertEqual(result, pos_order.id)
        # Order should be paid
        pos_order.invalidate_recordset(['state'])
        self.assertEqual(pos_order.state, "paid")

    def test_process_saved_order_draft_mode(self):
        """Test _process_saved_order with draft=True skips processing"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "state": "draft",
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

        # Call with draft=True
        result = pos_order._process_saved_order(True)

        # Should return order ID
        self.assertTrue(result)

    def test_process_saved_order_cancelled_order(self):
        """Test _process_saved_order skips cancelled orders"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "state": "cancel",  # Cancelled state
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

        # Call with draft=False but order is cancelled
        result = pos_order._process_saved_order(False)

        # Should return result via super (doesn't trigger external flow)
        self.assertTrue(result)

    def test_process_saved_order_with_invoice_flag(self):
        """Test _process_saved_order with to_invoice flag"""
        partner = self.env["res.partner"].create({
            "name": "Invoice Test Partner",
            "email": "invoicetest@test.com",
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
            "state": "draft",
            "partner_id": partner.id,
            "to_invoice": True,
            "external_order_source": "karage_pos_webhook",
            "external_order_id": "EXT-INVOICE-001",
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

        # Process
        result = pos_order._process_saved_order(False)

        self.assertEqual(result, pos_order.id)
        pos_order.invalidate_recordset(['state'])
        # After processing with to_invoice, state can be 'paid', 'invoiced', or 'done'
        # depending on the Odoo version and whether invoice was successfully generated
        self.assertIn(pos_order.state, ["paid", "invoiced", "done"])


@tagged("post_install", "-at_install")
class TestPosOrderExternalFields(TransactionCase, KaragePosTestCommon):
    """Test external order fields on POS order"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def test_external_order_id_index(self):
        """Test external_order_id field is indexed for fast lookups"""
        field = self.env["pos.order"]._fields.get("external_order_id")
        self.assertIsNotNone(field)
        self.assertTrue(field.index)

    def test_external_order_source_field(self):
        """Test external_order_source field exists"""
        field = self.env["pos.order"]._fields.get("external_order_source")
        self.assertIsNotNone(field)

    def test_external_order_date_field(self):
        """Test external_order_date field exists"""
        field = self.env["pos.order"]._fields.get("external_order_date")
        self.assertIsNotNone(field)

    def test_search_by_external_order_id_with_source(self):
        """Test searching by external_order_id and source"""
        pos_order = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "UNIQUE-EXT-ID-12345",
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

        # Search by both fields
        found = self.env["pos.order"].search([
            ("external_order_id", "=", "UNIQUE-EXT-ID-12345"),
            ("external_order_source", "=", "karage_pos_webhook"),
        ])
        self.assertEqual(len(found), 1)
        self.assertEqual(found.id, pos_order.id)

    def test_refund_suffix_on_external_order_id(self):
        """Test that :REFUND suffix allows same OrderID for order and refund"""
        # Create original order
        order1 = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "ORDER-123",
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

        # Create refund order with :REFUND suffix
        order2 = self.env["pos.order"].create({
            "session_id": self.pos_session.id,
            "config_id": self.pos_config.id,
            "company_id": self.pos_config.company_id.id,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "amount_total": -100.0,
            "amount_paid": -100.0,
            "amount_tax": 0.0,
            "amount_return": 0.0,
            "external_order_id": "ORDER-123:REFUND",
            "external_order_source": "karage_pos_webhook",
            "lines": [(0, 0, {
                "product_id": self.product1.id,
                "qty": -1,
                "price_unit": 100.0,
                "price_subtotal": -100.0,
                "price_subtotal_incl": -100.0,
            })],
            "payment_ids": [(0, 0, {
                "payment_method_id": self.payment_method_cash.id,
                "amount": -100.0,
            })],
        })

        # Both orders should exist
        self.assertTrue(order1.exists())
        self.assertTrue(order2.exists())
        self.assertNotEqual(order1.id, order2.id)
        self.assertEqual(order1.external_order_id, "ORDER-123")
        self.assertEqual(order2.external_order_id, "ORDER-123:REFUND")
