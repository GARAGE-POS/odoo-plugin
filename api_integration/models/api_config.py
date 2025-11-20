# -*- coding: utf-8 -*-

import secrets
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class APIConfig(models.Model):
    """API Configuration Model"""
    _name = 'api.config'
    _description = 'API Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', required=True)
    api_key = fields.Char(string='API Key', copy=False, readonly=True)
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description')
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now, readonly=True)
    last_used = fields.Datetime(string='Last Used', readonly=True)
    usage_count = fields.Integer(string='Usage Count', default=0, readonly=True)

    @api.model
    def create(self, vals):
        """Generate API key on creation"""
        if not vals.get('api_key'):
            # Generate a secure random API key
            vals['api_key'] = secrets.token_urlsafe(32)
        return super(APIConfig, self).create(vals)

    def regenerate_key(self):
        """Regenerate API key"""
        self.ensure_one()
        self.write({
            'api_key': secrets.token_urlsafe(32),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('API key regenerated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def update_usage(self):
        """Update usage statistics"""
        self.ensure_one()
        self.write({
            'last_used': fields.Datetime.now(),
            'usage_count': self.usage_count + 1,
        })



