# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KaragePosPaymentMapping(models.Model):
    _name = "karage.pos.payment.mapping"
    _description = "Payment Mode Mapping"
    _order = "external_code"

    # Common payment type presets with their external codes
    PAYMENT_TYPE_SELECTION = [
        ('1', 'Cash (Code: 1)'),
        ('2', 'Card (Code: 2)'),
        ('3', 'Credit (Code: 3)'),
        ('5', 'Tabby (Code: 5)'),
        ('6', 'Tamara (Code: 6)'),
        ('7', 'StcPay (Code: 7)'),
        ('8', 'Bank Transfer (Code: 8)'),
        ('custom', 'Custom Code'),
    ]

    payment_type = fields.Selection(
        PAYMENT_TYPE_SELECTION,
        string="Payment Type",
        required=True,
        default='1',
        help="Select a preset payment type or 'Custom Code' to enter your own"
    )
    custom_code = fields.Integer(
        string="Custom Code",
        help="Enter custom external payment code (only used when Payment Type is 'Custom Code')"
    )
    external_code = fields.Integer(
        string="External Payment Code",
        compute="_compute_external_code",
        store=True,
        help="The payment mode code from the external POS system"
    )
    name = fields.Char(
        string="Description",
        required=True,
        help="Human-readable description of this payment mode"
    )
    payment_method_id = fields.Many2one(
        "pos.payment.method",
        string="POS Payment Method",
        required=True,
        help="The Odoo POS payment method to use for this external code"
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('external_code_unique', 'unique(external_code)',
         'External payment code must be unique!')
    ]

    @api.depends('payment_type', 'custom_code')
    def _compute_external_code(self):
        for record in self:
            if record.payment_type == 'custom':
                record.external_code = record.custom_code or 0
            else:
                record.external_code = int(record.payment_type) if record.payment_type else 0

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        """Auto-fill description based on payment type"""
        type_names = {
            '1': 'Cash',
            '2': 'Card',
            '3': 'Credit',
            '5': 'Tabby',
            '6': 'Tamara',
            '7': 'StcPay',
            '8': 'Bank Transfer',
        }
        if self.payment_type and self.payment_type != 'custom':
            self.name = type_names.get(self.payment_type, '')

    @api.constrains('external_code', 'payment_type', 'custom_code')
    def _check_external_code(self):
        for record in self:
            if record.external_code < 0:
                raise ValidationError("External payment code must be a positive integer.")
            if record.payment_type == 'custom' and not record.custom_code:
                raise ValidationError("Please enter a custom code when using 'Custom Code' payment type.")
