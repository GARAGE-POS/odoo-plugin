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
                idempotency_record_id=idempotency_record,
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

        try:
            user_id = (
                request.env["res.users.apikeys"]
                .with_user(1)
                ._check_credentials(scope="rpc", key=api_key)
            )
            request.update_env(user=user_id)
            _logger.info(f"API request authenticated for user ID: {user_id}")
            return True, None
        except Exception as e:
            _logger.warning(f"Invalid API key attempt: {str(e)}")
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

        if created:
            # New request - proceed with processing
            _logger.info(f"New request with idempotency key: {idempotency_key[:20]}...")
            return True, idempotency_record

        # Record already exists - check status
        if idempotency_record.status == "completed":
            # Return cached response
            _logger.info(
                f"Duplicate request detected: {idempotency_key[:20]}... "
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
                        f"Idempotency record stuck in processing state: {idempotency_key[:20]}... "
                        f"Allowing retry."
                    )
                    idempotency_record.write({"status": "processing"})
                    return True, idempotency_record

            # Still processing
            _logger.warning(f"Request already being processed: {idempotency_key[:20]}...")
            self._update_log(
                webhook_log, 409, "Request is already being processed. Please wait.",
                False, idempotency_record=idempotency_record, start_time=start_time
            )
            return False, self._json_response(
                None, status=409, error="Request is already being processed. Please wait."
            )

        elif idempotency_record.status == "failed":
            # Allow retry
            _logger.info(f"Retrying previously failed request: {idempotency_key[:20]}...")
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

    def _process_pos_order(self, data):
        """
        Process POS order from webhook data

        :param data: Validated webhook data
        :return: Tuple of (pos_order, error_dict or None)
        """
        try:
            # Get open POS session
            pos_session = (
                request.env["pos.session"]
                .sudo()
                .search([("state", "=", "opened")], limit=1, order="id desc")
            )

            if not pos_session:
                return None, {
                    "status": 400,
                    "message": "No open POS session found. Please open a POS session first."
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

            # Parse amounts
            amount_paid = float(str(data.get("AmountPaid", 0)).replace(",", ""))
            grand_total = float(data.get("GrandTotal", 0))
            tax = float(data.get("Tax", 0))
            tax_percent = float(data.get("TaxPercent", 0))
            balance_amount = float(data.get("BalanceAmount", 0))

            # Validate data consistency
            currency = pos_session.config_id.currency_id
            rounding = currency.rounding

            calculated_total, calculated_tax = self._calculate_totals(
                data.get("OrderItems", []), tax_percent, tax
            )

            if abs(calculated_total - grand_total) > rounding * 10:
                return None, {
                    "status": 400,
                    "message": f"Data inconsistency: Calculated total ({calculated_total}) does not match GrandTotal ({grand_total})"
                }

            if abs(amount_paid - grand_total) > rounding * 10 and balance_amount > rounding:
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
                "date_order": fields.Datetime.now(),
                "partner_id": False,
                "to_invoice": False,
                "general_note": f'External Order ID: {data.get("OrderID")}',
                "lines": order_lines,
                "payment_ids": payment_lines,
                "amount_total": final_total,
                "amount_tax": final_tax,
                "amount_paid": total_paid,
                "amount_return": max(0.0, total_paid - final_total),
            }

            pos_order = request.env["pos.order"].sudo().create(order_vals)

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

    def _calculate_totals(self, order_items, tax_percent, tax):
        """Calculate expected totals from order items"""
        calculated_total = 0.0
        for item in order_items:
            item_price = float(item.get("Price", 0))
            item_qty = float(item.get("Quantity", 1))
            item_discount = float(item.get("DiscountAmount", 0))
            calculated_total += (item_price * item_qty) - item_discount

        if tax_percent > 0:
            calculated_tax = calculated_total * (tax_percent / 100.0)
            calculated_total_with_tax = calculated_total + calculated_tax
        else:
            calculated_total_with_tax = calculated_total + tax

        return calculated_total_with_tax, calculated_tax if tax_percent > 0 else tax

    def _prepare_order_lines(self, order_items, pos_session):
        """Prepare order lines from order items"""
        order_lines = []
        product_env = request.env["product.product"].sudo()

        for order_item in order_items:
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
                product = product_env.search([
                    ("name", "=", item_name),
                    ("sale_ok", "=", True),
                    ("available_in_pos", "=", True),
                ], limit=1)

                if not product:
                    product = product_env.search([
                        ("name", "ilike", item_name),
                        ("sale_ok", "=", True),
                        ("available_in_pos", "=", True),
                    ], limit=1)

            if not product:
                return None, {
                    "status": 404,
                    "message": f'Product not found: ItemName="{item_name}", ItemID={item_id}'
                }

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

            # Calculate tax amount
            tax_results = taxes.compute_all(
                price * (1 - discount_percent / 100.0),
                pos_session.config_id.currency_id,
                quantity,
                product=product,
                partner=False,
            )

            order_lines.append((0, 0, {
                "product_id": product.id,
                "qty": quantity,
                "price_unit": price,
                "discount": discount_percent,
                "price_subtotal": tax_results["total_excluded"],
                "price_subtotal_incl": tax_results["total_included"],
                "tax_ids": [(6, 0, taxes.ids)],
            }))

        if not order_lines:
            return None, {"status": 400, "message": "No valid order lines created"}

        return order_lines, None

    def _prepare_payment_lines(self, checkout_details, pos_session, expected_amount, rounding):
        """Prepare payment lines from checkout details"""
        payment_lines = []
        total_paid = 0.0

        # Payment mode mapping
        payment_mode_mapping = {
            1: "Cash",
            2: "Card",
            3: "Credit",
            5: "Tabby",
            6: "Tamara",
            7: "StcPay",
            8: "Bank Transfer",
        }

        for checkout in checkout_details:
            payment_mode = checkout.get("PaymentMode", 1)
            amount = float(str(checkout.get("AmountPaid", 0)).replace(",", ""))
            card_type = checkout.get("CardType", "Cash")

            if amount <= 0:
                continue

            # Find payment method
            payment_method = None
            journal_search_name = payment_mode_mapping.get(payment_mode)

            if journal_search_name:
                payment_method = pos_session.payment_method_ids.filtered(
                    lambda p: p.journal_id and journal_search_name.lower() in p.journal_id.name.lower()
                )[:1]

            if not payment_method and card_type:
                payment_method = pos_session.payment_method_ids.filtered(
                    lambda p: p.journal_id and card_type.lower() in p.journal_id.name.lower()
                )[:1]

            if not payment_method and payment_mode == 1:
                payment_method = pos_session.payment_method_ids.filtered(lambda p: p.is_cash_count)[:1]

            if not payment_method:
                return None, {
                    "status": 400,
                    "message": f'No payment method found for PaymentMode={payment_mode}, CardType={card_type}'
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
