# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    is_karage_default_pos = fields.Boolean(
        string='Is Karage Default POS',
        default=False,
        help='Marks this POS as the default Karage integration POS. '
             'Default POS configurations cannot be deleted.'
    )

    @api.constrains('name')
    def _check_karage_name_prefix(self):
        """
        Enforce KARAGE prefix for all Karage POS configurations.
        This ensures consistency with the dashboard domain filter.
        """
        for record in self:
            # Only check records that are being managed by Karage
            # (either marked as default or already have KARAGE prefix)
            if record.is_karage_default_pos or (record.name and record.name.startswith('KARAGE')):
                if not record.name or not record.name.startswith('KARAGE'):
                    raise ValidationError(_(
                        'Karage POS configurations must have names starting with "KARAGE". '
                        'Please ensure the name starts with "KARAGE" (e.g., "KARAGE - Branch Name").'
                    ))

    @api.constrains('active')
    def _check_karage_default_pos_archive(self):
        """Prevent archiving default Karage POS"""
        for record in self:
            if record.is_karage_default_pos and not record.active:
                raise UserError(_(
                    'Cannot archive the default Karage POS configuration. '
                    'This POS is required for webhook integration.'
                ))

    def unlink(self):
        """Prevent deletion of default Karage POS"""
        for record in self:
            if record.is_karage_default_pos:
                raise UserError(_(
                    'Cannot delete the default Karage POS configuration. '
                    'This POS is required for webhook integration. '
                    'If you need to change settings, please modify the existing configuration.'
                ))
        return super().unlink()

    def write(self, vals):
        """Prevent removing the is_karage_default_pos flag"""
        if 'is_karage_default_pos' in vals and not vals['is_karage_default_pos']:
            if any(record.is_karage_default_pos for record in self):
                raise UserError(_(
                    'Cannot remove the default Karage POS flag. '
                    'This POS must remain as the default for webhook integration.'
                ))
        return super().write(vals)

    def action_open_karage_settings(self):
        """Open the simplified Karage POS settings dialog"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('POS Settings'),
            'res_model': 'pos.config',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('karage_pos.view_karage_pos_config_settings_form').id,
            'target': 'new',
        }

    def action_edit_karage_pos(self):
        """Open the full form view for editing Karage POS configuration"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit POS Configuration'),
            'res_model': 'pos.config',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('karage_pos.view_karage_pos_config_form').id,
            'target': 'current',
        }
