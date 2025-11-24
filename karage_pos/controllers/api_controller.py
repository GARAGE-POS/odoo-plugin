# -*- coding: utf-8 -*-

import json
import logging
import time

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class APIController(http.Controller):
    """REST API Controller for webhook endpoint"""

    def _update_idempotency_on_error(
        self, idempotency_record, error_message, webhook_log=None, start_time=None
    ):
        """Helper method to update idempotency record and webhook log on error"""
        if idempotency_record:
            try:
                idempotency_record.mark_failed(error_message=error_message)
            except Exception as e:
                _logger.warning(f"Error updating idempotency record on error: {str(e)}")

        if webhook_log and start_time is not None:
            try:
                webhook_log.update_log_result(
                    status_code=500,
                    response_message=error_message,
                    success=False,
                    idempotency_record_id=idempotency_record,
                    processing_time=time.time() - start_time,
                )
            except Exception as e:
                _logger.warning(f"Error updating webhook log on error: {str(e)}")

    def _update_webhook_log_validation_error(
        self, webhook_log, status_code, error_message, start_time
    ):
        """Helper method to update webhook log for validation errors"""
        if webhook_log and start_time is not None:
            try:
                webhook_log.update_log_result(
                    status_code=status_code,
                    response_message=error_message,
                    success=False,
                    processing_time=time.time() - start_time,
                )
            except Exception as e:
                _logger.warning(f"Error updating webhook log: {str(e)}")

    def _authenticate(self, api_key=None):
        """Authenticate API request using API key"""
        if not api_key:
            return None

        # Check if API key is configured and valid
        config = (
            request.env["karage.pos.config"]
            .sudo()
            .search([("api_key", "=", api_key)], limit=1)
        )
        if not config or not config.active:
            return None

        # Update usage statistics
        config.update_usage()

        return config

    def _json_response(self, data, status=200, error=None):
        """Return JSON response"""
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

    @http.route(
        "/api/v1/webhook/pos-order",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    def webhook_pos_order(self, **kwargs):  # noqa: C901
        """
        Webhook endpoint to create POS order from external system

        Expected JSON format:
        {
            "OrderID": 639,
            "AmountDiscount": 0.0,
            "AmountPaid": "92.0",
            "AmountTotal": 80.0,
            "BalanceAmount": 0.0,
            "GrandTotal": 92.0,
            "Tax": 12.0,
            "TaxPercent": 15.0,
            "OrderStatus": 103,
            "PaymentMode": 1,
            "CheckoutDetails": [...],
            "OrderItems": [...]
        }
        """
        # Only POST requests are allowed
        if request.httprequest.method != "POST":
            return self._json_response(
                None,
                status=405,
                error="Method not allowed. Only POST requests are accepted.",
            )

        # Initialize variables for exception handling
        idempotency_key = None
        idempotency_record = None
        webhook_log = None
        start_time = time.time()

        try:
            # Get JSON data from request body
            if request.httprequest.data:
                try:
                    data = json.loads(request.httprequest.data.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as e:
                    # Log the invalid request
                    try:
                        webhook_log = (
                            request.env["karage.pos.webhook.log"]
                            .sudo()
                            .create_log(
                                webhook_body=request.httprequest.data.decode(
                                    "utf-8", errors="ignore"
                                ),
                                request_info={
                                    "ip_address": request.httprequest.remote_addr,
                                    "user_agent": request.httprequest.headers.get(
                                        "User-Agent"
                                    ),
                                    "http_method": request.httprequest.method,
                                },
                            )
                        )
                        webhook_log.update_log_result(
                            status_code=400,
                            response_message=f"Invalid JSON format: {str(e)}",
                            success=False,
                            processing_time=time.time() - start_time,
                        )
                    except Exception as log_error:
                        _logger.warning(
                            f"Failed to create webhook log: {str(log_error)}"
                        )

                    return self._json_response(
                        None, status=400, error=f"Invalid JSON format: {str(e)}"
                    )
            else:
                # Log empty request
                try:
                    webhook_log = (
                        request.env["karage.pos.webhook.log"]
                        .sudo()
                        .create_log(
                            webhook_body="{}",
                            request_info={
                                "ip_address": request.httprequest.remote_addr,
                                "user_agent": request.httprequest.headers.get(
                                    "User-Agent"
                                ),
                                "http_method": request.httprequest.method,
                            },
                        )
                    )
                    webhook_log.update_log_result(
                        status_code=400,
                        response_message="Request body is required",
                        success=False,
                        processing_time=time.time() - start_time,
                    )
                except Exception as log_error:
                    _logger.warning(f"Failed to create webhook log: {str(log_error)}")

                return self._json_response(
                    None, status=400, error="Request body is required"
                )

            # Extract idempotency key early for logging
            idempotency_key = (
                request.httprequest.headers.get("Idempotency-Key")
                or request.httprequest.headers.get("X-Idempotency-Key")
                or data.get("idempotency_key")
                or data.get("IdempotencyKey")
            )

            # Create webhook log entry
            try:
                webhook_log = (
                    request.env["karage.pos.webhook.log"]
                    .sudo()
                    .create_log(
                        webhook_body=data,
                        idempotency_key=idempotency_key,
                        request_info={
                            "ip_address": request.httprequest.remote_addr,
                            "user_agent": request.httprequest.headers.get("User-Agent"),
                            "http_method": request.httprequest.method,
                        },
                    )
                )
            except Exception as log_error:
                _logger.warning(f"Failed to create webhook log: {str(log_error)}")

            # Authenticate - API key can be in header or body
            api_key = (
                request.httprequest.headers.get("X-API-KEY")
                or request.httprequest.headers.get("X-API-Key")
                or data.get("api_key")
            )

            if not api_key:
                return self._json_response(
                    None, status=401, error="Invalid or missing API key"
                )

            # Get configured API key from settings
            config = request.env["karage.pos.config"].sudo().get_config()
            if not config or not config.api_key:
                _logger.error("Karage POS API key not configured in settings")
                return self._json_response(
                    None, status=500, error="API key not configured in system settings"
                )

            # Validate API key
            if api_key != config.api_key:
                _logger.warning(f"Invalid API key attempt: {api_key[:10]}...")
                if webhook_log:
                    webhook_log.update_log_result(
                        status_code=401,
                        response_message="Invalid or missing API key",
                        success=False,
                        processing_time=time.time() - start_time,
                    )
                return self._json_response(
                    None, status=401, error="Invalid or missing API key"
                )

            # Check idempotency - Idempotency-Key was already extracted above
            # If idempotency key is provided, check if request was already processed
            if idempotency_key:
                idempotency_record = (
                    request.env["karage.pos.webhook.idempotency"]
                    .sudo()
                    .check_idempotency(idempotency_key)
                )

                if idempotency_record:
                    if idempotency_record.status == "completed":
                        # Request already processed successfully, return previous response
                        _logger.info(
                            f"Duplicate request detected with idempotency key: {idempotency_key[:20]}... "
                            f"Returning previous response for OrderID: {idempotency_record.order_id}"
                        )
                        # Update webhook log
                        if webhook_log:
                            webhook_log.update_log_result(
                                status_code=200,
                                response_message="Duplicate request - returning previous response",
                                success=True,
                                pos_order_id=idempotency_record.pos_order_id,
                                idempotency_record_id=idempotency_record,
                                processing_time=time.time() - start_time,
                            )

                        if idempotency_record.response_data:
                            try:
                                previous_response = json.loads(
                                    idempotency_record.response_data
                                )
                                return self._json_response(
                                    previous_response, status=200
                                )
                            except (ValueError, TypeError):
                                pass
                        # If we can't parse the response, return basic info
                        return self._json_response(
                            {
                                "id": (
                                    idempotency_record.pos_order_id.id
                                    if idempotency_record.pos_order_id
                                    else None
                                ),
                                "name": (
                                    idempotency_record.pos_order_id.name
                                    if idempotency_record.pos_order_id
                                    else None
                                ),
                                "message": "Request already processed",
                                "idempotency_key": idempotency_key,
                                "processed_at": (
                                    str(idempotency_record.processed_at)
                                    if idempotency_record.processed_at
                                    else None
                                ),
                            },
                            status=200,
                        )
                    elif idempotency_record.status == "processing":
                        # Request is currently being processed
                        _logger.warning(
                            f"Request with idempotency key {idempotency_key[:20]}... is already being processed"
                        )
                        if webhook_log:
                            webhook_log.update_log_result(
                                status_code=409,
                                response_message="Request is already being processed. Please wait.",
                                success=False,
                                idempotency_record_id=idempotency_record,
                                processing_time=time.time() - start_time,
                            )
                        return self._json_response(
                            None,
                            status=409,
                            error="Request is already being processed. Please wait.",
                        )
                    elif idempotency_record.status == "failed":
                        # Previous attempt failed, allow retry but log it
                        _logger.info(
                            f"Retrying previously failed request with idempotency key: {idempotency_key[:20]}..."
                        )
                        idempotency_record.mark_processing()

            # Create idempotency record if key provided and not found
            if idempotency_key and not idempotency_record:
                try:
                    idempotency_record = (
                        request.env["karage.pos.webhook.idempotency"]
                        .sudo()
                        .create_idempotency_record(
                            idempotency_key,
                            order_id=str(data.get("OrderID", "")),
                            status="processing",
                        )
                    )
                    _logger.info(
                        f"Created idempotency record for key: {idempotency_key[:20]}..."
                    )
                except Exception as e:
                    _logger.error(f"Error creating idempotency record: {str(e)}")
                    # Continue processing even if idempotency record creation fails

            # Validate required fields
            required_fields = [
                "OrderID",
                "OrderItems",
                "CheckoutDetails",
                "AmountTotal",
                "AmountPaid",
            ]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                error_msg = f'Missing required fields: {", ".join(missing_fields)}'
                self._update_webhook_log_validation_error(
                    webhook_log, 400, error_msg, start_time
                )
                return self._json_response(
                    None,
                    status=400,
                    error=error_msg,
                )

            # Get or create default POS session (you may want to make this configurable)
            pos_session = (
                request.env["pos.session"]
                .sudo()
                .search([("state", "=", "opened")], limit=1, order="id desc")
            )

            if not pos_session:
                return self._json_response(
                    None,
                    status=400,
                    error="No open POS session found. Please open a POS session first.",
                )

            # Validate that payment methods have journals configured
            payment_methods = pos_session.payment_method_ids
            if not payment_methods:
                return self._json_response(
                    None,
                    status=400,
                    error="No payment methods configured for this POS session. Please configure payment methods first.",
                )

            # Check if all payment methods have journals
            missing_journals = []
            for payment_method in payment_methods:
                if not payment_method.journal_id:
                    missing_journals.append(payment_method.name)

            if missing_journals:
                return self._response(
                    None,
                    status=400,
                    error=(
                        f'Journal not found for payment method(s): {", ".join(missing_journals)}. '
                        "Please configure journals for all payment methods."
                    ),
                )

            # Validate data consistency
            amount_paid_str = str(data.get("AmountPaid", 0)).replace(",", "")
            amount_paid = float(amount_paid_str)
            grand_total = float(data.get("GrandTotal", 0))
            tax = float(data.get("Tax", 0))
            tax_percent = float(data.get("TaxPercent", 0))
            balance_amount = float(data.get("BalanceAmount", 0))

            # Calculate expected totals from order items
            calculated_total = 0.0
            calculated_tax = 0.0

            for item in data.get("OrderItems", []):
                item_price = float(item.get("Price", 0))
                item_qty = float(item.get("Quantity", 1))
                item_discount = float(item.get("DiscountAmount", 0))
                calculated_total += (item_price * item_qty) - item_discount

            # Add tax to total if not included
            if tax_percent > 0:
                calculated_tax = calculated_total * (tax_percent / 100.0)
                calculated_total_with_tax = calculated_total + calculated_tax
            else:
                calculated_total_with_tax = calculated_total + tax

            # Validate totals (allow small rounding differences)
            currency = pos_session.config_id.currency_id
            rounding = currency.rounding

            if abs(calculated_total_with_tax - grand_total) > rounding * 10:
                return self._response(
                    None,
                    status=400,
                    error=(
                        f"Data inconsistency: Calculated total ({calculated_total_with_tax}) "
                        f"does not match GrandTotal ({grand_total})"
                    ),
                )

            if (
                abs(amount_paid - grand_total) > rounding * 10
                and balance_amount > rounding
            ):
                return self._json_response(
                    None,
                    status=400,
                    error=(
                        f"Data inconsistency: AmountPaid ({amount_paid}) + BalanceAmount ({balance_amount}) "
                        f"should equal GrandTotal ({grand_total})"
                    ),
                )

            # Prepare order lines
            order_lines = []
            product_env = request.env["product.product"].sudo()

            for order_item in data.get("OrderItems", []):
                item_name = order_item.get("ItemName", "").strip()
                item_id = order_item.get("ItemID", 0)
                price = float(order_item.get("Price", 0))
                quantity = float(order_item.get("Quantity", 1))
                discount_amount = float(order_item.get("DiscountAmount", 0))

                # Find product by ItemID (if it's a valid Odoo product ID) or by name
                product = None
                if item_id and item_id > 0:
                    product = product_env.browse(item_id)
                    if not product.exists():
                        product = None

                if not product and item_name:
                    # Search by name
                    product = product_env.search(
                        [
                            ("name", "=", item_name),
                            ("sale_ok", "=", True),
                            ("available_in_pos", "=", True),
                        ],
                        limit=1,
                    )

                    if not product:
                        # Try case-insensitive search
                        product = product_env.search(
                            [
                                ("name", "ilike", item_name),
                                ("sale_ok", "=", True),
                                ("available_in_pos", "=", True),
                            ],
                            limit=1,
                        )

                if not product:
                    return self._json_response(
                        None,
                        status=404,
                        error=f'Product not found: ItemName="{item_name}", ItemID={item_id}',
                    )

                # Calculate discount percentage
                discount_percent = 0.0
                if price > 0 and discount_amount > 0:
                    discount_percent = (discount_amount / (price * quantity)) * 100.0

                # Get tax information
                taxes = product.taxes_id.filtered(
                    lambda t: t.company_id.id == pos_session.config_id.company_id.id
                )

                # Apply fiscal position if exists
                fiscal_position = pos_session.config_id.default_fiscal_position_id
                if fiscal_position:
                    taxes = fiscal_position.map_tax(taxes)

                # Calculate tax amount
                partner = False  # No partner by default
                tax_results = taxes.compute_all(
                    price * (1 - discount_percent / 100.0),
                    pos_session.config_id.currency_id,
                    quantity,
                    product=product,
                    partner=partner,
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

                # Handle OrderDetailPackages - these are components that need to be consumed
                order_detail_packages = order_item.get("OrderDetailPackages", [])
                if order_detail_packages:
                    # For each package item, create a consumption line or stock move
                    # This depends on your business logic - you might want to create
                    # separate order lines for components or handle them as BOM consumption
                    for package_item in order_detail_packages:
                        package_item_name = package_item.get("ItemName", "").strip()
                        package_item_id = package_item.get("ItemID", 0)
                        package_qty = float(package_item.get("Quantity", 0))

                        if package_qty > 0:
                            # Find the component product
                            component_product = None
                            if package_item_id and package_item_id > 0:
                                component_product = product_env.browse(package_item_id)
                                if not component_product.exists():
                                    component_product = None

                            if not component_product and package_item_name:
                                component_product = product_env.search(
                                    [
                                        ("name", "=", package_item_name),
                                        ("type", "in", ["product", "consu"]),
                                    ],
                                    limit=1,
                                )

                            # If component found, you might want to create a consumption line
                            # For now, we'll log it - you can extend this based on your needs
                            if component_product:
                                _logger.info(
                                    f"Package component: {component_product.name} x {package_qty} "
                                    f"for order item {item_name}"
                                )

            if not order_lines:
                return self._json_response(
                    None, status=400, error="No valid order lines created"
                )

            # Process payments from CheckoutDetails
            payment_lines = []
            total_paid = 0.0

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

            for checkout in data.get("CheckoutDetails", []):
                payment_mode = checkout.get("PaymentMode", 1)
                amount = float(str(checkout.get("AmountPaid", 0)).replace(",", ""))
                card_type = checkout.get("CardType", "Cash")

                if amount <= 0:
                    continue

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
                        return self._json_response(
                            None,
                            status=400,
                            error=(
                                f'Payment method with journal name containing "{journal_search_name}" '
                                f"not found for PaymentMode={payment_mode}. Please configure a payment method "
                                f'with a journal containing "{journal_search_name}" in its name.'
                            ),
                        )
                    else:
                        return self._json_response(
                            None,
                            status=400,
                            error=(
                                f"No payment method found for PaymentMode={payment_mode}, CardType={card_type}. "
                                "PaymentMode must be 1 (Cash), 2 (Card), 3 (Credit), 5 (Tabby), 6 (Tamara), "
                                "7 (StcPay), or 8 (Bank Transfer)."
                            ),
                        )

                # Validate that payment method has a journal configured
                if not payment_method.journal_id:
                    return self._json_response(
                        None,
                        status=400,
                        error=(
                            f"Journal not found for payment method: {payment_method.name}. "
                            "Please configure a journal for this payment method."
                        ),
                    )

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
                return self._json_response(
                    None, status=400, error="No valid payment lines created"
                )

            # Validate payment amount matches
            if abs(total_paid - amount_paid) > rounding:
                return self._json_response(
                    None,
                    status=400,
                    error=(
                        f"Payment inconsistency: Sum of CheckoutDetails ({total_paid}) "
                        f"does not match AmountPaid ({amount_paid})"
                    ),
                )

            # Calculate order totals from lines
            calculated_total = sum(
                line[2]["price_subtotal_incl"] for line in order_lines
            )
            calculated_tax = sum(
                line[2]["price_subtotal_incl"] - line[2]["price_subtotal"]
                for line in order_lines
            )

            # Prepare order values
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
                "partner_id": False,  # No customer by default
                "to_invoice": False,
                "note": f'External Order ID: {data.get("OrderID")}',
                "lines": order_lines,
                "payment_ids": payment_lines,
                "amount_total": calculated_total,
                "amount_tax": calculated_tax,
                "amount_paid": total_paid,
                "amount_return": max(0.0, total_paid - calculated_total),
            }

            # Create the POS order
            pos_order = request.env["pos.order"].sudo().create(order_vals)

            # Confirm the order (mark as paid)
            try:
                pos_order.action_pos_order_paid()
            except Exception as e:
                _logger.error(f"Error confirming POS order: {str(e)}", exc_info=True)
                error_msg = f"Failed to confirm order: {str(e)}"
                self._update_idempotency_on_error(
                    idempotency_record, error_msg, webhook_log, start_time
                )
                return self._json_response(None, status=500, error=error_msg)

            # Create picking for inventory consumption (if needed)
            try:
                pos_order._create_order_picking()
            except Exception as e:
                _logger.warning(
                    f"Could not create picking for order {pos_order.name}: {str(e)}"
                )

            # Prepare success response
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

            # Update idempotency record if exists
            if idempotency_record:
                try:
                    idempotency_record.mark_completed(
                        pos_order_id=pos_order, response_data=json.dumps(response_data)
                    )
                except Exception as e:
                    _logger.warning(f"Error updating idempotency record: {str(e)}")

            # Update webhook log with success
            if webhook_log:
                try:
                    webhook_log.update_log_result(
                        status_code=200,
                        response_message=json.dumps(response_data),
                        success=True,
                        pos_order_id=pos_order,
                        idempotency_record_id=idempotency_record,
                        processing_time=time.time() - start_time,
                    )
                except Exception as e:
                    _logger.warning(f"Error updating webhook log: {str(e)}")

            # Return success response
            return self._json_response(response_data)

        except Exception as e:
            _logger.error(f"Error in webhook_pos_order: {str(e)}", exc_info=True)
            error_msg = f"Internal server error: {str(e)}"
            self._update_idempotency_on_error(
                idempotency_record, error_msg, webhook_log, start_time
            )
            return self._json_response(None, status=500, error=error_msg)
