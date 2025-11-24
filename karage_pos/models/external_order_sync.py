# -*- coding: utf-8 -*-

import json
import logging

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class ExternalOrderSync(models.Model):
    """Configuration for syncing orders from external systems"""

    _name = "external.order.sync"
    _description = "External Order Synchronization"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    external_api_url = fields.Char(
        string="External API URL",
        required=True,
        help="URL of the external system API to fetch orders from",
    )
    external_api_key = fields.Char(
        string="External API Key",
        required=True,
        help="API key for authenticating with external system",
    )
    pos_config_id = fields.Many2one(
        "pos.config",
        string="POS Configuration",
        required=True,
        help="POS configuration to use for creating orders",
    )
    auto_create_session = fields.Boolean(
        string="Auto Create Session",
        default=True,
        help="Automatically create POS session if none is open",
    )
    last_sync_date = fields.Datetime(
        string="Last Sync Date",
        readonly=True,
        help="Last successful synchronization date",
    )
    last_sync_status = fields.Selection(
        [
            ("success", "Success"),
            ("error", "Error"),
            ("no_orders", "No Orders"),
        ],
        string="Last Sync Status",
        readonly=True,
    )
    last_sync_message = fields.Text(string="Last Sync Message", readonly=True)
    sync_interval = fields.Integer(
        string="Sync Interval (minutes)",
        default=15,
        help="Interval in minutes between syncs",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    def _get_or_create_pos_session(self):
        """Get existing open session or create a new one"""
        self.ensure_one()

        # Try to find an open session for this POS config
        session = (
            self.env["pos.session"]
            .sudo()
            .search(
                [("config_id", "=", self.pos_config_id.id), ("state", "=", "opened")],
                limit=1,
                order="id desc",
            )
        )

        if session:
            return session

        # If no session and auto_create is enabled, create one
        if self.auto_create_session:
            _logger.info(
                f"Creating new POS session for config {self.pos_config_id.name}"
            )
            try:
                # Create session with system user
                system_user = self.env.ref("base.user_admin")
                session = (
                    self.env["pos.session"]
                    .sudo()
                    .with_user(system_user)
                    .create(
                        {
                            "config_id": self.pos_config_id.id,
                            "user_id": system_user.id,
                        }
                    )
                )
                # Session is automatically opened by create method
                _logger.info(f"Created POS session: {session.name}")
                return session
            except Exception as e:
                _logger.error(f"Failed to create POS session: {str(e)}")
                raise UserError(_("Failed to create POS session: %s") % str(e))
        else:
            raise UserError(
                _(
                    "No open POS session found and auto-create is disabled. Please open a POS session manually."
                )
            )

    def _fetch_orders_from_external(self):
        """Fetch orders from external system"""
        self.ensure_one()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.external_api_key}",
            # Alternative: 'X-API-Key': self.external_api_key
        }

        # You can customize the request parameters based on your external API
        params = {}
        if self.last_sync_date:
            # Only fetch orders since last sync
            params["since"] = self.last_sync_date.isoformat()

        try:
            _logger.info(f"Fetching orders from {self.external_api_url}")
            response = requests.get(
                self.external_api_url, headers=headers, params=params, timeout=30
            )
            response.raise_for_status()

            # Try to parse as JSON
            try:
                data = response.json()
            except json.JSONDecodeError:
                # If not JSON, try to parse as array of orders
                data = response.text
                if data.strip().startswith("["):
                    data = json.loads(data)
                else:
                    # Single order wrapped in object
                    data = json.loads(data)
                    if isinstance(data, dict) and "orders" in data:
                        data = data["orders"]
                    elif isinstance(data, dict):
                        data = [data]

            # Ensure data is a list
            if not isinstance(data, list):
                data = [data] if data else []

            _logger.info(f"Fetched {len(data)} orders from external system")
            return data

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching orders from external system: {str(e)}")
            raise UserError(
                _("Failed to fetch orders from external system: %s") % str(e)
            )
        except Exception as e:
            _logger.error(f"Unexpected error fetching orders: {str(e)}")
            raise UserError(_("Unexpected error: %s") % str(e))

    def _process_external_order(self, order_data):
        """Process a single order from external system and create POS order"""
        self.ensure_one()

        try:
            # Get or create POS session
            pos_session = self._get_or_create_pos_session()

            # Validate that payment methods have journals configured
            payment_methods = pos_session.payment_method_ids
            if not payment_methods:
                _logger.error(
                    f"No payment methods configured for POS session {pos_session.name}"
                )
                raise UserError(
                    _(
                        "No payment methods configured for this POS session. Please configure payment methods first."
                    )
                )

            # Check if all payment methods have journals
            missing_journals = []
            for payment_method in payment_methods:
                if not payment_method.journal_id:
                    missing_journals.append(payment_method.name)

            if missing_journals:
                error_msg = _(
                    "Journal not found for payment method(s): %s. Please configure journals for all payment methods."
                ) % ", ".join(missing_journals)
                _logger.error(error_msg)
                raise UserError(error_msg)

            # Validate required fields
            if not order_data.get("OrderItems"):
                _logger.warning(
                    f'Order {order_data.get("OrderID")} has no items, skipping'
                )
                return False

            # Get product environment
            product_env = self.env["product.product"].sudo()

            # Prepare order lines
            order_lines = []
            for order_item in order_data.get("OrderItems", []):
                item_name = order_item.get("ItemName", "").strip()
                item_id = order_item.get("ItemID", 0)
                price = float(order_item.get("Price", 0))
                quantity = float(order_item.get("Quantity", 1))
                discount_amount = float(order_item.get("DiscountAmount", 0))

                # Find product
                product = None
                if item_id and item_id > 0:
                    product = product_env.browse(item_id)
                    if not product.exists():
                        product = None

                if not product and item_name:
                    product = product_env.search(
                        [
                            ("name", "=", item_name),
                            ("sale_ok", "=", True),
                            ("available_in_pos", "=", True),
                        ],
                        limit=1,
                    )

                    if not product:
                        product = product_env.search(
                            [
                                ("name", "ilike", item_name),
                                ("sale_ok", "=", True),
                                ("available_in_pos", "=", True),
                            ],
                            limit=1,
                        )

                if not product:
                    _logger.warning(
                        f'Product not found: ItemName="{item_name}", ItemID={item_id}'
                    )
                    continue

                # Calculate discount percentage
                discount_percent = 0.0
                if price > 0 and discount_amount > 0:
                    discount_percent = (discount_amount / (price * quantity)) * 100.0

                # Get taxes
                taxes = product.taxes_id.filtered(
                    lambda t: t.company_id.id == pos_session.config_id.company_id.id
                )

                fiscal_position = pos_session.config_id.default_fiscal_position_id
                if fiscal_position:
                    taxes = fiscal_position.map_tax(taxes)

                # Calculate tax
                tax_results = taxes.compute_all(
                    price * (1 - discount_percent / 100.0),
                    pos_session.config_id.currency_id,
                    quantity,
                    product=product,
                    partner=False,
                )

                price_subtotal = tax_results["total_excluded"]
                price_subtotal_incl = tax_results["total_included"]

                order_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "qty": quantity,
                            "price_unit": price,
                            "discount": discount_percent,
                            "price_subtotal": price_subtotal,
                            "price_subtotal_incl": price_subtotal_incl,
                            "tax_ids": [(6, 0, taxes.ids)],
                        },
                    )
                )

            if not order_lines:
                _logger.warning(
                    f'No valid order lines for order {order_data.get("OrderID")}'
                )
                return False

            # Process payments
            payment_lines = []
            total_paid = 0.0

            for checkout in order_data.get("CheckoutDetails", []):
                payment_mode = checkout.get("PaymentMode", 1)
                amount = float(str(checkout.get("AmountPaid", 0)).replace(",", ""))
                card_type = checkout.get("CardType", "Cash")

                if amount <= 0:
                    continue

                # PaymentMode to Journal Name mapping
                payment_mode_mapping = {
                    1: "Cash",
                    2: "Card",
                    3: "Credit",
                    5: "Tabby",
                    6: "Tamara",
                    7: "StcPay",
                    8: "Bank Transfer",
                }

                # Find payment method based on PaymentMode mapping
                payment_method = None
                journal_search_name = payment_mode_mapping.get(payment_mode)

                if journal_search_name:
                    # Search for payment method where journal name contains the mapped name
                    payment_method = pos_session.payment_method_ids.filtered(
                        lambda p: p.journal_id
                        and journal_search_name.lower() in p.journal_id.name.lower()
                    )[:1]

                # Fallback: If PaymentMode not in mapping or not found, try card_type
                if not payment_method and card_type:
                    payment_method = pos_session.payment_method_ids.filtered(
                        lambda p: p.journal_id
                        and card_type.lower() in p.journal_id.name.lower()
                    )[:1]

                # Fallback: Try is_cash_count for PaymentMode = 1
                if not payment_method and payment_mode == 1:
                    payment_method = pos_session.payment_method_ids.filtered(
                        lambda p: p.is_cash_count
                    )[:1]

                if not payment_method:
                    if journal_search_name:
                        error_msg = _(
                            'Payment method with journal name containing "%s" not found for PaymentMode=%s. Please configure a payment method with a journal containing "%s" in its name.'
                        ) % (journal_search_name, payment_mode, journal_search_name)
                        _logger.error(error_msg)
                        raise UserError(error_msg)
                    else:
                        error_msg = _(
                            "No payment method found for PaymentMode=%s, CardType=%s. PaymentMode must be 1 (Cash), 2 (Card), 3 (Credit), 5 (Tabby), 6 (Tamara), 7 (StcPay), or 8 (Bank Transfer)."
                        ) % (payment_mode, card_type)
                        _logger.error(error_msg)
                        raise UserError(error_msg)

                # Validate that payment method has a journal configured
                if not payment_method.journal_id:
                    error_msg = (
                        _(
                            "Journal not found for payment method: %s. Please configure a journal for this payment method."
                        )
                        % payment_method.name
                    )
                    _logger.error(error_msg)
                    raise UserError(error_msg)

                total_paid += amount
                payment_lines.append(
                    (
                        0,
                        0,
                        {
                            "payment_method_id": payment_method.id,
                            "amount": amount,
                            "payment_date": fields.Datetime.now(),
                        },
                    )
                )

            if not payment_lines:
                _logger.warning(
                    f'No valid payment lines for order {order_data.get("OrderID")}'
                )
                return False

            # Calculate totals
            calculated_total = sum(
                line[2]["price_subtotal_incl"] for line in order_lines
            )
            calculated_tax = sum(
                line[2]["price_subtotal_incl"] - line[2]["price_subtotal"]
                for line in order_lines
            )

            # Create POS order
            order_vals = {
                "session_id": pos_session.id,
                "config_id": pos_session.config_id.id,
                "company_id": pos_session.config_id.company_id.id,
                "pricelist_id": pos_session.config_id.pricelist_id.id,
                "fiscal_position_id": (
                    pos_session.config_id.default_fiscal_position_id.id
                    if pos_session.config_id.default_fiscal_position_id
                    else False
                ),
                "user_id": pos_session.user_id.id,
                "date_order": fields.Datetime.now(),
                "partner_id": False,
                "to_invoice": False,
                "note": f'External Order ID: {order_data.get("OrderID")}',
                "lines": order_lines,
                "payment_ids": payment_lines,
                "amount_total": calculated_total,
                "amount_tax": calculated_tax,
                "amount_paid": total_paid,
                "amount_return": max(0.0, total_paid - calculated_total),
            }

            pos_order = self.env["pos.order"].sudo().create(order_vals)

            # Confirm order
            pos_order.action_pos_order_paid()

            # Create picking for inventory consumption
            try:
                pos_order._create_order_picking()
            except Exception as e:
                _logger.warning(
                    f"Could not create picking for order {pos_order.name}: {str(e)}"
                )

            _logger.info(
                f'Created POS order {pos_order.name} from external order {order_data.get("OrderID")}'
            )
            return pos_order

        except Exception as e:
            _logger.error(
                f'Error processing external order {order_data.get("OrderID")}: {str(e)}',
                exc_info=True,
            )
            return False

    def sync_orders(self):
        """Main method to sync orders from external system"""
        self.ensure_one()

        if not self.active:
            _logger.info(f"Sync {self.name} is not active, skipping")
            return

        try:
            # Fetch orders from external system
            orders = self._fetch_orders_from_external()

            if not orders:
                self.write(
                    {
                        "last_sync_date": fields.Datetime.now(),
                        "last_sync_status": "no_orders",
                        "last_sync_message": "No orders found to sync",
                    }
                )
                return

            # Process each order
            success_count = 0
            error_count = 0

            for order_data in orders:
                result = self._process_external_order(order_data)
                if result:
                    success_count += 1
                else:
                    error_count += 1

            # Update sync status
            status = "success" if error_count == 0 else "error"
            message = f"Processed {success_count} orders successfully"
            if error_count > 0:
                message += f", {error_count} failed"

            self.write(
                {
                    "last_sync_date": fields.Datetime.now(),
                    "last_sync_status": status,
                    "last_sync_message": message,
                }
            )

            _logger.info(f"Sync completed: {message}")

        except Exception as e:
            _logger.error(f"Error in sync_orders: {str(e)}", exc_info=True)
            self.write(
                {
                    "last_sync_date": fields.Datetime.now(),
                    "last_sync_status": "error",
                    "last_sync_message": f"Error: {str(e)}",
                }
            )
            raise
