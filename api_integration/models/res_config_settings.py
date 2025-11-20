# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Fix for is_installed_sale field if purchase_stock is not installed"""
    _inherit = 'res.config.settings'

    # Ensure is_installed_sale field is always available
    # This fixes the issue where purchase_stock module might not be installed
    # or the field isn't properly computed
    is_installed_sale = fields.Boolean(
        string="Is the Sale Module Installed",
        compute='_compute_is_installed_sale',
        store=False,
    )

    @api.depends()
    def _compute_is_installed_sale(self):
        """Compute if sale module is installed"""
        for record in self:
            sale_module = self.env['ir.module.module'].search([
                ('name', '=', 'sale'),
                ('state', '=', 'installed')
            ], limit=1)
            record.is_installed_sale = bool(sale_module)



