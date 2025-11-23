# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestAPIConfig(TransactionCase):
    """Test API Config model"""

    def setUp(self):
        super(TestAPIConfig, self).setUp()
        self.api_config_model = self.env['api.config']

    def test_create_api_config(self):
        """Test creating API config generates API key"""
        config = self.api_config_model.create({
            'name': 'Test Config',
            'active': True,
        })
        self.assertTrue(config.api_key)
        self.assertEqual(len(config.api_key), 43)  # token_urlsafe(32) produces 43 chars
        self.assertEqual(config.usage_count, 0)
        self.assertFalse(config.last_used)

    def test_create_api_config_with_key(self):
        """Test creating API config with existing key"""
        custom_key = 'custom_api_key_123'
        config = self.api_config_model.create({
            'name': 'Test Config',
            'api_key': custom_key,
            'active': True,
        })
        self.assertEqual(config.api_key, custom_key)

    def test_regenerate_key(self):
        """Test regenerating API key"""
        config = self.api_config_model.create({
            'name': 'Test Config',
            'active': True,
        })
        old_key = config.api_key
        result = config.regenerate_key()
        self.assertNotEqual(config.api_key, old_key)
        self.assertEqual(len(config.api_key), 43)
        self.assertIsNotNone(result)

    def test_update_usage(self):
        """Test updating usage statistics"""
        config = self.api_config_model.create({
            'name': 'Test Config',
            'active': True,
        })
        initial_count = config.usage_count
        config.update_usage()
        self.assertEqual(config.usage_count, initial_count + 1)
        self.assertIsNotNone(config.last_used)
        
        # Update again
        config.update_usage()
        self.assertEqual(config.usage_count, initial_count + 2)

    def test_inactive_config(self):
        """Test inactive config cannot authenticate"""
        config = self.api_config_model.create({
            'name': 'Test Config',
            'active': False,
        })
        api_key = config.api_key
        
        # Try to authenticate with inactive config
        found_config = self.api_config_model.sudo().search([
            ('api_key', '=', api_key),
            ('active', '=', True)
        ], limit=1)
        self.assertFalse(found_config)

    def test_multiple_configs(self):
        """Test creating multiple API configs"""
        config1 = self.api_config_model.create({
            'name': 'Config 1',
            'active': True,
        })
        config2 = self.api_config_model.create({
            'name': 'Config 2',
            'active': True,
        })
        self.assertNotEqual(config1.api_key, config2.api_key)
        self.assertEqual(config1.usage_count, 0)
        self.assertEqual(config2.usage_count, 0)

    def test_api_config_name_required(self):
        """Test that name is required"""
        with self.assertRaises(Exception):
            self.api_config_model.create({
                'active': True,
            })

