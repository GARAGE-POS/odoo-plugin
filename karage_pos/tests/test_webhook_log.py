# -*- coding: utf-8 -*-

import json
from odoo.tests import TransactionCase

from .test_common import KaragePosTestCommon


class TestWebhookLog(KaragePosTestCommon):
    """Test webhook log model"""

    def test_create_log(self):
        """Test creating webhook log"""
        webhook_data = {"OrderID": 123, "AmountTotal": 100.0}

        log = self.env["karage.pos.webhook.log"].create_log(
            webhook_body=webhook_data,
            idempotency_key="log-key-123",
            request_info={
                "ip_address": "127.0.0.1",
                "user_agent": "Test Agent",
                "http_method": "POST",
            },
        )

        self.assertTrue(log.exists())
        self.assertEqual(log.idempotency_key, "log-key-123")
        self.assertEqual(log.order_id, "123")
        self.assertEqual(log.ip_address, "127.0.0.1")
        self.assertEqual(log.user_agent, "Test Agent")
        self.assertEqual(log.http_method, "POST")

        # Verify webhook body is stored as JSON string
        body_dict = json.loads(log.webhook_body)
        self.assertEqual(body_dict["OrderID"], 123)

    def test_create_log_with_string_body(self):
        """Test creating log with string body"""
        log = self.env["karage.pos.webhook.log"].create_log(
            webhook_body='{"OrderID": 456, "AmountTotal": 200.0}',
            idempotency_key="log-key-456",
        )

        self.assertTrue(log.exists())
        body_dict = json.loads(log.webhook_body)
        self.assertEqual(body_dict["OrderID"], 456)

    def test_create_log_extracts_order_id(self):
        """Test that create_log extracts OrderID from body"""
        webhook_data = {"OrderID": 789, "AmountTotal": 300.0}

        log = self.env["karage.pos.webhook.log"].create_log(
            webhook_body=webhook_data,
        )

        self.assertEqual(log.order_id, "789")

    def test_update_log_result(self):
        """Test updating log with results"""
        log = self.env["karage.pos.webhook.log"].create_log(
            webhook_body={"OrderID": 999},
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

        idempotency_record = self.env["karage.pos.webhook.idempotency"].create(
            {
                "idempotency_key": "update-key-123",
                "status": "completed",
            }
        )

        log.update_log_result(
            status_code=200,
            response_message="Success",
            success=True,
            pos_order_id=pos_order,
            idempotency_record_id=idempotency_record,
            processing_time=1.5,
        )

        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.response_message, "Success")
        self.assertTrue(log.success)
        self.assertEqual(log.pos_order_id, pos_order)
        self.assertEqual(log.idempotency_record_id, idempotency_record)
        self.assertEqual(log.processing_time, 1.5)

    def test_update_log_result_failure(self):
        """Test updating log with failure"""
        log = self.env["karage.pos.webhook.log"].create_log(
            webhook_body={"OrderID": 888},
        )

        log.update_log_result(
            status_code=400,
            response_message="Validation error",
            success=False,
            processing_time=0.5,
        )

        self.assertEqual(log.status_code, 400)
        self.assertEqual(log.response_message, "Validation error")
        self.assertFalse(log.success)
        self.assertEqual(log.processing_time, 0.5)

    def test_log_receive_date(self):
        """Test that receive_date is automatically set"""
        log = self.env["karage.pos.webhook.log"].create_log(
            webhook_body={"OrderID": 777},
        )

        self.assertIsNotNone(log.receive_date)

    def test_log_order_by_date(self):
        """Test that logs are ordered by receive_date desc"""
        log1 = self.env["karage.pos.webhook.log"].create_log(
            webhook_body={"OrderID": 1},
        )

        log2 = self.env["karage.pos.webhook.log"].create_log(
            webhook_body={"OrderID": 2},
        )

        logs = self.env["karage.pos.webhook.log"].search([])
        # Most recent should be first
        self.assertEqual(logs[0], log2)
