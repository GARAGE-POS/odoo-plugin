# -*- coding: utf-8 -*-

import json
import logging
import time
from random import randint
from uuid import uuid4

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Constants
IR_CONFIG_PARAMETER = "ir.config_parameter"


class APIController(http.Controller):
    """REST API Controller for bulk POS order webhook endpoint"""

    # ========== Helper Methods ==========

    def _get_header_or_body(self, data, *keys):
        """
        Extract value from headers or request body using multiple possible key names

        :param data: Request body dictionary
        :param keys: Possible header/body key names to check
        :return: First matching value or None
        """
        # Check headers first
        for key in keys:
            value = request.httprequest.headers.get(key)
            if value:
                return value

        # Check body
        if data:
            for key in keys:
                value = data.get(key)
                if value:
                    return value

        return None

    def _parse_request_body(self):
        """Parse and validate JSON request body"""
        if not request.httprequest.data:
            return None, "Request body is required"

        try:
            return json.loads(request.httprequest.data.decode("utf-8")), None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return None, f"Invalid JSON format: {str(e)}"

    def _create_webhook_log(self, body_data, idempotency_key=None):
        """Create webhook log entry"""
        try:
            # Use savepoint to isolate potential duplicate key errors
            with request.env.cr.savepoint():
                return request.env["karage.pos.webhook.log"].sudo().create_log(
                    webhook_body=body_data,
                    idempotency_key=idempotency_key,
                    request_info={
                        "ip_address": request.httprequest.remote_addr,
                        "user_agent": request.httprequest.headers.get("User-Agent"),
                        "http_method": request.httprequest.method,
                    },
                )
        except Exception as e:
            _logger.warning(f"Failed to create webhook log: {str(e)}")
            return None

    def _update_log(self, webhook_log, status_code, message, success=False,
                    pos_order=None, start_time=None):
        """Update webhook log with processing result"""
        if not webhook_log:
            return

        try:
            # Determine status based on success/failure
            if success:
                status = "completed"
            else:
                status = "failed"

            webhook_log.update_log_result(
                status_code=status_code,
                response_message=message,
                success=success,
                pos_order_id=pos_order,
                processing_time=time.time() - start_time if start_time else None,
                status=status,
            )
        except Exception as e:
            _logger.warning(f"Error updating webhook log: {str(e)}")

    def _json_response(self, data, status=200, error=None):
        """Return standardized JSON response"""
        # Calculate count based on data type
        if isinstance(data, list):
            count = len(data)
        elif data:
            count = 1
        else:
            count = 0

        response_data = {
            "status": "success" if status == 200 else "error",
            "data": data if status == 200 else None,
            "error": error or None,
            "count": count,
        }
        return request.make_response(
            json.dumps(response_data, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )

    def _authenticate_api_key(self, api_key):
        """
        Authenticate using Odoo's built-in API key system

        :param api_key: API key to validate
        :return: Tuple of (success: bool, error_message: str or None)
        """
        if not api_key:
            return False, "Invalid or missing API key"

        # Get scopes from configuration
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()
        scopes_str = config_param.get_param(
            "karage_pos.api_key_scopes",
            "rpc,odoo.addons.base.models.res_users"
        )
        scopes_to_try = [s.strip() for s in scopes_str.split(",") if s.strip()]

        apikeys_model = request.env["res.users.apikeys"].with_user(1)

        for scope in scopes_to_try:
            try:
                user_id = apikeys_model._check_credentials(scope=scope, key=api_key)
                if user_id:
                    request.update_env(user=user_id)
                    _logger.info(f"API request authenticated for user ID: {user_id} (scope: {scope})")
                    return True, None
            except Exception:
                continue

        _logger.warning("API key check failed for all scopes")
        return False, "Invalid or missing API key"

    # ========== Main Endpoint ==========

    @http.route(
        "/api/v1/webhook/pos-order/bulk",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def webhook_pos_order_bulk(self, **kwargs):
        """
        Bulk webhook endpoint to create multiple POS orders

        Expected JSON format:
        {
            "pos_config_id": 5,  // Optional - POS config ID to use (falls back to default from settings)
            "partner_id": 15,  // Optional - Default partner ID for ALL orders (can be overridden per-order)
            "customer_ref": "CUST-001",  // Optional - Default customer reference for ALL orders
            "orders": [
                {
                    "OrderID": "11112111",
                    "OrderDate": "2025-08-10T17:16:43+00:00",
                    "OrderStatus": 103,
                    "partner_id": 20,  // Optional - Override default partner for this order
                    "customer_ref": "CUST-002",  // Optional - Override default customer ref for this order
                    "OrderItems": [
                        {
                            "OdooItemID": 35722,
                            "PriceWithoutTax": 18.75,
                            "Quantity": 1,
                            "DiscountPercentage": 0
                        }
                    ],
                    "CheckoutDetails": [
                        {
                            "PaymentMode": 1,
                            "AmountPaid": 18.75,
                            "CardType": "Cash"
                        }
                    ]
                },
                ...
            ]
        }

        Partner resolution priority (per order):
        1. Order-level partner_id (if provided)
        2. Top-level partner_id (applies to all orders)
        3. Order-level customer_ref lookup
        4. Top-level customer_ref lookup
        5. Default partner from settings (karage_pos.default_partner_id)

        Note: Invoice is only generated if a partner is resolved.

        For backwards compatibility, also accepts an array of orders directly (uses default POS config):
        [
            { "OrderID": "...", ... }
        ]

        Returns HTTP 200 if all succeed
        Returns HTTP 207 (Multi-Status) if partial success
        Returns HTTP 400 if all fail
        """
        start_time = time.time()
        webhook_log = None

        try:
            # 1. Validate HTTP method
            if request.httprequest.method != "POST":
                return self._json_response(
                    None, status=405, error="Method not allowed. Only POST requests are accepted."
                )

            # 2. Parse request body
            data, error = self._parse_request_body()
            if error:
                return self._json_response(None, status=400, error=error)

            # 3. Extract API key from headers (not from body since body is now an array)
            api_key = (request.httprequest.headers.get("X-API-KEY")
                       or request.httprequest.headers.get("X-API-Key"))

            # 4. Create webhook log
            webhook_log = self._create_webhook_log(data)

            # 5. Authenticate API key
            authenticated, auth_error = self._authenticate_api_key(api_key)
            if not authenticated:
                self._update_log(webhook_log, 401, auth_error, False, start_time=start_time)
                return self._json_response(None, status=401, error=auth_error)

            # 6. Parse payload - support both new format and legacy array format
            pos_config_id = None
            top_level_partner_id = None
            top_level_customer_ref = None
            if isinstance(data, dict):
                # New format: { "pos_config_id": 5, "partner_id": 15, "orders": [...] }
                pos_config_id = data.get("pos_config_id")
                top_level_partner_id = data.get("partner_id")  # Partner for all orders
                top_level_customer_ref = data.get("customer_ref")  # Customer ref for all orders
                orders_data = data.get("orders")
                if not isinstance(orders_data, list):
                    error_msg = 'Request body must contain an "orders" array'
                    self._update_log(webhook_log, 400, error_msg, False, start_time=start_time)
                    return self._json_response(None, status=400, error=error_msg)
            elif isinstance(data, list):
                # Legacy format: direct array of orders (uses default POS config)
                orders_data = data
            else:
                error_msg = 'Request body must be an object with "orders" array or a direct array of orders'
                self._update_log(webhook_log, 400, error_msg, False, start_time=start_time)
                return self._json_response(None, status=400, error=error_msg)

            # 7. Check bulk size limit
            max_orders = int(
                request.env[IR_CONFIG_PARAMETER]
                .sudo()
                .get_param("karage_pos.bulk_sync_max_orders", default="1000")
            )
            if len(orders_data) > max_orders:
                error_msg = f"Too many orders: {len(orders_data)}. Maximum allowed: {max_orders}"
                self._update_log(webhook_log, 400, error_msg, False, start_time=start_time)
                return self._json_response(None, status=400, error=error_msg)

            # 8. Process orders
            results = self._process_bulk_orders(
                orders_data,
                pos_config_id=pos_config_id,
                default_partner_id=top_level_partner_id,
                default_customer_ref=top_level_customer_ref,
            )

            # 9. Close and post the POS session
            pos_session = self._get_current_external_session(pos_config_id=pos_config_id)
            if pos_session:
                self._close_and_post_session(pos_session)

            # 10. Determine overall status
            total = len(results)
            successful = sum(1 for r in results if r["status"] == "success")
            failed = total - successful

            if successful == total:
                status_code = 200
            elif successful == 0:
                status_code = 400
            else:
                status_code = 207  # Multi-Status

            # 11. Prepare response
            # Include the POS config ID that was used (from request or default)
            used_pos_config_id = pos_config_id
            if not used_pos_config_id:
                used_pos_config_id = int(request.env[IR_CONFIG_PARAMETER].sudo().get_param(
                    "karage_pos.external_pos_config_id", "0"
                ) or 0)

            response_data = {
                "pos_config_id": used_pos_config_id,
                "total": total,
                "successful": successful,
                "failed": failed,
                "results": results,
            }

            # 12. Update webhook log
            self._update_log(
                webhook_log,
                status_code,
                json.dumps(response_data),
                successful > 0,
                start_time=start_time,
            )

            return self._json_response(
                response_data,
                status=status_code if status_code == 200 else 200,  # Always return 200, status in data
            )

        except Exception as e:
            _logger.error(f"Unexpected error in webhook_pos_order_bulk: {str(e)}", exc_info=True)
            if webhook_log:
                self._update_log(
                    webhook_log, 500, f"Internal server error: {str(e)}", False, start_time=start_time
                )
            return self._json_response(None, status=500, error=f"Internal server error: {str(e)}")

    def _process_bulk_orders(self, orders_data, pos_config_id=None, default_partner_id=None, default_customer_ref=None):
        """
        Process multiple orders independently

        :param orders_data: List of order data dicts
        :param pos_config_id: Optional POS config ID to use (falls back to default from settings)
        :param default_partner_id: Optional default partner ID for all orders (can be overridden per-order)
        :param default_customer_ref: Optional default customer ref for all orders (can be overridden per-order)
        :return: List of result dicts, one per order
        """
        results = []

        for idx, order_data in enumerate(orders_data):
            order_id = order_data.get("OrderID", f"unknown_{idx}")

            try:
                # Use savepoint for atomic per-order processing
                with request.env.cr.savepoint():
                    # Validate required fields for this order (simplified - no amount fields required)
                    required_fields = ["OrderID", "OrderItems", "CheckoutDetails"]
                    missing_fields = [field for field in required_fields if field not in order_data]

                    if missing_fields:
                        results.append({
                            "external_order_id": order_id,
                            "status": "error",
                            "error": f'Missing required fields: {", ".join(missing_fields)}'
                        })
                        continue

                    # Process the order
                    pos_order, order_error = self._process_pos_order(
                        order_data,
                        pos_config_id=pos_config_id,
                        default_partner_id=default_partner_id,
                        default_customer_ref=default_customer_ref,
                    )

                    if order_error:
                        results.append({
                            "external_order_id": order_id,
                            "status": "error",
                            "error": order_error.get("message", "Unknown error")
                        })
                    else:
                        # Calculate tax percent: (tax / untaxed) * 100
                        amount_untaxed = pos_order.amount_total - pos_order.amount_tax
                        tax_percent = (pos_order.amount_tax / amount_untaxed * 100) if amount_untaxed else 0.0
                        results.append({
                            "external_order_id": order_id,
                            "status": "success",
                            "pos_order_id": pos_order.id,
                            "pos_order_name": pos_order.name,
                            "amount_total": pos_order.amount_total,
                            "tax_percent": round(tax_percent, 2),
                        })

            except Exception as e:
                _logger.error(f"Error processing order {order_id}: {str(e)}", exc_info=True)
                results.append({
                    "external_order_id": order_id,
                    "status": "error",
                    "error": str(e)
                })

        return results

    def _validate_pos_session(self, pos_session):
        """Validate POS session and payment methods"""
        if not pos_session:
            return {
                "status": 400,
                "message": "No POS configuration found for external sync. "
                           "Please configure a POS for webhook integration."
            }

        payment_methods = pos_session.payment_method_ids
        if not payment_methods:
            return {
                "status": 400,
                "message": "No payment methods configured for this POS session."
            }

        missing_journals = [pm.name for pm in payment_methods if not pm.journal_id]
        if missing_journals:
            return {
                "status": 400,
                "message": f'Journal not found for payment method(s): {", ".join(missing_journals)}'
            }
        return None

    def _check_duplicate_order(self, external_order_id, external_order_source):
        """Check if order already exists"""
        if not external_order_id:
            return None

        existing = request.env["pos.order"].sudo().search([
            ("external_order_id", "=", external_order_id),
            ("external_order_source", "=", external_order_source),
        ], limit=1)

        if existing:
            return {
                "status": 400,
                "message": f"Duplicate order: OrderID {external_order_id} already exists as {existing.name}"
            }
        return None

    def _validate_order_status(self, order_status):
        """Validate order status against configured valid statuses"""
        if order_status is None:
            return None

        valid_statuses_str = request.env[IR_CONFIG_PARAMETER].sudo().get_param(
            "karage_pos.valid_order_statuses", "103,104"
        )
        valid_statuses = [
            int(s.strip()) for s in valid_statuses_str.split(",") if s.strip().isdigit()
        ]

        if order_status not in valid_statuses:
            return {
                "status": 400,
                "message": (
                    f"Invalid OrderStatus: {order_status}. "
                    f"Only completed orders ({', '.join(map(str, valid_statuses))}) are accepted."
                )
            }
        return None

    def _resolve_partner(self, partner_id=None, customer_ref=None):
        """
        Resolve partner for the order using multiple lookup strategies.

        Priority order:
        1. Direct partner_id (Odoo ID)
        2. Customer reference (partner's ref field)
        3. Default partner from settings

        :param partner_id: Direct Odoo partner ID
        :param customer_ref: External customer reference
        :return: res.partner record or None
        """
        partner_env = request.env["res.partner"].sudo()
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()

        # Strategy 1: Direct partner_id
        if partner_id:
            try:
                partner_id = int(partner_id)
                partner = partner_env.browse(partner_id)
                if partner.exists():
                    _logger.debug(f"Partner found by ID: {partner_id} -> {partner.name}")
                    return partner
                else:
                    _logger.warning(f"Partner ID {partner_id} does not exist")
            except (ValueError, TypeError):
                _logger.warning(f"Invalid partner_id: {partner_id}")

        # Strategy 2: Customer reference lookup
        if customer_ref:
            partner = partner_env.search([("ref", "=", customer_ref)], limit=1)
            if partner:
                _logger.debug(f"Partner found by ref: {customer_ref} -> {partner.name}")
                return partner
            else:
                _logger.warning(f"No partner found with ref: {customer_ref}")

        # Strategy 3: Default partner from settings
        default_partner_id = config_param.get_param("karage_pos.default_partner_id", "0")
        try:
            default_partner_id = int(default_partner_id)
        except (ValueError, TypeError):
            default_partner_id = 0

        if default_partner_id:
            partner = partner_env.browse(default_partner_id)
            if partner.exists():
                _logger.debug(f"Using default partner: {partner.name}")
                return partner
            else:
                _logger.warning(f"Default partner ID {default_partner_id} does not exist")

        _logger.warning("No partner resolved - invoice creation will fail")
        return None

    def _parse_order_datetime(self, order_date):
        """Parse OrderDate from payload, returning datetime in UTC"""
        from datetime import datetime, timezone

        if not order_date:
            return fields.Datetime.now()

        try:
            parsed_dt = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
            if parsed_dt.tzinfo is not None:
                return parsed_dt.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed_dt
        except (ValueError, AttributeError):
            _logger.warning(f"Could not parse OrderDate: {order_date}. Using current time.")
            return fields.Datetime.now()

    def _transform_to_odoo_format(self, webhook_data, pos_session, order_lines, payment_lines, partner=None):
        """
        Transform webhook order data to Odoo's sync_from_ui format.

        This transforms the webhook JSON into the format expected by Odoo's
        standard POS order processing methods (_process_order, sync_from_ui).

        :param webhook_data: Original webhook data dict
        :param pos_session: POS session record
        :param order_lines: Prepared order lines in Odoo format
        :param payment_lines: Prepared payment lines in Odoo format
        :param partner: Optional res.partner record for invoicing
        :return: Dict in Odoo's sync_from_ui format
        """
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()
        external_order_source = config_param.get_param(
            "karage_pos.external_order_source_code", "karage_pos_webhook"
        )

        # Generate unique identifiers
        order_uuid = str(uuid4())
        order_name = f"Order {order_uuid[:15]}"

        # Parse order datetime
        order_datetime = self._parse_order_datetime(webhook_data.get("OrderDate"))

        # Calculate totals from lines and payments
        total_amount_incl = sum(line[2]['price_subtotal_incl'] for line in order_lines)
        total_amount_base = sum(line[2]['price_subtotal'] for line in order_lines)
        total_paid = sum(line[2]['amount'] for line in payment_lines)

        # Build Odoo order data structure
        # Include both Odoo 17 and Odoo 18+ field names for compatibility
        odoo_order = {
            # Core identifiers
            'name': order_name,
            'uuid': order_uuid,
            'access_token': str(uuid4()),

            # Session and config (include both field names for version compatibility)
            'session_id': pos_session.id,          # Odoo 18+
            'pos_session_id': pos_session.id,      # Odoo 17
            'user_id': pos_session.user_id.id,
            'pricelist_id': pos_session.config_id.pricelist_id.id,
            'fiscal_position_id': (
                pos_session.config_id.default_fiscal_position_id.id
                if pos_session.config_id.default_fiscal_position_id
                else False
            ),

            # Order details
            'date_order': fields.Datetime.to_string(order_datetime),
            'partner_id': partner.id if partner else False,
            'to_invoice': bool(partner),  # Only invoice if we have a partner
            'sequence_number': randint(1, 99999),
            'last_order_preparation_change': '{}',

            # Amounts
            'amount_paid': total_paid,
            'amount_return': 0,
            'amount_tax': total_amount_incl - total_amount_base,
            'amount_total': total_paid,  # Use payment total as order total

            # Lines and payments (include both field names for version compatibility)
            'lines': order_lines,
            'payment_ids': payment_lines,          # Odoo 18+
            'statement_ids': payment_lines,        # Odoo 17

            # State - 'paid' triggers _process_saved_order flow
            'state': 'paid',

            # External order tracking fields (handled by overridden _process_order)
            'external_order_id': str(webhook_data.get("OrderID", "")),
            'external_order_source': external_order_source,
            'external_order_date': order_datetime,
        }

        return odoo_order

    def _is_picking_config_valid(self, pos_order):
        """Check if picking type is properly configured for inventory operations."""
        picking_type = pos_order.config_id.picking_type_id
        if not picking_type:
            _logger.warning(
                f"POS config '{pos_order.config_id.name}' has no picking type configured. "
                f"Skipping inventory operations for order {pos_order.name}."
            )
            return False

        if not picking_type.default_location_src_id:
            _logger.warning(
                f"Picking type '{picking_type.name}' has no source location configured. "
                f"Skipping inventory operations for order {pos_order.name}."
            )
            return False

        return True

    def _finalize_order(self, pos_order):
        """
        Finalize a draft POS order with resilient error handling.

        This method processes the order after creation, handling:
        - Payment confirmation (critical - must succeed)
        - Picking creation (non-critical - failure logged but doesn't fail order)
        - Invoice creation (non-critical - failure logged but doesn't fail order)

        :param pos_order: The draft POS order to finalize
        :return: True on success, error dict on critical failure
        """
        try:
            # Confirm payment (critical - must succeed)
            pos_order.action_pos_order_paid()
            _logger.info(f"Payment confirmed for order {pos_order.name}")
        except Exception as e:
            _logger.error(f"Could not confirm payment for order {pos_order.name}: {e}")
            return {"status": 500, "message": f"Payment confirmation failed: {str(e)}"}

        # Refresh picking_ids from database (action_pos_order_paid may have created one)
        pos_order.invalidate_recordset(['picking_ids'])

        # Create picking with savepoint (non-critical)
        # Only create if no picking exists yet (action_pos_order_paid may have created one)
        if self._is_picking_config_valid(pos_order) and not pos_order.picking_ids:
            try:
                with request.env.cr.savepoint():
                    pos_order._create_order_picking()
                    _logger.info(f"Picking created for order {pos_order.name}")
            except Exception as e:
                _logger.warning(f"Could not create picking for order {pos_order.name}: {e}")
        elif pos_order.picking_ids:
            _logger.debug(f"Picking already exists for order {pos_order.name}, skipping creation")

        # Compute costs
        try:
            pos_order._compute_total_cost_in_real_time()
        except Exception as e:
            _logger.warning(f"Could not compute costs for order {pos_order.name}: {e}")

        # Generate invoice with savepoint (non-critical)
        _logger.info(
            f"Invoice check for order {pos_order.name}: "
            f"to_invoice={pos_order.to_invoice}, state={pos_order.state}, partner_id={pos_order.partner_id.id if pos_order.partner_id else False}"
        )
        if pos_order.to_invoice and pos_order.state == 'paid' and pos_order.partner_id:
            try:
                with request.env.cr.savepoint():
                    pos_order._generate_pos_order_invoice()
                    pos_order.invalidate_recordset(['account_move'])
                    _logger.info(f"Invoice created for order {pos_order.name}: {pos_order.account_move.name if pos_order.account_move else 'N/A'}")
            except Exception as e:
                _logger.warning(f"Could not create invoice for order {pos_order.name}: {e}", exc_info=True)
        else:
            _logger.info(
                f"Skipping invoice for order {pos_order.name}: "
                f"to_invoice={pos_order.to_invoice}, state={pos_order.state}, partner_id={pos_order.partner_id.id if pos_order.partner_id else False}"
            )

        # Mark order as 'done' to prevent session closing from reprocessing it
        # This prevents duplicate pickings during action_pos_session_closing_control
        if pos_order.state == 'paid':
            pos_order.write({'state': 'done'})
            _logger.info(f"Order {pos_order.name} marked as done")

        return True

    def _process_pos_order(self, data, pos_config_id=None, default_partner_id=None, default_customer_ref=None):
        """
        Process POS order from webhook data with resilient error handling.

        This method creates the order as draft first, then manually processes
        payment, picking, and invoicing with proper error isolation. This ensures
        picking/invoice failures don't prevent order creation.

        :param data: Validated webhook data
        :param pos_config_id: Optional POS config ID to use (falls back to default from settings)
        :param default_partner_id: Optional default partner ID (can be overridden by order-level partner_id)
        :param default_customer_ref: Optional default customer ref (can be overridden by order-level customer_ref)
        :return: Tuple of (pos_order, error_dict or None)
        """
        try:
            # Get or create POS session for external sync
            pos_session = self._get_or_create_external_session(pos_config_id=pos_config_id)

            # Validate POS session
            session_error = self._validate_pos_session(pos_session)
            if session_error:
                return None, session_error

            # Get configuration parameters for duplicate check
            config_param = request.env[IR_CONFIG_PARAMETER].sudo()
            external_order_source = config_param.get_param(
                "karage_pos.external_order_source_code", "karage_pos_webhook"
            )

            # Check for duplicate external order ID
            external_order_id = str(data.get("OrderID", ""))
            duplicate_error = self._check_duplicate_order(external_order_id, external_order_source)
            if duplicate_error:
                return None, duplicate_error

            # Validate OrderStatus
            status_error = self._validate_order_status(data.get("OrderStatus"))
            if status_error:
                return None, status_error

            # Prepare order lines in Odoo sync_from_ui format
            order_lines, lines_error = self._prepare_order_lines(
                data.get("OrderItems", []), pos_session
            )
            if lines_error:
                return None, lines_error

            # Prepare payment lines in Odoo sync_from_ui format
            payment_lines, payment_error = self._prepare_payment_lines(
                data.get("CheckoutDetails", []), pos_session
            )
            if payment_error:
                return None, payment_error

            # Resolve partner for invoicing (order-level overrides top-level defaults)
            order_partner_id = data.get("partner_id") or default_partner_id
            order_customer_ref = data.get("customer_ref") or default_customer_ref
            partner = self._resolve_partner(
                partner_id=order_partner_id,
                customer_ref=order_customer_ref,
            )

            # Transform webhook data to Odoo's sync_from_ui format
            # Set state to 'draft' so _process_order creates order without
            # triggering picking/invoice creation - we'll handle that manually
            odoo_order_data = self._transform_to_odoo_format(
                data, pos_session, order_lines, payment_lines, partner=partner
            )
            odoo_order_data['state'] = 'draft'  # Create as draft first

            _logger.info(
                f"Transformed order data: state={odoo_order_data.get('state')}, "
                f"session_id={odoo_order_data.get('session_id')}, "
                f"to_invoice={odoo_order_data.get('to_invoice')}"
            )

            # Use Odoo's _process_order method to create the order
            pos_order_model = request.env["pos.order"].sudo()

            try:
                # Try Odoo 18+ signature first (2 arguments)
                # Odoo 18+: _process_order(order, existing_order)
                _logger.info("Attempting Odoo 18+ _process_order signature (2 args)")
                order_id = pos_order_model._process_order(odoo_order_data, False)
                _logger.info(f"Odoo 18+ signature succeeded, order_id={order_id}")
            except TypeError as e:
                # Fall back to Odoo 17.0 signature (3 arguments)
                # Odoo 17: _process_order(order, draft, existing_order)
                # - order: dict with 'data' key containing order data
                # - draft: boolean - True to skip picking/invoice creation
                # - existing_order: existing order to update or False
                _logger.info(f"Odoo 18+ signature failed ({e}), falling back to Odoo 17")
                wrapped_order = {
                    'data': odoo_order_data,
                    'id': odoo_order_data.get('name', str(uuid4())),
                    'to_invoice': odoo_order_data.get('to_invoice', True),
                }
                _logger.info(f"Wrapped order id={wrapped_order.get('id')}, calling with draft=True")
                # Pass draft=True to skip picking/invoice in _process_saved_order
                # We'll handle payment, picking, invoice ourselves with error handling
                order_id = pos_order_model._process_order(wrapped_order, True, False)
                _logger.info(f"Odoo 17 signature succeeded, order_id={order_id}")

            if not order_id:
                return None, {"status": 500, "message": "Order creation failed - no order ID returned"}

            pos_order = pos_order_model.browse(order_id)

            # Update with external tracking fields, partner, and invoice flag
            pos_order.write({
                'external_order_id': external_order_id,
                'external_order_source': external_order_source,
                'external_order_date': self._parse_order_datetime(data.get("OrderDate")),
                'partner_id': partner.id if partner else False,
                'to_invoice': bool(partner),  # Only invoice if we have a partner
            })

            _logger.info(
                f"Order {pos_order.id} created as draft: "
                f"name={pos_order.name}, external_order_id={external_order_id}"
            )

            # Now finalize the order with resilient error handling
            finalize_result = self._finalize_order(pos_order)
            if isinstance(finalize_result, dict):
                # Critical error during finalization
                return None, finalize_result

            _logger.info(
                f"Order {pos_order.id} finalized: "
                f"name={pos_order.name}, state={pos_order.state}, "
                f"amount_total={pos_order.amount_total}, amount_paid={pos_order.amount_paid}"
            )

            return pos_order, None

        except Exception as e:
            _logger.error(f"Error processing POS order: {str(e)}", exc_info=True)
            return None, {"status": 500, "message": str(e)}

    def _get_or_create_external_session(self, pos_config_id=None):
        """
        Get or create a POS session for external webhook integration

        Strategy:
        1. Use provided pos_config_id or get from settings
        2. Look for an open session for that config
        3. Create a new session if needed
        4. Return the session

        :param pos_config_id: Optional POS config ID from request (falls back to default from settings)
        :return: pos.session record or None
        """
        pos_session_env = request.env["pos.session"].sudo()
        pos_config_env = request.env["pos.config"].sudo()
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()

        # Use provided pos_config_id or fall back to configured default
        if pos_config_id:
            try:
                pos_config_id = int(pos_config_id)
            except (ValueError, TypeError):
                _logger.warning(f"Invalid pos_config_id provided: {pos_config_id}, falling back to default")
                pos_config_id = None

        if not pos_config_id:
            # Fall back to configured default
            pos_config_id = config_param.get_param("karage_pos.external_pos_config_id", "0")
            try:
                pos_config_id = int(pos_config_id)
            except (ValueError, TypeError):
                pos_config_id = 0

        if not pos_config_id:
            _logger.error(
                "No POS configuration provided in request and no default set in Karage POS settings. "
                "Please provide pos_config_id in request body or configure 'External POS Configuration' in Settings > Karage POS"
            )
            return None

        # Get configured acceptable session states
        states_str = config_param.get_param(
            "karage_pos.acceptable_session_states", "opened,opening_control"
        )
        acceptable_states = [s.strip() for s in states_str.split(",") if s.strip()]

        # Get the POS config
        pos_config = pos_config_env.browse(pos_config_id)
        if not pos_config.exists():
            _logger.error(f"Configured POS config ID {pos_config_id} does not exist")
            return None

        # 1. Check if there's already an open session for this config
        existing_session = pos_session_env.search([
            ("config_id", "=", pos_config.id),
            ("state", "in", acceptable_states),
        ], limit=1)

        if existing_session:
            _logger.info(f"Found existing open session for config {pos_config.name}: {existing_session.name}")
            return existing_session

        # 2. Check for sessions stuck in closing_control and complete their closing
        closing_session = pos_session_env.search([
            ("config_id", "=", pos_config.id),
            ("state", "=", "closing_control"),
        ], limit=1)

        if closing_session:
            _logger.info(f"Found session in closing_control state: {closing_session.name}, completing close")
            try:
                from odoo import SUPERUSER_ID
                # Use SUPERUSER and bypass context to close stuck session
                bypass_context = {
                    'force_delete': True,
                    'bypass_account_move_restriction': True,
                }
                session_to_close = closing_session.with_user(SUPERUSER_ID).with_context(**bypass_context)
                session_to_close.action_pos_session_close()
                _logger.info(f"Session {closing_session.name} closed successfully")
            except Exception as e:
                _logger.warning(f"Could not close session {closing_session.name}: {e}, attempting force close")
                # If we can't close it, use the force-close fallback
                self._force_close_session(closing_session)

        # 3. Create a new session for external sync
        try:
            # Use the current request user for the session
            session_user_id = request.env.user.id
            _logger.info(f"Creating new POS session for external sync using config: {pos_config.name}")
            new_session = pos_session_env.create({
                "config_id": pos_config.id,
                "user_id": session_user_id,
            })

            # Open the session
            new_session.action_pos_session_open()
            _logger.info(f"Successfully created and opened POS session: {new_session.name}")
            return new_session

        except Exception as e:
            _logger.error(f"Failed to create POS session for external sync: {str(e)}", exc_info=True)
            return None

    def _get_current_external_session(self, pos_config_id=None):
        """
        Get the current external POS session without creating a new one.

        Used to retrieve the session for closing after order processing.

        :param pos_config_id: Optional POS config ID from request (falls back to default from settings)
        :return: pos.session record or None
        """
        pos_session_env = request.env["pos.session"].sudo()
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()

        # Use provided pos_config_id or fall back to configured default
        if pos_config_id:
            try:
                pos_config_id = int(pos_config_id)
            except (ValueError, TypeError):
                pos_config_id = None

        if not pos_config_id:
            pos_config_id = config_param.get_param("karage_pos.external_pos_config_id", "0")
            try:
                pos_config_id = int(pos_config_id)
            except (ValueError, TypeError):
                return None

        if not pos_config_id:
            return None

        # Look for open or opening_control sessions
        return pos_session_env.search([
            ("config_id", "=", pos_config_id),
            ("state", "in", ["opened", "opening_control"]),
        ], limit=1)

    def _close_and_post_session(self, pos_session):
        """
        Close and post a POS session after processing orders.

        This creates the accounting journal entries and marks the session as closed.
        The session closing is non-critical - if it fails, orders are still processed.

        :param pos_session: POS session to close
        """
        from odoo import SUPERUSER_ID

        if not pos_session or pos_session.state == 'closed':
            return

        session_name = pos_session.name
        original_state = pos_session.state

        try:
            # Use SUPERUSER_ID and context flags to bypass custom permission restrictions
            # Many custom modules (like accounting_access) check these context flags
            bypass_context = {
                'force_delete': True,
                'bypass_account_move_restriction': True,
                'skip_account_move_synchronization': True,
                'installing_modules': True,  # Common bypass flag
            }
            pos_session = pos_session.with_user(SUPERUSER_ID).with_context(**bypass_context)
            _logger.info(f"Closing POS session {session_name} (state: {original_state})")

            # Try to close the session through standard Odoo flow
            # action_pos_session_closing_control() handles the full flow for sessions without cash control
            if pos_session.state in ('opened', 'opening_control'):
                pos_session.action_pos_session_closing_control()
                pos_session.invalidate_recordset(['state'])
                _logger.info(f"POS session {session_name} state after closing_control: {pos_session.state}")

            # If session is in closing_control, complete the close
            if pos_session.state == 'closing_control':
                pos_session.action_pos_session_close()
                pos_session.invalidate_recordset(['state', 'move_id'])

            # Final state check and logging
            pos_session.invalidate_recordset(['state', 'move_id'])
            _logger.info(
                f"POS session {session_name} final state: {pos_session.state}, "
                f"Journal entry: {pos_session.move_id.name if pos_session.move_id else 'N/A'}"
            )

        except Exception as e:
            # Standard close failed (e.g., due to custom permission modules like accounting_access)
            # Fall back to force-closing the session
            _logger.warning(
                f"Standard session close failed for {session_name}: {e}. "
                "Attempting force close..."
            )
            self._force_close_session(pos_session)

    def _force_close_session(self, pos_session):
        """
        Force close a POS session when standard closing fails.

        This is a fallback when custom permission modules block normal closing.
        It tries to complete essential steps and force the state to 'closed'.

        :param pos_session: POS session to force close (should already have SUPERUSER context)
        """
        from odoo import SUPERUSER_ID

        session_name = pos_session.name
        _logger.info(f"Force closing POS session {session_name}")

        # Ensure we have elevated permissions
        pos_session = pos_session.with_user(SUPERUSER_ID).with_context(
            force_delete=True,
            bypass_account_move_restriction=True,
        )

        try:
            # Mark all paid orders as done (this is normally done during close)
            paid_orders = pos_session.env['pos.order'].sudo().search([
                ('session_id', '=', pos_session.id),
                ('state', '=', 'paid')
            ])
            if paid_orders:
                paid_orders.write({'state': 'done'})
                _logger.info(f"Marked {len(paid_orders)} orders as 'done' for session {session_name}")

            # If there's an empty move created during closing attempt, try to remove it
            if pos_session.move_id and not pos_session.move_id.line_ids:
                try:
                    pos_session.move_id.with_context(force_delete=True).sudo().unlink()
                    _logger.info(f"Removed empty journal entry for session {session_name}")
                except Exception as unlink_error:
                    _logger.warning(f"Could not remove empty move: {unlink_error}")
                    # Clear the move_id reference even if we can't delete the move
                    pos_session.sudo().write({'move_id': False})

            # Force the session state to closed
            pos_session.sudo().write({'state': 'closed'})
            _logger.info(f"Force closed POS session {session_name}")

        except Exception as e:
            _logger.error(f"Force close failed for session {session_name}: {e}", exc_info=True)

    def _build_product_search_domain(self, name_condition, item_name, company_id,
                                     require_sale_ok, require_available_in_pos):
        """Build product search domain based on configuration"""
        domain = [(name_condition[0], name_condition[1], item_name)]
        if require_sale_ok:
            domain.append(("sale_ok", "=", True))
        if require_available_in_pos:
            domain.append(("available_in_pos", "=", True))
        domain.extend(["|", ("company_id", "=", False), ("company_id", "=", company_id)])
        return domain

    def _find_product_by_direct_id(self, product_env, product_id, id_type):
        """Try to find product by direct ID (OdooItemID or ItemID)"""
        if not product_id or product_id <= 0:
            return None, None

        product = product_env.browse(product_id)
        if product.exists():
            log_level = _logger.debug if id_type == "OdooItemID" else _logger.info
            log_level(f"Product found by {id_type}: {product_id}")
            return product, id_type

        if id_type == "OdooItemID":
            _logger.warning(f"OdooItemID {product_id} does not exist")
        return None, None

    def _find_product_by_name(self, product_env, item_name, company_id, config_param):
        """Find product by name (exact then fuzzy match)"""
        if not item_name:
            return None, None

        require_sale_ok = config_param.get_param(
            "karage_pos.product_require_sale_ok", "True"
        ).lower() == "true"
        require_available_in_pos = config_param.get_param(
            "karage_pos.product_require_available_in_pos", "True"
        ).lower() == "true"

        # Exact match
        exact_domain = self._build_product_search_domain(
            ("name", "="), item_name, company_id, require_sale_ok, require_available_in_pos
        )
        product = product_env.search(exact_domain, limit=1)
        if product:
            _logger.warning(
                f"Product found by exact ItemName match: '{item_name}'. "
                f"Consider using OdooItemID for better performance."
            )
            return product, "ItemName (exact)"

        # Fuzzy match
        fuzzy_domain = self._build_product_search_domain(
            ("name", "ilike"), item_name, company_id, require_sale_ok, require_available_in_pos
        )
        product = product_env.search(fuzzy_domain, limit=1)
        if product:
            _logger.warning(
                f"Product found by fuzzy ItemName match: '{item_name}' -> '{product.name}'. "
                f"Consider using OdooItemID for accuracy."
            )
            return product, "ItemName (fuzzy)"

        return None, None

    def _find_product_by_id(self, odoo_item_id, item_id, item_name, pos_session):
        """
        Find product by OdooItemID (preferred), ItemID, or ItemName

        Priority order:
        1. OdooItemID (direct product_id)
        2. ItemID (legacy support)
        3. ItemName (exact match)
        4. ItemName (fuzzy match with warning)

        :param odoo_item_id: Direct Odoo product_id (preferred)
        :param item_id: Legacy ItemID
        :param item_name: Product name for fallback
        :param pos_session: POS session for company context
        :return: Tuple of (product, lookup_method) or (None, None)
        """
        product_env = request.env["product.product"].sudo()
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()
        company_id = pos_session.config_id.company_id.id

        # Priority 1: OdooItemID (direct product_id)
        product, method = self._find_product_by_direct_id(product_env, odoo_item_id, "OdooItemID")
        if product:
            return product, method

        # Priority 2: ItemID (legacy support)
        product, method = self._find_product_by_direct_id(product_env, item_id, "ItemID")
        if product:
            return product, method

        # Priority 3 & 4: ItemName (exact then fuzzy match)
        return self._find_product_by_name(product_env, item_name, company_id, config_param)

    def _get_product_validation_config(self):
        """Get product validation settings from config parameters"""
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()
        return {
            "require_sale_ok": config_param.get_param(
                "karage_pos.product_require_sale_ok", "True"
            ).lower() == "true",
            "require_available_in_pos": config_param.get_param(
                "karage_pos.product_require_available_in_pos", "True"
            ).lower() == "true",
            "enforce_company_match": config_param.get_param(
                "karage_pos.enforce_product_company_match", "True"
            ).lower() == "true",
        }

    def _create_product_error(self, product, message_suffix):
        """Create a standardized product validation error"""
        return {
            "status": 400,
            "message": f"Product '{product.name}' (ID: {product.id}) {message_suffix}"
        }

    def _resolve_validation_settings(self, require_sale_ok, require_available_in_pos,
                                     enforce_company_match):
        """Resolve validation settings, loading from config if None"""
        if None not in (require_sale_ok, require_available_in_pos, enforce_company_match):
            return require_sale_ok, require_available_in_pos, enforce_company_match

        config = self._get_product_validation_config()
        return (
            require_sale_ok if require_sale_ok is not None else config["require_sale_ok"],
            require_available_in_pos if require_available_in_pos is not None else config["require_available_in_pos"],
            enforce_company_match if enforce_company_match is not None else config["enforce_company_match"],
        )

    def _validate_product_for_pos(self, product, pos_session,
                                  require_sale_ok=None, require_available_in_pos=None,
                                  enforce_company_match=None):
        """
        Validate product is suitable for POS order

        :param product: Product to validate
        :param pos_session: POS session for company context
        :param require_sale_ok: Override config setting (for testing)
        :param require_available_in_pos: Override config setting (for testing)
        :param enforce_company_match: Override config setting (for testing)
        :return: None if valid, error dict if invalid
        """
        if not product:
            return {"status": 404, "message": "Product not found"}

        require_sale_ok, require_available_in_pos, enforce_company_match = \
            self._resolve_validation_settings(
                require_sale_ok, require_available_in_pos, enforce_company_match
            )

        if not product.active:
            return self._create_product_error(product, "is not active")

        if require_sale_ok and not product.sale_ok:
            return self._create_product_error(product, "is not available for sale")

        if require_available_in_pos and not product.available_in_pos:
            return self._create_product_error(product, "is not available in POS")

        if enforce_company_match and product.company_id:
            if product.company_id.id != pos_session.config_id.company_id.id:
                return self._create_product_error(product, "belongs to a different company")

        return None

    def _prepare_order_lines(self, order_items, pos_session):
        """Prepare order lines from order items in Odoo sync_from_ui format.

        Returns order lines with all fields needed by Odoo's _process_order method.
        Uses product taxes from Odoo to calculate tax amounts.
        """
        order_lines = []

        # Get fiscal position from POS config (if any)
        fiscal_position = pos_session.config_id.default_fiscal_position_id

        for order_item in order_items:
            item_name = order_item.get("ItemName", "").strip()
            item_id = order_item.get("ItemID", 0)
            odoo_item_id = order_item.get("OdooItemID", 0)
            price = float(order_item.get("PriceWithoutTax", 0))
            quantity = float(order_item.get("Quantity", 1))
            discount_percent = float(order_item.get("DiscountPercentage", 0))

            # Find product using helper
            product, _ = self._find_product_by_id(
                odoo_item_id, item_id, item_name, pos_session
            )

            if not product:
                return None, {
                    "status": 404,
                    "message": f'Product not found: OdooItemID={odoo_item_id}, ItemID={item_id}, ItemName="{item_name}"'
                }

            # Validate product for POS
            validation_error = self._validate_product_for_pos(product, pos_session)
            if validation_error:
                return None, validation_error

            # Get product taxes, mapped through fiscal position if applicable
            product_taxes = product.taxes_id
            if fiscal_position:
                product_taxes = fiscal_position.map_tax(product_taxes)

            # Calculate price after discount
            price_after_discount = price * (1 - discount_percent / 100.0)

            # Use Odoo's tax computation to calculate amounts
            # PriceWithoutTax is tax-excluded, so compute_all adds tax on top
            tax_computation = product_taxes.compute_all(
                price_after_discount,
                currency=pos_session.currency_id,
                quantity=quantity,
                product=product,
                partner=False,
            )

            price_subtotal = tax_computation['total_excluded']
            price_subtotal_incl = tax_computation['total_included']

            # Build order line in Odoo sync_from_ui format
            order_lines.append((0, 0, {
                # Required by Odoo's sync_from_ui format
                "id": randint(1, 1000000),
                "uuid": str(uuid4()),
                "pack_lot_ids": [],

                # Product and pricing
                "product_id": product.id,
                "full_product_name": product.display_name,
                "qty": quantity,
                "price_unit": price,
                "discount": discount_percent,
                "price_subtotal": price_subtotal,
                "price_subtotal_incl": price_subtotal_incl,

                # Use product taxes
                "tax_ids": [(6, 0, product_taxes.ids)],
            }))

        if not order_lines:
            return None, {"status": 400, "message": "No valid order lines created"}

        return order_lines, None

    def _find_payment_method_by_card_type(self, card_type, pos_session):
        """Find payment method by CardType in journal name"""
        if not card_type:
            return None
        return pos_session.payment_method_ids.filtered(
            lambda p: p.journal_id and card_type.lower() in p.journal_id.name.lower()
        )[:1] or None

    def _find_payment_method_by_fallback(self, fallback_payment_method_id, pos_session):
        """Find payment method using fallback from config"""
        if not fallback_payment_method_id:
            return None
        default_pm = request.env["pos.payment.method"].sudo().browse(fallback_payment_method_id)
        if default_pm.exists() and default_pm in pos_session.payment_method_ids:
            return default_pm
        return None

    def _find_cash_payment_method(self, payment_mode, pos_session):
        """Find cash payment method for payment mode 1"""
        if payment_mode != 1:
            return None
        return pos_session.payment_method_ids.filtered(lambda p: p.is_cash_count)[:1] or None

    def _resolve_payment_method(self, payment_mode, card_type, pos_session,
                                fallback_payment_method_id):
        """Resolve payment method using multiple strategies"""
        # Strategy 1: CardType in journal name
        payment_method = self._find_payment_method_by_card_type(card_type, pos_session)
        if payment_method:
            return payment_method

        # Strategy 2: Fallback from config
        payment_method = self._find_payment_method_by_fallback(
            fallback_payment_method_id, pos_session
        )
        if payment_method:
            return payment_method

        # Strategy 3: Cash for payment mode 1
        return self._find_cash_payment_method(payment_mode, pos_session)

    def _get_payment_config(self):
        """Get payment configuration from settings"""
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()
        fallback_payment_mode = int(config_param.get_param(
            "karage_pos.fallback_payment_mode", "1"
        ))

        fallback_payment_method_id = config_param.get_param(
            "karage_pos.fallback_payment_method_id", "0"
        )
        try:
            fallback_payment_method_id = int(fallback_payment_method_id)
        except (ValueError, TypeError):
            fallback_payment_method_id = 0

        return fallback_payment_mode, fallback_payment_method_id

    def _prepare_payment_lines(self, checkout_details, pos_session):
        """Prepare payment lines from checkout details in Odoo sync_from_ui format.

        Payment amounts are taken directly from CheckoutDetails.
        Returns payment lines with all fields needed by Odoo's _process_order method.
        """
        payment_lines = []

        # Get configuration
        fallback_payment_mode, fallback_payment_method_id = self._get_payment_config()

        for checkout in checkout_details:
            payment_mode = checkout.get("PaymentMode", fallback_payment_mode)
            amount = float(str(checkout.get("AmountPaid", 0)).replace(",", ""))
            card_type = checkout.get("CardType", "Cash")

            if amount <= 0:
                continue

            # Resolve payment method using multiple strategies
            payment_method = self._resolve_payment_method(
                payment_mode, card_type, pos_session,
                fallback_payment_method_id
            )

            if not payment_method:
                return None, {
                    "status": 400,
                    "message": (
                        f'No payment method found for PaymentMode={payment_mode}, CardType={card_type}. '
                        f'Please configure payment methods in Settings > Karage POS or check your fallback payment method.'
                    )
                }

            if not payment_method.journal_id:
                return None, {
                    "status": 400,
                    "message": f"Journal not found for payment method: {payment_method.name}"
                }

            # Build payment line in Odoo sync_from_ui format
            # Note: 'name' is used for datetime in sync_from_ui format
            payment_lines.append((0, 0, {
                "amount": amount,
                "name": fields.Datetime.now(),
                "payment_method_id": payment_method.id,
            }))

        if not payment_lines:
            return None, {"status": 400, "message": "No valid payment lines created"}

        return payment_lines, None
