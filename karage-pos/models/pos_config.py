from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # Karage-specific fields
    karage_location_id = fields.Integer(
        string='Karage Location ID',
        help='Unique identifier for this POS location in Karage system'
    )
    karage_auto_invoice = fields.Boolean(
        string='Auto Generate Invoices',
        default=True,
        help='Automatically generate invoices for orders from this location'
    )
    karage_default_customer = fields.Many2one(
        'res.partner',
        string='Default Customer',
        help='Default customer for walk-in orders'
    )

    @api.constrains('karage_location_id')
    def _check_unique_karage_location(self):
        for config in self:
            if config.karage_location_id:
                existing = self.search([
                    ('karage_location_id', '=', config.karage_location_id),
                    ('id', '!=', config.id)
                ])
                if existing:
                    raise ValidationError(
                        _('Karage Location ID %s is already used by POS configuration: %s') % 
                        (config.karage_location_id, existing.name)
                    )

    def get_karage_session(self):
        """Get or create an active session for this Karage location"""
        self.ensure_one()
        
        # Look for an open session
        existing_session = self.env['pos.session'].search([
            ('config_id', '=', self.id),
            ('state', 'in', ['opening_control', 'opened'])
        ], limit=1)
        
        if existing_session:
            return existing_session
            
        # Create a new session if none exists
        session_vals = {
            'config_id': self.id,
            'user_id': self.env.uid,
        }
        
        new_session = self.env['pos.session'].create(session_vals)
        new_session.action_pos_session_open()
        
        return new_session

    @api.model
    def get_config_for_location(self, karage_location_id):
        """Get POS configuration for a specific Karage location ID"""
        config = self.search([('karage_location_id', '=', karage_location_id)], limit=1)
        
        if not config:
            # Get or create required references safely
            try:
                journal = self.env.ref('karage-pos.karage_pos_sales_journal')
            except ValueError:
                # Create journal if it doesn't exist
                journal = self.env['account.journal'].create({
                    'name': f'Karage POS Sales {karage_location_id}',
                    'code': f'KPOS{karage_location_id}',
                    'type': 'sale',
                    'currency_id': self.env.company.currency_id.id,
                })
            
            # Ensure journal has currency_id set
            if not journal.currency_id:
                journal.currency_id = self.env.company.currency_id
            
            try:
                pricelist = self.env.ref('karage-pos.karage_pos_pricelist')
            except ValueError:
                # Create pricelist if it doesn't exist
                pricelist = self.env['product.pricelist'].create({
                    'name': f'Karage POS Pricelist {karage_location_id}',
                })
            
            # Get a suitable picking type (outgoing delivery)
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', self.env.company.id)
            ], limit=1)
            
            if not picking_type:
                # If no picking type found, get the default one
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'outgoing')
                ], limit=1)
            
            # Get payment methods for this config
            payment_methods = []
            try:
                cash_method = self.env.ref('karage-pos.payment_method_cash_karage')
                payment_methods.append(cash_method.id)
            except ValueError:
                # Create basic cash method if it doesn't exist
                cash_journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
                if not cash_journal:
                    cash_journal = self.env['account.journal'].create({
                        'name': 'Cash',
                        'code': 'CSH1',
                        'type': 'cash',
                        'currency_id': self.env.company.currency_id.id,
                    })
                
                cash_method = self.env['pos.payment.method'].create({
                    'name': 'Cash',
                    'is_cash_count': True,
                    'journal_id': cash_journal.id,
                })
                payment_methods.append(cash_method.id)
                
            try:
                card_method = self.env.ref('karage-pos.payment_method_card_karage')
                payment_methods.append(card_method.id)
            except ValueError:
                pass  # Skip card method if not available
            
            # Create a default configuration for this location
            config = self.create({
                'name': f'Karage Location {karage_location_id}',
                'karage_location_id': karage_location_id,
                'journal_id': journal.id,
                'pricelist_id': pricelist.id,
                'picking_type_id': picking_type.id,
                'company_id': self.env.company.id,
                'karage_auto_invoice': True,
                'payment_method_ids': [(6, 0, payment_methods)],
            })
            
        return config