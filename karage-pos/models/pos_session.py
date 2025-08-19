from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    # Karage-specific session fields
    karage_location_id = fields.Integer(
        string='Karage Location ID',
        related='config_id.karage_location_id',
        store=True,
        help='Karage location ID for this session'
    )
    karage_order_count = fields.Integer(
        string='Karage Orders',
        compute='_compute_karage_order_count',
        help='Number of orders from Karage POS in this session'
    )

    @api.depends('order_ids', 'order_ids.karage_order_id')
    def _compute_karage_order_count(self):
        for session in self:
            session.karage_order_count = len(
                session.order_ids.filtered('karage_order_id')
            )

    @api.model
    def get_or_create_session_for_location(self, karage_location_id):
        """
        Get or create an active session for a specific Karage location
        
        Args:
            karage_location_id (int): Karage location identifier
            
        Returns:
            pos.session: Active session for the location
        """
        # Get POS configuration for this location
        pos_config = self.env['pos.config'].get_config_for_location(karage_location_id)
        
        # Get the session from config
        return pos_config.get_karage_session()

    def action_pos_session_open(self):
        """Override to add Karage-specific session opening logic"""
        result = super().action_pos_session_open()
        
        if self.config_id.karage_location_id:
            _logger.info(
                f"Opened Karage POS session {self.name} for location {self.config_id.karage_location_id}"
            )
        
        return result

    def action_pos_session_close(self):
        """Override to add Karage-specific session closing logic"""
        if self.config_id.karage_location_id:
            _logger.info(
                f"Closing Karage POS session {self.name} for location {self.config_id.karage_location_id} "
                f"with {self.karage_order_count} Karage orders"
            )
        
        return super().action_pos_session_close()