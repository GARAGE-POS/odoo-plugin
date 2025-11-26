# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    karage_pos_api_key = fields.Char(
        string='Karage POS API Key',
        config_parameter='karage_pos.api_key',
        help='API key to authenticate webhooks sent to Odoo. This key should be included in the X-API-KEY header when sending webhooks.'
    )

    @api.model
    def get_api_key(self):
        """Get the API key from system parameters"""
        return self.env['ir.config_parameter'].sudo().get_param('karage_pos.api_key')

