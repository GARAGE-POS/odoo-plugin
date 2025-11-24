# -*- coding: utf-8 -*-

import json
import logging

from odoo import fields, http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class APIController(http.Controller):
    """REST API Controller for webhook endpoint"""

    def _authenticate(self, api_key=None):
        """Authenticate API request using API key"""
        if not api_key:
            return None

        # Check if API key is configured and valid
        config = (
            request.env["api.config"]
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
        methods=["GET", "POST", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    def webhook_pos_order(self, **kwargs):
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
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == "OPTIONS":
            return request.make_response(
                "",
                headers=[
                    ("Access-Control-Allow-Origin", "*"),
                    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                    ("Access-Control-Allow-Headers", "Content-Type"),
                    ("Access-Control-Max-Age", "3600"),
                ],
                status=200,
            )

        # Handle GET request - return endpoint info
        if request.httprequest.method == "GET":
            return self._json_response(
                {
                    "endpoint": "/api/v1/webhook/pos-order",
                    "methods": ["GET", "POST", "OPTIONS"],
                    "description": "Webhook endpoint to create and confirm POS orders from external systems",
                    "usage": "Send POST request with JSON body containing order data",
                    "status": "active",
                }
            )

        try:
            # Get JSON data from request body
            if request.httprequest.data:
                try:
                    data = json.loads(request.httprequest.data.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as e:
                    return self._json_response(
                        None, status=400, error=f"Invalid JSON format: {str(e)}"
                    )
            else:
                return self._json_response(
                    None, status=400, error="Request body is required"
                )

            # Authenticate - API key can be in header or body
            api_key = request.httprequest.headers.get("X-API-Key") or data.get(
                "api_key"
            )

            if not api_key:
                return self._json_response(
                    None, status=401, error="Invalid or missing API key"
                )
            elif api_key != "my_secure_api_key":
                return self._json_response(
                    None, status=401, error="Invalid or missing API key"
                )

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
                return self._json_response(
                    None,
                    status=400,
                    error=f'Missing required fields: {", ".join(missing_fields)}',
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
                return self._json_response(
                    None,
                    status=400,
                    error=f'Journal not found for payment method(s): {", ".join(missing_journals)}. Please configure journals for all payment methods.',
                )

            # Validate data consistency
            amount_total = float(data.get("AmountTotal", 0))
            amount_paid = float(str(data.get("AmountPaid", 0)).replace(",", ""))
            grand_total = float(data.get("GrandTotal", 0))
            tax = float(data.get("Tax", 0))
            tax_percent = float(data.get("TaxPercent", 0))
            amount_discount = float(data.get("AmountDiscount", 0))
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
                return self._json_response(
                    None,
                    status=400,
                    error=f"Data inconsistency: Calculated total ({calculated_total_with_tax}) does not match GrandTotal ({grand_total})",
                )

            if (
                abs(amount_paid - grand_total) > rounding * 10
                and balance_amount > rounding
            ):
                return self._json_response(
                    None,
                    status=400,
                    error=f"Data inconsistency: AmountPaid ({amount_paid}) + BalanceAmount ({balance_amount}) should equal GrandTotal ({grand_total})",
                )

            # Prepare order lines
            order_lines = []
            product_env = request.env["product.product"].sudo()

            for order_item in data.get("OrderItems", []):
                item_name = order_item.get("ItemName", "").strip()
                item_id = order_item.get("ItemID", 0)
                package_id = order_item.get("PackageID", 0)
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
                        package_price = float(package_item.get("Price", 0))

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
                reference_id = checkout.get("ReferenceID", "")

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
                            error=f'Payment method with journal name containing "{journal_search_name}" not found for PaymentMode={payment_mode}. Please configure a payment method with a journal containing "{journal_search_name}" in its name.',
                        )
                    else:
                        return self._json_response(
                            None,
                            status=400,
                            error=f"No payment method found for PaymentMode={payment_mode}, CardType={card_type}. PaymentMode must be 1 (Cash), 2 (Card), 3 (Credit), 5 (Tabby), 6 (Tamara), 7 (StcPay), or 8 (Bank Transfer).",
                        )

                # Validate that payment method has a journal configured
                if not payment_method.journal_id:
                    return self._json_response(
                        None,
                        status=400,
                        error=f"Journal not found for payment method: {payment_method.name}. Please configure a journal for this payment method.",
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
                    error=f"Payment inconsistency: Sum of CheckoutDetails ({total_paid}) does not match AmountPaid ({amount_paid})",
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
                return self._json_response(
                    None, status=500, error=f"Failed to confirm order: {str(e)}"
                )

            # Create picking for inventory consumption (if needed)
            try:
                pos_order._create_order_picking()
            except Exception as e:
                _logger.warning(
                    f"Could not create picking for order {pos_order.name}: {str(e)}"
                )

            # Return success response
            return self._json_response(
                {
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
            )

        except Exception as e:
            _logger.error(f"Error in webhook_pos_order: {str(e)}", exc_info=True)
            return self._json_response(
                None, status=500, error=f"Internal server error: {str(e)}"
            )
