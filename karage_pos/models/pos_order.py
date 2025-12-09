# -*- coding: utf-8 -*-

from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    external_order_id = fields.Char(
        string="External Order ID",
        index=True,
        help="Order ID from external POS system"
    )
    external_order_source = fields.Char(
        string="External Source",
        help="Source system (e.g., 'karage_pos_webhook')"
    )
    external_order_date = fields.Datetime(
        string="External Order Date",
        help="Order date from external system"
    )

    def _should_create_picking_real_time(self):
        """Override to force real-time picking for external/webhook orders.

        External orders (from webhooks) should always create pickings immediately
        to deduct inventory, regardless of session's update_stock_at_closing setting.
        This ensures inventory is accurate when orders come from external systems.
        """
        if self.external_order_source:
            return True
        return super()._should_create_picking_real_time()
