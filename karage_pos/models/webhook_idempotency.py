# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WebhookIdempotency(models.Model):
    """Model to track processed webhook requests for idempotency"""
    _name = 'karage.pos.webhook.idempotency'
    _description = 'Karage POS Webhook Idempotency'
    _rec_name = 'idempotency_key'
    _order = 'create_date desc'

    idempotency_key = fields.Char(
        string='Idempotency Key',
        required=True,
        index=True,
        help='Unique key to identify duplicate requests'
    )
    order_id = fields.Char(
        string='Order ID',
        help='External Order ID from the webhook request'
    )
    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
        help='Created POS order from this webhook'
    )
    status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], string='Status', default='pending', required=True)
    response_data = fields.Text(
        string='Response Data',
        help='JSON response data from the webhook processing'
    )
    error_message = fields.Text(
        string='Error Message',
        help='Error message if processing failed'
    )
    processed_at = fields.Datetime(
        string='Processed At',
        help='Timestamp when the request was processed'
    )
    create_date = fields.Datetime(string='Created At', readonly=True)

    _sql_constraints = [
        ('idempotency_key_unique', 'unique(idempotency_key)', 'Idempotency key must be unique!'),
    ]

    @api.model
    def check_idempotency(self, idempotency_key):
        """
        Check if a request with this idempotency key has been processed
        
        :param idempotency_key: The idempotency key to check
        :return: Record if found, None otherwise
        """
        if not idempotency_key:
            return None
        
        record = self.search([('idempotency_key', '=', idempotency_key)], limit=1)
        return record if record else None

    @api.model
    def create_idempotency_record(self, idempotency_key, order_id=None, status='pending'):
        """
        Create a new idempotency record
        
        :param idempotency_key: The idempotency key
        :param order_id: External Order ID (optional)
        :param status: Initial status
        :return: Created record
        """
        if not idempotency_key:
            raise ValidationError('Idempotency key is required')
        
        # Check if already exists
        existing = self.check_idempotency(idempotency_key)
        if existing:
            return existing
        
        return self.create({
            'idempotency_key': idempotency_key,
            'order_id': order_id,
            'status': status,
        })

    def mark_completed(self, pos_order_id=None, response_data=None):
        """Mark the idempotency record as completed"""
        self.write({
            'status': 'completed',
            'pos_order_id': pos_order_id.id if pos_order_id else False,
            'response_data': response_data,
            'processed_at': fields.Datetime.now(),
        })

    def mark_failed(self, error_message=None):
        """Mark the idempotency record as failed"""
        self.write({
            'status': 'failed',
            'error_message': error_message,
            'processed_at': fields.Datetime.now(),
        })

    def mark_processing(self):
        """Mark the idempotency record as processing"""
        self.write({
            'status': 'processing',
        })


