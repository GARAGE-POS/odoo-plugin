# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class KaragePosConfig(models.Model):
    """Configuration model for Karage POS settings"""

    _name = "karage.pos.config"
    _description = "Karage POS Configuration"
    _rec_name = "name"

    name = fields.Char(
        string="Configuration Name", required=True, default="Default Configuration"
    )
    api_key = fields.Char(
        string="API Key",
        required=True,
        help="API key to authenticate webhooks sent to Odoo. This key should be included in the X-API-KEY header when sending webhooks.",
    )
    active = fields.Boolean(string="Active", default=True)
    odoo_url = fields.Char(
        string="Odoo URL",
        help="Base URL of the Odoo instance (e.g., https://odoo.example.com)",
    )
    webhook_endpoint = fields.Char(
        string="Webhook Endpoint",
        default="/api/v1/webhook/pos-order",
        help="Endpoint path for webhook requests",
    )

    _sql_constraints = [
        ("name_unique", "unique(name)", "Configuration name must be unique!"),
    ]

    @api.model
    def get_config(self):
        """Get the active configuration"""
        config = self.search([("active", "=", True)], limit=1)
        if not config:
            _logger.warning("No active Karage POS configuration found")
        return config

    @api.model
    def get_api_key(self):
        """Get the API key from active configuration"""
        config = self.get_config()
        return config.api_key if config else None

    def get_webhook_url(self):
        """Get the full webhook URL"""
        if not self.odoo_url:
            return None
        base_url = self.odoo_url.rstrip("/")
        endpoint = self.webhook_endpoint.lstrip("/")
        return f"{base_url}/{endpoint}"

    def update_usage(self):
        """Update usage statistics (placeholder)"""
        # TODO: Implement usage tracking if needed
        return
