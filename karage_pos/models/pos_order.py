# -*- coding: utf-8 -*-

import logging
from uuid import uuid4

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

    @api.model
    def _process_order(self, order, draft_or_existing=None, existing_order=None):
        """
        Extended to handle external webhook orders with tracking fields.

        Uses context to pass external order flag through the processing chain,
        ensuring _process_saved_order can detect external orders even before
        the fields are committed to the database.

        Handles version differences:
        - Odoo 17.0: _process_order(order, draft, existing_order) - 3 arguments
        - Odoo 18+: _process_order(order, existing_order) - 2 arguments

        :param dict order: dictionary representing the order
        :param draft_or_existing: draft (bool) for Odoo 17, existing_order for Odoo 18
        :param existing_order: existing order for Odoo 17 (None for Odoo 18)
        :returns: id of created/updated pos.order
        """
        # Extract external order info from order data
        order_data = order.get('data', order)
        external_order_source = order_data.get('external_order_source')
        external_order_id = order_data.get('external_order_id')

        # Use context to pass external flag through the processing chain
        # This ensures _process_saved_order knows it's an external order
        # even before the record fields are committed
        if external_order_source:
            _logger.info(
                f"Processing external order: external_order_id={external_order_id}, "
                f"external_order_source={external_order_source}"
            )
            self = self.with_context(
                is_external_order=True,
                external_order_source=external_order_source,
                external_order_id=external_order_id,
            )

        # Call parent implementation for standard order processing
        # Handle version differences in method signature
        try:
            # Odoo 18+ signature (2 arguments)
            order_id = super()._process_order(order, draft_or_existing)
        except TypeError:
            # Odoo 17.0 signature (3 arguments)
            # Odoo 17 expects order wrapped as {'data': order_data, ...}
            if 'data' not in order:
                order = {
                    'data': order,
                    'id': order.get('name', str(uuid4())),
                    'to_invoice': order.get('to_invoice', False),
                }
            order_id = super()._process_order(order, draft_or_existing, existing_order)

        return order_id

    def _is_picking_config_valid(self):
        """
        Check if picking type is properly configured for inventory operations.

        Returns True if picking can be created, False otherwise.
        """
        picking_type = self.config_id.picking_type_id
        if not picking_type:
            _logger.warning(
                f"POS config '{self.config_id.name}' has no picking type configured. "
                f"Skipping inventory operations for order {self.name}."
            )
            return False

        if not picking_type.default_location_src_id:
            _logger.warning(
                f"Picking type '{picking_type.name}' has no source location configured. "
                f"Skipping inventory operations for order {self.name}."
            )
            return False

        return True

    def _is_external_order(self):
        """
        Check if this is an external order (from webhook).

        Checks both the record field and context, since context is set
        during _process_order before the record fields are committed.
        """
        return (
            self.external_order_source
            or self.env.context.get('is_external_order')
        )

    def _process_saved_order(self, draft):
        """
        Extended to provide resilient error handling for external orders.

        For external orders (from webhooks), picking and invoice creation
        failures are logged but don't prevent the order from being saved.
        This ensures webhook orders complete even if secondary operations fail.
        """
        self.ensure_one()

        # For external orders, use savepoints for resilience
        # Check both record field AND context (context is set before fields are committed)
        is_external = self._is_external_order()
        if is_external and not draft and self.state != 'cancel':
            external_source = self.external_order_source or self.env.context.get('external_order_source')
            external_id = self.external_order_id or self.env.context.get('external_order_id')
            _logger.info(
                f"Processing external order {self.name} "
                f"(source: {external_source}, external_id: {external_id})"
            )

            # Confirm payment (critical - must succeed)
            try:
                self.action_pos_order_paid()
            except Exception as e:
                _logger.error(
                    f'Could not process order payment for external order {self.id}: {e}'
                )
                raise

            # Create picking with savepoint (non-critical)
            # Only attempt if picking configuration is valid
            if self._is_picking_config_valid():
                try:
                    with self.env.cr.savepoint():
                        self._create_order_picking()
                        _logger.info(f"Picking created for external order {self.name}")
                except Exception as e:
                    _logger.warning(
                        f"Could not create picking for external order {self.name}: {e}"
                    )

            self._compute_total_cost_in_real_time()

            # Generate invoice with savepoint (non-critical)
            if self.to_invoice and self.state == 'paid':
                try:
                    with self.env.cr.savepoint():
                        self._generate_pos_order_invoice()
                        _logger.info(f"Invoice created for external order {self.name}")
                except Exception as e:
                    _logger.warning(
                        f"Could not create invoice for external order {self.name}: {e}"
                    )

            return self.id

        # Non-external orders use standard flow
        return super()._process_saved_order(draft)

    def action_pos_order_paid(self):
        """Override to accept partial payments for external/webhook orders.

        Standard Odoo requires full payment before marking order as paid.
        For webhook orders, we accept partial payments since the external
        system handles payment validation.
        """
        if self._is_external_order():
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
        if self._is_external_order():
            return True
        return super()._should_create_picking_real_time()


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _prepare_base_line_for_taxes_computation(self):
        """Override to use external_order_id as invoice line name.

        When generating invoices for external/webhook orders, use the external
        order ID as the invoice line description for better traceability.
        """
        values = super()._prepare_base_line_for_taxes_computation()

        # Use external_order_id as label if available
        external_order_id = self.order_id.external_order_id
        if external_order_id:
            values['name'] = external_order_id
            _logger.debug(f"Set invoice line name to external_order_id: {external_order_id}")

        return values
