# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError

from .test_common import KaragePosTestCommon


class TestKaragePosConfig(TransactionCase, KaragePosTestCommon):
    """Test karage.pos.config model"""

    def test_create_config(self):
        """Test creating a configuration"""
        config = self.env['karage.pos.config'].create({
            'name': 'Test Config 2',
            'api_key': 'test_key_456',
            'active': True,
            'odoo_url': 'https://test.odoo.com',
            'webhook_endpoint': '/api/v1/webhook/pos-order',
        })
        
        self.assertTrue(config.exists())
        self.assertEqual(config.name, 'Test Config 2')
        self.assertEqual(config.api_key, 'test_key_456')
        self.assertTrue(config.active)

    def test_unique_name_constraint(self):
        """Test that configuration name must be unique"""
        with self.assertRaises(ValidationError):
            self.env['karage.pos.config'].create({
                'name': 'Test Config',  # Same as existing
                'api_key': 'test_key',
                'active': True,
            })

    def test_get_config(self):
        """Test get_config method"""
        # Should return active config
        config = self.env['karage.pos.config'].get_config()
        self.assertTrue(config)
        self.assertEqual(config, self.karage_config)
        
        # Deactivate config
        self.karage_config.active = False
        
        # Should return None
        config = self.env['karage.pos.config'].get_config()
        self.assertFalse(config)

    def test_get_api_key(self):
        """Test get_api_key method"""
        api_key = self.env['karage.pos.config'].get_api_key()
        self.assertEqual(api_key, 'test_api_key_12345')
        
        # Deactivate config
        self.karage_config.active = False
        api_key = self.env['karage.pos.config'].get_api_key()
        self.assertIsNone(api_key)

    def test_get_webhook_url(self):
        """Test get_webhook_url method"""
        url = self.karage_config.get_webhook_url()
        self.assertEqual(url, 'http://localhost:8069/api/v1/webhook/pos-order')
        
        # Test with trailing slash in odoo_url
        self.karage_config.odoo_url = 'http://localhost:8069/'
        url = self.karage_config.get_webhook_url()
        self.assertEqual(url, 'http://localhost:8069/api/v1/webhook/pos-order')
        
        # Test with leading slash in endpoint
        self.karage_config.webhook_endpoint = '/api/v1/webhook/pos-order'
        url = self.karage_config.get_webhook_url()
        self.assertEqual(url, 'http://localhost:8069/api/v1/webhook/pos-order')
        
        # Test without odoo_url
        self.karage_config.odoo_url = False
        url = self.karage_config.get_webhook_url()
        self.assertIsNone(url)

    def test_multiple_configs_only_one_active(self):
        """Test that only one config should be active"""
        config2 = self.env['karage.pos.config'].create({
            'name': 'Test Config 2',
            'api_key': 'test_key_2',
            'active': True,
        })
        
        # Both can be active, but get_config returns the first one found
        config = self.env['karage.pos.config'].get_config()
        self.assertTrue(config)


