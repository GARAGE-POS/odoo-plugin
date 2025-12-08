# -*- coding: utf-8 -*-

import json
import logging
import time

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class APIController(http.Controller):
    """REST API Controller for webhook endpoint"""

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
        except (ValueError, UnicodeDecodeError) as e:
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
                    pos_order=None, idempotency_record=None, start_time=None):
        """Update webhook log with processing result"""
        if not webhook_log:
            return

        try:
            webhook_log.update_log_result(
                status_code=status_code,
                response_message=message,
                success=success,
                pos_order_id=pos_order,
                processing_time=time.time() - start_time if start_time else None,
            )
        except Exception as e:
            _logger.warning(f"Error updating webhook log: {str(e)}")

    def _error_response(self, status, error_msg, webhook_log=None,
                        idempotency_record=None, start_time=None):
        """
        Create error response and update logs

        :param status: HTTP status code
        :param error_msg: Error message
        :param webhook_log: Webhook log record to update
        :param idempotency_record: Idempotency record to mark as failed
        :param start_time: Request start time for duration calculation
        :return: JSON error response
        """
        # Update idempotency record if exists
        if idempotency_record:
            try:
                idempotency_record.mark_failed(error_message=error_msg)
            except Exception as e:
                _logger.warning(f"Error updating idempotency record: {str(e)}")

        # Update webhook log
        self._update_log(webhook_log, status, error_msg, False,
                         idempotency_record=idempotency_record, start_time=start_time)

        # Return JSON response
        return self._json_response(None, status=status, error=error_msg)

    def _json_response(self, data, status=200, error=None):
        """Return standardized JSON response"""
        response_data = {
            "status": "success" if status == 200 else "error",
            "data": data if status == 200 else None,
            "error": error if error else None,
            "count": len(data) if isinstance(data, list) else (1 if data else 0),
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
        config_param = request.env["ir.config_parameter"].sudo()
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

    def _check_idempotency(self, idempotency_key, order_id, webhook_log, start_time):
        """
        Check idempotency and return cached response if duplicate

        :param idempotency_key: Idempotency key from request
        :param order_id: External order ID
        :param webhook_log: Webhook log record
        :param start_time: Request start time
        :return: Tuple of (should_process: bool, response_or_record)
                 - If should_process=False, response_or_record is the HTTP response to return
                 - If should_process=True, response_or_record is the idempotency record
        """
        if not idempotency_key:
            return True, None

        # Get or create idempotency record atomically
        idempotency_record, created = (
            request.env["karage.pos.webhook.log"]
            .sudo()
            .get_or_create_log(
                idempotency_key,
                order_id=str(order_id),
                status="processing",
            )
        )

        # Get log truncation length from config
        config_param = request.env["ir.config_parameter"].sudo()
        log_truncate_len = int(config_param.get_param("karage_pos.log_key_truncation_length", "20"))

        if created:
            # New request - proceed with processing
            _logger.info(f"New request with idempotency key: {idempotency_key[:log_truncate_len]}...")
            return True, idempotency_record

        # Record already exists - check status
        if idempotency_record.status == "completed":
            # Return cached response
            _logger.info(
                f"Duplicate request detected: {idempotency_key[:log_truncate_len]}... "
                f"Returning cached response for OrderID: {idempotency_record.order_id}"
            )
            self._update_log(
                webhook_log, 200, "Duplicate request - returning cached response",
                True, idempotency_record.pos_order_id, idempotency_record, start_time
            )

            # Parse and return cached response
            if idempotency_record.response_data:
                try:
                    cached_data = json.loads(idempotency_record.response_data)
                    return False, self._json_response(cached_data, status=200)
                except (ValueError, TypeError):
                    pass

            # Fallback response
            return False, self._json_response({
                "id": idempotency_record.pos_order_id.id if idempotency_record.pos_order_id else None,
                "name": idempotency_record.pos_order_id.name if idempotency_record.pos_order_id else None,
                "message": "Request already processed",
                "idempotency_key": idempotency_key,
            }, status=200)

        elif idempotency_record.status == "processing":
            # Check if stuck (timeout)
            if idempotency_record.create_date:
                from datetime import datetime, timedelta

                timeout_minutes = int(
                    request.env["ir.config_parameter"]
                    .sudo()
                    .get_param("karage_pos.idempotency_processing_timeout", default="5")
                )
                processing_timeout = timedelta(minutes=timeout_minutes)

                if datetime.now() - idempotency_record.create_date > processing_timeout:
                    _logger.warning(
                        f"Idempotency record stuck in processing state: {idempotency_key[:log_truncate_len]}... "
                        f"Allowing retry."
                    )
                    idempotency_record.write({"status": "processing"})
                    return True, idempotency_record

            # Still processing
            _logger.warning(f"Request already being processed: {idempotency_key[:log_truncate_len]}...")
            self._update_log(
                webhook_log, 409, "Request is already being processed. Please wait.",
                False, idempotency_record=idempotency_record, start_time=start_time
            )
            return False, self._json_response(
                None, status=409, error="Request is already being processed. Please wait."
            )

        elif idempotency_record.status == "failed":
            # Allow retry
            _logger.info(f"Retrying previously failed request: {idempotency_key[:log_truncate_len]}...")
            idempotency_record.mark_processing()
            return True, idempotency_record

        return True, idempotency_record

    # ========== Main Endpoint ==========

    @http.route(
        "/api/v1/webhook/pos-order",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def webhook_pos_order(self, **kwargs):
        """
        Webhook endpoint to create POS order from external system

        Expected JSON format:
        {
            "OrderID": 639,
            "AmountPaid": "92.0",
            "AmountTotal": 80.0,
            "GrandTotal": 92.0,
            "Tax": 12.0,
            "TaxPercent": 15.0,
            "CheckoutDetails": [...],
            "OrderItems": [...]
        }
        """
        start_time = time.time()
        webhook_log = None
        idempotency_record = None

        try:
            # 1. Validate HTTP method
            if request.httprequest.method != "POST":
                return self._json_response(
                    None, status=405, error="Method not allowed. Only POST requests are accepted."
                )

            # 2. Parse request body
            data, error = self._parse_request_body()
            if error:
                webhook_log = self._create_webhook_log(
                    request.httprequest.data.decode("utf-8", errors="ignore") if request.httprequest.data else "{}"
                )
                return self._error_response(400, error, webhook_log, start_time=start_time)

            # 3. Extract headers
            idempotency_key = self._get_header_or_body(
                data, "Idempotency-Key", "X-Idempotency-Key", "idempotency_key", "IdempotencyKey"
            )
            api_key = self._get_header_or_body(data, "X-API-KEY", "X-API-Key", "api_key")

            # 4. Create webhook log
            webhook_log = self._create_webhook_log(data, idempotency_key)

            # 5. Authenticate API key
            authenticated, auth_error = self._authenticate_api_key(api_key)
            if not authenticated:
                return self._error_response(401, auth_error, webhook_log, start_time=start_time)

            # 6. Check idempotency
            should_process, result = self._check_idempotency(
                idempotency_key, data.get("OrderID", ""), webhook_log, start_time
            )
            if not should_process:
                return result  # Return cached response or error

            idempotency_record = result

            # 7. Validate required fields
            required_fields = ["OrderID", "OrderItems", "CheckoutDetails", "AmountTotal", "AmountPaid"]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return self._error_response(
                    400, f'Missing required fields: {", ".join(missing_fields)}',
                    webhook_log, idempotency_record, start_time
                )

            # 8. Process the order
            pos_order, order_error = self._process_pos_order(data)
            if order_error:
                return self._error_response(
                    order_error.get("status", 500), order_error.get("message"),
                    webhook_log, idempotency_record, start_time
                )

            # 9. Prepare success response
            response_data = {
                "id": pos_order.id,
                "name": pos_order.name,
                "pos_reference": pos_order.pos_reference,
                "amount_total": pos_order.amount_total,
                "amount_paid": pos_order.amount_paid,
                "amount_tax": pos_order.amount_tax,
                "state": pos_order.state,
                "date_order": str(pos_order.date_order),
                "external_order_id": data.get("OrderID"),
            }

            # 10. Update idempotency record
            if idempotency_record:
                try:
                    idempotency_record.mark_completed(
                        pos_order_id=pos_order, response_data=json.dumps(response_data)
                    )
                except Exception as e:
                    _logger.warning(f"Error updating idempotency record: {str(e)}")

            # 11. Update webhook log with success
            self._update_log(
                webhook_log, 200, json.dumps(response_data), True,
                pos_order, idempotency_record, start_time
            )

            return self._json_response(response_data)

        except Exception as e:
            _logger.error(f"Unexpected error in webhook_pos_order: {str(e)}", exc_info=True)
            return self._error_response(
                500, f"Internal server error: {str(e)}",
                webhook_log, idempotency_record, start_time
            )

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
            "orders": [
                { /* order 1 data */ },
                { /* order 2 data */ },
                ...
            ]
        }

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

            # 3. Extract API key
            api_key = self._get_header_or_body(data, "X-API-KEY", "X-API-Key", "api_key")

            # 4. Create webhook log
            webhook_log = self._create_webhook_log(data)

            # 5. Authenticate API key
            authenticated, auth_error = self._authenticate_api_key(api_key)
            if not authenticated:
                self._update_log(webhook_log, 401, auth_error, False, start_time=start_time)
                return self._json_response(None, status=401, error=auth_error)

            # 6. Validate required fields
            if "orders" not in data:
                error_msg = 'Missing required field: "orders"'
                self._update_log(webhook_log, 400, error_msg, False, start_time=start_time)
                return self._json_response(None, status=400, error=error_msg)

            orders_data = data.get("orders", [])
            if not isinstance(orders_data, list):
                error_msg = '"orders" must be an array'
                self._update_log(webhook_log, 400, error_msg, False, start_time=start_time)
                return self._json_response(None, status=400, error=error_msg)

            # 7. Check bulk size limit
            max_orders = int(
                request.env["ir.config_parameter"]
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
                status_text = "success"
            elif successful == 0:
                status_code = 400
                status_text = "error"
            else:
                status_code = 207  # Multi-Status
                status_text = "partial_success"

            # 10. Prepare response
            response_data = {
                "total": total,
                "successful": successful,
                "failed": failed,
                "results": results,
            }

            # 11. Update webhook log
            processing_time = time.time() - start_time
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
                    # Validate required fields for this order
                    required_fields = ["OrderID", "OrderItems", "CheckoutDetails", "AmountTotal", "AmountPaid"]
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

    def _process_pos_order(self, data):
        """
        Process POS order from webhook data

        :param data: Validated webhook data
        :return: Tuple of (pos_order, error_dict or None)
        """
        try:
            # Get or create POS session for external sync
            pos_session = self._get_or_create_external_session()

            if not pos_session:
                return None, {
                    "status": 400,
                    "message": "No POS configuration found for external sync. Please configure a POS for webhook integration."
                }

            # Validate payment methods
            payment_methods = pos_session.payment_method_ids
            if not payment_methods:
                return None, {
                    "status": 400,
                    "message": "No payment methods configured for this POS session."
                }

            missing_journals = [
                pm.name for pm in payment_methods if not pm.journal_id
            ]
            if missing_journals:
                return None, {
                    "status": 400,
                    "message": f'Journal not found for payment method(s): {", ".join(missing_journals)}'
                }

            # Get configuration parameters
            config_param = request.env["ir.config_parameter"].sudo()
            external_order_source = config_param.get_param(
                "karage_pos.external_order_source_code", "karage_pos_webhook"
            )

            # Check for duplicate external order ID
            external_order_id = str(data.get("OrderID", ""))
            if external_order_id:
                existing = request.env["pos.order"].sudo().search([
                    ("external_order_id", "=", external_order_id),
                    ("external_order_source", "=", external_order_source),
                ], limit=1)
                if existing:
                    return None, {
                        "status": 400,
                        "message": f"Duplicate order: OrderID {external_order_id} already exists as {existing.name}"
                    }

            # Validate OrderStatus (only accept completed orders)
            order_status = data.get("OrderStatus")
            if order_status is not None:
                # Get valid statuses from config (default to 103)
                valid_statuses_str = request.env["ir.config_parameter"].sudo().get_param(
                    "karage_pos.valid_order_statuses", "103"
                )
                valid_statuses = [int(s.strip()) for s in valid_statuses_str.split(",") if s.strip().isdigit()]

                if order_status not in valid_statuses:
                    return None, {
                        "status": 400,
                        "message": f"Invalid OrderStatus: {order_status}. Only completed orders ({', '.join(map(str, valid_statuses))}) are accepted."
                    }

            # Parse OrderDate from payload (use external timestamp)
            from datetime import datetime, timezone
            order_date = data.get("OrderDate")
            if order_date:
                try:
                    # Handle ISO format with or without timezone
                    parsed_dt = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
                    # Convert to UTC and remove timezone info (Odoo expects naive datetime in UTC)
                    if parsed_dt.tzinfo is not None:
                        order_datetime = parsed_dt.astimezone(timezone.utc).replace(tzinfo=None)
                    else:
                        order_datetime = parsed_dt
                except (ValueError, AttributeError):
                    _logger.warning(f"Could not parse OrderDate: {order_date}. Using current time.")
                    order_datetime = fields.Datetime.now()
            else:
                order_datetime = fields.Datetime.now()

            # Parse amounts
            amount_paid = float(str(data.get("AmountPaid", 0)).replace(",", ""))
            grand_total = float(data.get("GrandTotal", 0))
            tax = float(data.get("Tax", 0))
            tax_percent = float(data.get("TaxPercent", 0))
            balance_amount = float(data.get("BalanceAmount", 0))

            # Validate data consistency
            currency = pos_session.config_id.currency_id
            rounding = currency.rounding

            # Get consistency check multiplier from config
            consistency_multiplier = float(config_param.get_param(
                "karage_pos.consistency_check_multiplier", "10.0"
            ))

            calculated_total, calculated_tax = self._calculate_totals(
                data.get("OrderItems", []), tax_percent, tax, config_param
            )

            if abs(calculated_total - grand_total) > rounding * consistency_multiplier:
                return None, {
                    "status": 400,
                    "message": f"Data inconsistency: Calculated total ({calculated_total}) does not match GrandTotal ({grand_total})"
                }

            if abs(amount_paid - grand_total) > rounding * consistency_multiplier and balance_amount > rounding:
                return None, {
                    "status": 400,
                    "message": f"Data inconsistency: AmountPaid ({amount_paid}) + BalanceAmount ({balance_amount}) should equal GrandTotal ({grand_total})"
                }

            # Prepare order lines
            order_lines, lines_error = self._prepare_order_lines(
                data.get("OrderItems", []), pos_session
            )
            if lines_error:
                return None, lines_error

            # Prepare payment lines
            payment_lines, payment_error = self._prepare_payment_lines(
                data.get("CheckoutDetails", []), pos_session, amount_paid, rounding
            )
            if payment_error:
                return None, payment_error

            # Calculate final totals
            final_total = sum(line[2]["price_subtotal_incl"] for line in order_lines)
            final_tax = sum(
                line[2]["price_subtotal_incl"] - line[2]["price_subtotal"]
                for line in order_lines
            )
            total_paid = sum(line[2]["amount"] for line in payment_lines)

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
                "date_order": order_datetime,  # Use external timestamp
                "partner_id": False,
                "to_invoice": False,
                "lines": order_lines,
                "amount_total": final_total,
                "amount_tax": final_tax,
                "amount_paid": total_paid,
                "amount_return": max(0.0, total_paid - final_total),
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

            return pos_order, None

        except Exception as e:
            _logger.error(f"Error processing POS order: {str(e)}", exc_info=True)
            return None, {"status": 500, "message": str(e)}

    def _calculate_totals(self, order_items, tax_percent, tax, config_param=None):
        """Calculate expected totals from order items"""
        calculated_total = 0.0
        for item in order_items:
            item_price = float(item.get("Price", 0))
            item_qty = float(item.get("Quantity", 1))
            item_discount = float(item.get("DiscountAmount", 0))
            calculated_total += (item_price * item_qty) - item_discount

        # Get tax calculation priority from config
        tax_priority = "percent_first"
        if config_param:
            tax_priority = config_param.get_param(
                "karage_pos.tax_calculation_priority", "percent_first"
            )

        if tax_priority == "percent_first":
            if tax_percent > 0:
                calculated_tax = calculated_total * (tax_percent / 100.0)
                calculated_total_with_tax = calculated_total + calculated_tax
            else:
                calculated_total_with_tax = calculated_total + tax
                calculated_tax = tax
        else:  # amount_first
            if tax > 0:
                calculated_total_with_tax = calculated_total + tax
                calculated_tax = tax
            else:
                calculated_tax = calculated_total * (tax_percent / 100.0)
                calculated_total_with_tax = calculated_total + calculated_tax

        return calculated_total_with_tax, calculated_tax

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
        config_param = request.env["ir.config_parameter"].sudo()

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
        config_param = request.env["ir.config_parameter"].sudo()
        company_id = pos_session.config_id.company_id.id

        # Get product validation settings
        require_sale_ok = config_param.get_param(
            "karage_pos.product_require_sale_ok", "True"
        ).lower() == "true"
        require_available_in_pos = config_param.get_param(
            "karage_pos.product_require_available_in_pos", "True"
        ).lower() == "true"

        # Priority 1: OdooItemID (direct product_id)
        if odoo_item_id and odoo_item_id > 0:
            product = product_env.browse(odoo_item_id)
            if product.exists():
                _logger.debug(f"Product found by OdooItemID: {odoo_item_id}")
                return product, "OdooItemID"
            else:
                _logger.warning(f"OdooItemID {odoo_item_id} does not exist")

        # Priority 2: ItemID (legacy support)
        if item_id and item_id > 0:
            product = product_env.browse(item_id)
            if product.exists():
                _logger.info(f"Product found by ItemID (legacy): {item_id}")
                return product, "ItemID"

        # Build search domain based on config
        search_domain = [("name", "=", item_name)]
        if require_sale_ok:
            search_domain.append(("sale_ok", "=", True))
        if require_available_in_pos:
            search_domain.append(("available_in_pos", "=", True))
        search_domain.extend(["|", ("company_id", "=", False), ("company_id", "=", company_id)])

        # Priority 3: ItemName exact match
        if item_name:
            product = product_env.search(search_domain, limit=1)

            if product:
                _logger.warning(
                    f"Product found by exact ItemName match: '{item_name}'. "
                    f"Consider using OdooItemID for better performance."
                )
                return product, "ItemName (exact)"

            # Priority 4: ItemName fuzzy match
            fuzzy_domain = [("name", "ilike", item_name)]
            if require_sale_ok:
                fuzzy_domain.append(("sale_ok", "=", True))
            if require_available_in_pos:
                fuzzy_domain.append(("available_in_pos", "=", True))
            fuzzy_domain.extend(["|", ("company_id", "=", False), ("company_id", "=", company_id)])

            product = product_env.search(fuzzy_domain, limit=1)

            if product:
                _logger.warning(
                    f"Product found by fuzzy ItemName match: '{item_name}' -> '{product.name}'. "
                    f"Consider using OdooItemID for accuracy."
                )
                return product, "ItemName (fuzzy)"

        return None, None

    def _validate_product_for_pos(self, product, pos_session):
        """
        Validate product is suitable for POS order

        Checks (based on configuration):
        - Product exists and is active
        - Product.sale_ok = True (if configured)
        - Product.available_in_pos = True (if configured)
        - Product company matches session company (if configured)

        :param product: Product to validate
        :param pos_session: POS session for company context
        :return: None if valid, error dict if invalid
        """
        if not product:
            return {
                "status": 404,
                "message": "Product not found"
            }

        # Get validation settings from config
        config_param = request.env["ir.config_parameter"].sudo()
        require_sale_ok = config_param.get_param(
            "karage_pos.product_require_sale_ok", "True"
        ).lower() == "true"
        require_available_in_pos = config_param.get_param(
            "karage_pos.product_require_available_in_pos", "True"
        ).lower() == "true"
        enforce_company_match = config_param.get_param(
            "karage_pos.enforce_product_company_match", "True"
        ).lower() == "true"

        if not product.active:
            return {
                "status": 400,
                "message": f"Product '{product.name}' (ID: {product.id}) is not active"
            }

        if require_sale_ok and not product.sale_ok:
            return {
                "status": 400,
                "message": f"Product '{product.name}' (ID: {product.id}) is not available for sale"
            }

        if require_available_in_pos and not product.available_in_pos:
            return {
                "status": 400,
                "message": f"Product '{product.name}' (ID: {product.id}) is not available in POS"
            }

        # Check company match
        if enforce_company_match:
            company_id = pos_session.config_id.company_id.id
            if product.company_id and product.company_id.id != company_id:
                return {
                    "status": 400,
                    "message": f"Product '{product.name}' (ID: {product.id}) belongs to a different company"
                }

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
            product, lookup_method = self._find_product_by_id(
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

    def _prepare_payment_lines(self, checkout_details, pos_session, expected_amount, rounding):
        """Prepare payment lines from checkout details"""
        payment_lines = []
        total_paid = 0.0

        # Get configuration
        config_param = request.env["ir.config_parameter"].sudo()
        fallback_payment_mode = int(config_param.get_param(
            "karage_pos.fallback_payment_mode", "1"
        ))

        # Get fallback payment method from config
        fallback_payment_method_id = config_param.get_param(
            "karage_pos.fallback_payment_method_id", "0"
        )
        try:
            fallback_payment_method_id = int(fallback_payment_method_id)
        except (ValueError, TypeError):
            fallback_payment_method_id = 0

        # Get payment mapping model
        payment_mapping_env = request.env["karage.pos.payment.mapping"].sudo()

        for checkout in checkout_details:
            payment_mode = checkout.get("PaymentMode", fallback_payment_mode)
            amount = float(str(checkout.get("AmountPaid", 0)).replace(",", ""))
            card_type = checkout.get("CardType", "Cash")

            if amount <= 0:
                continue

            # Find payment method using database mapping
            payment_method = None

            # Look up in payment mapping table
            mapping = payment_mapping_env.search([
                ("external_code", "=", payment_mode),
                ("active", "=", True)
            ], limit=1)

            if mapping and mapping.payment_method_id:
                # Check if the mapped payment method is available in this POS session
                if mapping.payment_method_id in pos_session.payment_method_ids:
                    payment_method = mapping.payment_method_id
                else:
                    _logger.warning(
                        f"Payment method '{mapping.payment_method_id.name}' from mapping "
                        f"is not available in POS session. Trying fallbacks."
                    )

            # Fallback: Try to find by CardType in journal name
            if not payment_method and card_type:
                payment_method = pos_session.payment_method_ids.filtered(
                    lambda p: p.journal_id and card_type.lower() in p.journal_id.name.lower()
                )[:1]

            # Fallback: Use fallback payment method from config
            if not payment_method and fallback_payment_method_id:
                default_pm = request.env["pos.payment.method"].sudo().browse(fallback_payment_method_id)
                if default_pm.exists() and default_pm in pos_session.payment_method_ids:
                    payment_method = default_pm

            # Fallback: Use cash payment method for payment mode 1
            if not payment_method and payment_mode == 1:
                payment_method = pos_session.payment_method_ids.filtered(lambda p: p.is_cash_count)[:1]

            if not payment_method:
                return None, {
                    "status": 400,
                    "message": (
                        f'No payment method found for PaymentMode={payment_mode}, CardType={card_type}. '
                        f'Please configure payment mappings in Settings > Karage POS.'
                    )
                }

            if not payment_method.journal_id:
                return None, {
                    "status": 400,
                    "message": f"Journal not found for payment method: {payment_method.name}"
                }

            total_paid += amount
            payment_lines.append((0, 0, {
                "payment_method_id": payment_method.id,
                "amount": amount,
                "payment_date": fields.Datetime.now(),
            }))

        if not payment_lines:
            return None, {"status": 400, "message": "No valid payment lines created"}

        if abs(total_paid - expected_amount) > rounding:
            return None, {
                "status": 400,
                "message": f"Payment inconsistency: Sum of CheckoutDetails ({total_paid}) does not match AmountPaid ({expected_amount})"
            }

        return payment_lines, None
