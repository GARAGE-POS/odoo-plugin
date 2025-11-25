# -*- coding: utf-8 -*-

import json
from unittest.mock import patch, MagicMock
from odoo.tests import TransactionCase

from .test_common import KaragePosTestCommon


class TestWebhookSender(TransactionCase, KaragePosTestCommon):
    """Test webhook sender model"""

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_webhook_success(self, mock_requests):
        """Test sending webhook successfully"""
        # Mock requests library
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'success'}
        mock_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_response

        # Update config with URL
        self.karage_config.odoo_url = 'http://test.odoo.com'

        webhook_sender = self.env['karage.pos.webhook.sender']
        data = {'OrderID': 123, 'AmountTotal': 100.0}

        response = webhook_sender.send_webhook(data)
        
        self.assertIsNotNone(response)
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertEqual(call_args[0][0], 'http://test.odoo.com/api/v1/webhook/pos-order')
        self.assertEqual(call_args[1]['json'], data)
        self.assertIn('X-API-KEY', call_args[1]['headers'])
        self.assertEqual(call_args[1]['headers']['X-API-KEY'], 'test_api_key_12345')

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_webhook_no_config(self, mock_requests):
        """Test sending webhook without active config"""
        # Deactivate config
        self.karage_config.active = False

        webhook_sender = self.env['karage.pos.webhook.sender']
        response = webhook_sender.send_webhook({'OrderID': 123})
        
        self.assertIsNone(response)
        mock_requests.post.assert_not_called()

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_webhook_no_api_key(self, mock_requests):
        """Test sending webhook without API key"""
        self.karage_config.api_key = False
        
        webhook_sender = self.env['karage.pos.webhook.sender']
        response = webhook_sender.send_webhook({'OrderID': 123})
        
        self.assertIsNone(response)
        mock_requests.post.assert_not_called()

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_webhook_no_url(self, mock_requests):
        """Test sending webhook without Odoo URL"""
        self.karage_config.odoo_url = False
        
        webhook_sender = self.env['karage.pos.webhook.sender']
        response = webhook_sender.send_webhook({'OrderID': 123})
        
        self.assertIsNone(response)
        mock_requests.post.assert_not_called()

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_webhook_request_exception(self, mock_requests):
        """Test sending webhook with request exception"""
        import requests
        mock_requests.post.side_effect = requests.exceptions.RequestException('Connection error')

        self.karage_config.odoo_url = 'http://test.odoo.com'

        webhook_sender = self.env['karage.pos.webhook.sender']
        response = webhook_sender.send_webhook({'OrderID': 123})
        
        self.assertIsNone(response)

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_webhook_http_error(self, mock_requests):
        """Test sending webhook with HTTP error"""
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('404 Not Found')
        mock_requests.post.return_value = mock_response

        self.karage_config.odoo_url = 'http://test.odoo.com'

        webhook_sender = self.env['karage.pos.webhook.sender']
        response = webhook_sender.send_webhook({'OrderID': 123})
        
        self.assertIsNone(response)

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_webhook_timeout(self, mock_requests):
        """Test sending webhook with custom timeout"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_response

        self.karage_config.odoo_url = 'http://test.odoo.com'

        webhook_sender = self.env['karage.pos.webhook.sender']
        webhook_sender.send_webhook({'OrderID': 123}, timeout=60)
        
        call_args = mock_requests.post.call_args
        self.assertEqual(call_args[1]['timeout'], 60)

    @patch('karage_pos.models.webhook_sender.requests')
    def test_send_pos_order_webhook(self, mock_requests):
        """Test send_pos_order_webhook method"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_response
        
        self.karage_config.odoo_url = 'http://test.odoo.com'

        webhook_sender = self.env['karage.pos.webhook.sender']
        order_data = {'OrderID': 456, 'AmountTotal': 200.0}

        response = webhook_sender.send_pos_order_webhook(order_data)
        
        self.assertIsNotNone(response)
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertEqual(call_args[1]['json'], order_data)

    @patch('custom_addons.karage_pos.models.webhook_sender.requests', None)
    def test_send_webhook_no_requests_library(self):
        """Test sending webhook when requests library is not available"""
        webhook_sender = self.env['karage.pos.webhook.sender']
        response = webhook_sender.send_webhook({'OrderID': 123})
        
        self.assertIsNone(response)

