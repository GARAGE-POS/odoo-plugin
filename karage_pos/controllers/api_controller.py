# -*- coding: utf-8 -*-

import json
import logging
import time

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

        Expected JSON format (array of orders):
        [
            {
                "OrderID": "11112111",
                "OrderDate": "2025-08-10T17:16:43+00:00",
                "OrderStatus": 103,
                "OrderItems": [
                    {
                        "ItemID": 35722,
                        "Price": 18.75,
                        "Quantity": 1,
                        "DiscountAmount": 0
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

            # 6. Validate payload is an array of orders
            if not isinstance(data, list):
                error_msg = 'Request body must be an array of orders'
                self._update_log(webhook_log, 400, error_msg, False, start_time=start_time)
                return self._json_response(None, status=400, error=error_msg)

            orders_data = data

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
            results = self._process_bulk_orders(orders_data)

            # 9. Determine overall status
            total = len(results)
            successful = sum(1 for r in results if r["status"] == "success")
            failed = total - successful

            if successful == total:
                status_code = 200
            elif successful == 0:
                status_code = 400
            else:
                status_code = 207  # Multi-Status

            # 10. Prepare response
            response_data = {
                "total": total,
                "successful": successful,
                "failed": failed,
                "results": results,
            }

            # 11. Update webhook log
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

    def _process_bulk_orders(self, orders_data):
        """
        Process multiple orders independently

        :param orders_data: List of order data dicts
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
                    pos_order, order_error = self._process_pos_order(order_data)

                    if order_error:
                        results.append({
                            "external_order_id": order_id,
                            "status": "error",
                            "error": order_error.get("message", "Unknown error")
                        })
                    else:
                        results.append({
                            "external_order_id": order_id,
                            "status": "success",
                            "pos_order_id": pos_order.id,
                            "pos_order_name": pos_order.name,
                            "amount_total": pos_order.amount_total,
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
            "karage_pos.valid_order_statuses", "103"
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

    def _process_pos_order(self, data):
        """
        Process POS order from webhook data

        :param data: Validated webhook data
        :return: Tuple of (pos_order, error_dict or None)
        """
        try:
            # Get or create POS session for external sync
            pos_session = self._get_or_create_external_session()

            # Validate POS session
            session_error = self._validate_pos_session(pos_session)
            if session_error:
                return None, session_error

            # Get configuration parameters
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

            # Parse OrderDate
            order_datetime = self._parse_order_datetime(data.get("OrderDate"))

            # Prepare order lines
            order_lines, lines_error = self._prepare_order_lines(
                data.get("OrderItems", []), pos_session
            )
            if lines_error:
                return None, lines_error

            # Prepare payment lines
            payment_lines, payment_error = self._prepare_payment_lines(
                data.get("CheckoutDetails", []), pos_session
            )
            if payment_error:
                return None, payment_error

            # Use total from payment lines (sum of CheckoutDetails AmountPaid)
            total_paid = sum(line[2]["amount"] for line in payment_lines)

            # Create POS order - use payment total as the order total
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
                "date_order": order_datetime,  # Use external timestamp
                "partner_id": False,
                "to_invoice": True,
                "lines": order_lines,
                "amount_total": total_paid,
                "amount_tax": 0.0,
                "amount_paid": total_paid,
                "amount_return": 0.0,
                # External order tracking fields
                "external_order_id": external_order_id,
                "external_order_source": external_order_source,
                "external_order_date": order_datetime,
            }

            pos_order = request.env["pos.order"].sudo().create(order_vals)

            # Create payments separately (required for Odoo 18)
            for payment_line in payment_lines:
                payment_vals = payment_line[2].copy()
                payment_vals["pos_order_id"] = pos_order.id
                payment_vals["session_id"] = pos_session.id
                request.env["pos.payment"].sudo().create(payment_vals)

            # Invalidate cache and refresh to ensure amount_paid is recalculated
            pos_order.invalidate_recordset(['amount_paid', 'payment_ids'])

            # Log payment status for debugging
            _logger.info(f"Order {pos_order.id}: amount_total={pos_order.amount_total}, amount_paid={pos_order.amount_paid}, payments={pos_order.payment_ids.mapped('amount')}")

            # Confirm the order
            try:
                pos_order.action_pos_order_paid()
            except Exception as e:
                _logger.error(f"Error confirming POS order: {str(e)}", exc_info=True)
                return None, {"status": 500, "message": f"Failed to confirm order: {str(e)}"}

            # Create picking for inventory
            try:
                pos_order._create_order_picking()
            except Exception as e:
                _logger.warning(f"Could not create picking for order {pos_order.name}: {str(e)}")

            # Generate invoice for accounting entries
            try:
                pos_order.action_pos_order_invoice()
            except Exception as e:
                _logger.warning(f"Could not create invoice for order {pos_order.name}: {str(e)}")

            return pos_order, None

        except Exception as e:
            _logger.error(f"Error processing POS order: {str(e)}", exc_info=True)
            return None, {"status": 500, "message": str(e)}

    def _get_or_create_external_session(self):
        """
        Get or create a POS session for external webhook integration

        Strategy:
        1. Get the configured POS config from settings
        2. Look for an open session for that config
        3. Create a new session if needed
        4. Return the session

        :return: pos.session record or None
        """
        pos_session_env = request.env["pos.session"].sudo()
        pos_config_env = request.env["pos.config"].sudo()
        config_param = request.env[IR_CONFIG_PARAMETER].sudo()

        # Get configured POS config ID
        pos_config_id = config_param.get_param("karage_pos.external_pos_config_id", "0")
        try:
            pos_config_id = int(pos_config_id)
        except (ValueError, TypeError):
            pos_config_id = 0

        if not pos_config_id:
            _logger.error(
                "No POS configuration set in Karage POS settings. "
                "Please configure 'External POS Configuration' in Settings > Karage POS"
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

        # 2. Create a new session for external sync
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
        """Prepare order lines from order items"""
        order_lines = []

        for order_item in order_items:
            item_name = order_item.get("ItemName", "").strip()
            item_id = order_item.get("ItemID", 0)
            odoo_item_id = order_item.get("OdooItemID", 0)
            price = float(order_item.get("Price", 0))
            quantity = float(order_item.get("Quantity", 1))
            discount_amount = float(order_item.get("DiscountAmount", 0))

            # Find product using new helper
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

            # Calculate discount percentage
            discount_percent = 0.0
            if price > 0 and discount_amount > 0:
                discount_percent = (discount_amount / (price * quantity)) * 100.0

            # Calculate line total (webhook prices are assumed to be final/tax-inclusive)
            price_after_discount = price * (1 - discount_percent / 100.0)
            subtotal = price_after_discount * quantity

            # Get taxes for the product (for display/reporting purposes only)
            # The actual amounts come from the webhook, not from Odoo tax computation
            taxes = product.taxes_id.filtered(
                lambda t: t.company_id.id == pos_session.config_id.company_id.id
            )

            fiscal_position = pos_session.config_id.default_fiscal_position_id
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)

            order_lines.append((0, 0, {
                "product_id": product.id,
                "full_product_name": product.display_name,
                "qty": quantity,
                "price_unit": price,
                "discount": discount_percent,
                "price_subtotal": subtotal,
                "price_subtotal_incl": subtotal,
                "tax_ids": [(6, 0, [])],  # Don't assign taxes - webhook provides final amounts
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
        """Prepare payment lines from checkout details

        Payment amounts are taken directly from CheckoutDetails.
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

            payment_lines.append((0, 0, {
                "payment_method_id": payment_method.id,
                "amount": amount,
                "payment_date": fields.Datetime.now(),
            }))

        if not payment_lines:
            return None, {"status": 400, "message": "No valid payment lines created"}

        return payment_lines, None
