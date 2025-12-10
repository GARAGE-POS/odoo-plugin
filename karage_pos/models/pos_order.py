# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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

    def action_pos_order_paid(self):
        """Override to accept partial payments for external/webhook orders.

        Standard Odoo requires full payment before marking order as paid.
        For webhook orders, we accept partial payments since the external
        system handles payment validation.
        """
        if self.external_order_source:
            # For webhook orders, skip payment validation and mark as paid
            self.write({'state': 'paid'})
            return True
        return super().action_pos_order_paid()

    def _should_create_picking_real_time(self):
        """Override to force real-time picking for external/webhook orders.

        External orders (from webhooks) should always create pickings immediately
        to deduct inventory, regardless of session's update_stock_at_closing setting.
        This ensures inventory is accurate when orders come from external systems.
        """
        if self.external_order_source:
            return True
        return super()._should_create_picking_real_time()


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _prepare_base_line_for_taxes_computation(self):
        """Override to use external_order_id as the line name for invoice labels."""
        values = super()._prepare_base_line_for_taxes_computation()

        # Use external_order_id as label if available
        external_order_id = self.order_id.external_order_id
        _logger.info(f"PosOrderLine._prepare_base_line_for_taxes_computation: "
                     f"order_id={self.order_id.id}, external_order_id={external_order_id}")
        if external_order_id:
            values['name'] = external_order_id
            _logger.info(f"Set invoice line name to: {external_order_id}")

        return values
