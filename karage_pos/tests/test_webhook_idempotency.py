# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

from .test_common import KaragePosTestCommon


class TestWebhookIdempotency(TransactionCase, KaragePosTestCommon):
    """Test webhook idempotency model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_common()

    def test_create_idempotency_record(self):
        """Test creating idempotency record"""
        record = self.env["karage.pos.webhook.idempotency"].create_idempotency_record(
            "test-key-123", order_id="12345", status="pending"
        )

        self.assertTrue(record.exists())
        self.assertEqual(record.idempotency_key, "test-key-123")
        self.assertEqual(record.order_id, "12345")
        self.assertEqual(record.status, "pending")

    def test_unique_idempotency_key(self):
        """Test that idempotency key must be unique"""
        self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": "unique-key-123",
                "status": "pending",
            }
        )

        with self.assertRaises(ValidationError):
            self.env["karage.pos.webhook.idempotency"].create(
                {
                    "idempotency_key": "unique-key-123",  # Duplicate
                    "status": "pending",
                }
            )

    def test_check_idempotency(self):
        """Test check_idempotency method"""
        # Create a record
        record = self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": "check-key-123",
                "status": "completed",
                "order_id": "12345",
            }
        )

        # Check for existing key
        found = self.env["karage.pos.webhook.idempotency"].check_idempotency(
            "check-key-123"
        )
        self.assertEqual(found, record)

        # Check for non-existent key
        found = self.env["karage.pos.webhook.idempotency"].check_idempotency(
            "non-existent"
        )
        self.assertFalse(found)

    def test_mark_completed(self):
        """Test mark_completed method"""
        record = self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": "complete-key-123",
                "status": "processing",
            }
        )

        pos_order = self.env["pos.order"].create(
            {
                "session_id": self.pos_session.id,
                "config_id": self.pos_config.id,
                "company_id": self.company.id,
                "pricelist_id": self.pos_config.pricelist_id.id,
                "user_id": self.user.id,
            }
        )

        record.mark_completed(
            pos_order_id=pos_order, response_data='{"id": 1, "name": "TEST"}'
        )

        self.assertEqual(record.status, "completed")
        self.assertEqual(record.pos_order_id, pos_order)
        self.assertEqual(record.response_data, '{"id": 1, "name": "TEST"}')
        self.assertIsNotNone(record.processed_at)

    def test_mark_failed(self):
        """Test mark_failed method"""
        record = self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": "fail-key-123",
                "status": "processing",
            }
        )

        record.mark_failed(error_message="Test error message")

        self.assertEqual(record.status, "failed")
        self.assertEqual(record.error_message, "Test error message")
        self.assertIsNotNone(record.processed_at)

    def test_mark_processing(self):
        """Test mark_processing method"""
        record = self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": "process-key-123",
                "status": "pending",
            }
        )

        record.mark_processing()

        self.assertEqual(record.status, "processing")

    def test_create_idempotency_record_returns_existing(self):
        """Test that create_idempotency_record returns existing record if key exists"""
        existing = self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": "existing-key-123",
                "status": "completed",
            }
        )

        # Try to create again with same key
        result = self.env["karage.pos.webhook.idempotency"].create_idempotency_record(
            "existing-key-123",
            order_id="99999",
        )

        self.assertEqual(result, existing)
        self.assertEqual(result.order_id, "99999")  # Should update order_id

    def test_create_idempotency_record_requires_key(self):
        """Test that idempotency key is required"""
        with self.assertRaises(ValidationError):
            self.env["karage.pos.webhook.idempotency"].create_idempotency_record(
                None,  # Missing key
                order_id="12345",
            )
