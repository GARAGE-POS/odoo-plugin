# -*- coding: utf-8 -*-

import json
import logging
try:
    import requests
except ImportError:
    requests = None
from odoo import models, api, fields

_logger = logging.getLogger(__name__)


class WebhookSender(models.AbstractModel):
    """Helper model for sending webhooks to Odoo with X-API-KEY header"""
    _name = 'karage.pos.webhook.sender'
    _description = 'Karage POS Webhook Sender'

    def send_webhook(self, data, timeout=30):
        """
        Send webhook to Odoo with X-API-KEY header
        
        :param data: Dictionary containing the webhook payload
        :param timeout: Request timeout in seconds (default: 30)
        :return: Response object or None if error
        """
        if not requests:
            _logger.error('requests library not available. Cannot send webhook.')
            return None
        
        api_key = self.env['ir.config_parameter'].sudo().get_param('karage_pos.api_key')
        
        if not api_key:
            _logger.error('API key not configured. Cannot send webhook.')
            return None
        
        # Get base URL from system parameter or use request base URL
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
        webhook_endpoint = '/api/v1/webhook/pos-order'
        webhook_url = f"{base_url.rstrip('/')}/{webhook_endpoint.lstrip('/')}"
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': api_key,
        }
        
        try:
            _logger.info(f'Sending webhook to {webhook_url}')
            response = requests.post(
                webhook_url,
                json=data,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            _logger.info(f'Webhook sent successfully. Status: {response.status_code}')
            return response
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error sending webhook: {str(e)}')
            return None

    def send_pos_order_webhook(self, order_data, timeout=30):
        """
        Send POS order webhook to Odoo
        
        :param order_data: Dictionary containing POS order data
        :param timeout: Request timeout in seconds (default: 30)
        :return: Response object or None if error
        """
        return self.send_webhook(order_data, timeout=timeout)

