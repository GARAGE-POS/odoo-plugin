# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class WebhookLog(models.Model):
    """Model to log all incoming webhook requests"""

    _name = "karage.pos.webhook.log"
    _description = "Karage POS Webhook Log"
    _rec_name = "id"
    _order = "receive_date desc"

    receive_date = fields.Datetime(
        string="Receive Date",
        required=True,
        default=fields.Datetime.now,
        help="Date and time when the webhook was received",
    )
    webhook_body = fields.Text(
        string="Webhook Body",
        required=True,
        help="Full JSON body of the incoming webhook request",
    )
    idempotency_key = fields.Char(
        string="Idempotency Key",
        index=True,
        help="Idempotency key from the request (if provided)",
    )
    order_id = fields.Char(
        string="Order ID", index=True, help="External Order ID from the webhook"
    )
    ip_address = fields.Char(
        string="IP Address", help="IP address of the request sender"
    )
    user_agent = fields.Char(string="User Agent", help="User agent of the request")
    http_method = fields.Char(
        string="HTTP Method", default="POST", help="HTTP method of the request"
    )
    status_code = fields.Integer(string="Status Code", help="HTTP status code returned")
    response_message = fields.Text(
        string="Response Message", help="Response message or error"
    )
    processing_time = fields.Float(
        string="Processing Time (seconds)", help="Time taken to process the webhook"
    )
    idempotency_record_id = fields.Many2one(
        "karage.pos.webhook.idempotency",
        string="Idempotency Record",
        help="Related idempotency record if idempotency key was provided",
    )
    pos_order_id = fields.Many2one(
        "pos.order",
        string="Created POS Order",
        help="POS order created from this webhook (if successful)",
    )
    success = fields.Boolean(
        string="Success",
        default=False,
        help="Whether the webhook was processed successfully",
    )

    @api.model
    def create_log(self, webhook_body, idempotency_key=None, request_info=None):
        """
        Create a webhook log entry

        :param webhook_body: The webhook request body (dict or JSON string)
        :param idempotency_key: Idempotency key if provided
        :param request_info: Dictionary with request metadata (ip_address, user_agent, etc.)
        :return: Created log record
        """
        # Convert dict to JSON string if needed
        if isinstance(webhook_body, dict):
            webhook_body_str = json.dumps(webhook_body, indent=2, default=str)
        else:
            webhook_body_str = str(webhook_body)

        # Extract order ID from body if it's a dict
        order_id = None
        if isinstance(webhook_body, dict):
            order_id = str(webhook_body.get("OrderID", ""))
        elif isinstance(webhook_body, str):
            try:
                body_dict = json.loads(webhook_body)
                order_id = str(body_dict.get("OrderID", ""))
            except (ValueError, TypeError):
                pass

        request_info = request_info or {}

        return self.create(
            {
                "webhook_body": webhook_body_str,
                "idempotency_key": idempotency_key,
                "order_id": order_id,
                "ip_address": request_info.get("ip_address"),
                "user_agent": request_info.get("user_agent"),
                "http_method": request_info.get("http_method", "POST"),
            }
        )

    def update_log_result(
        self,
        status_code=None,
        response_message=None,
        success=False,
        pos_order_id=None,
        idempotency_record_id=None,
        processing_time=None,
    ):
        """Update log with processing results"""
        update_vals = {
            "status_code": status_code,
            "response_message": response_message,
            "success": success,
            "pos_order_id": pos_order_id.id if pos_order_id else False,
            "idempotency_record_id": (
                idempotency_record_id.id if idempotency_record_id else False
            ),
        }
        if processing_time is not None:
            update_vals["processing_time"] = processing_time
        self.write(update_vals)
