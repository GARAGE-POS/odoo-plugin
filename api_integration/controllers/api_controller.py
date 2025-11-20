# -*- coding: utf-8 -*-

import json
import logging
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class APIController(http.Controller):
    """REST API Controller for pushing Odoo data"""

    def _authenticate(self, api_key=None):
        """Authenticate API request using API key"""
        if not api_key:
            return None
        
        # Check if API key is configured and valid
        config = request.env['api.config'].sudo().search([('api_key', '=', api_key)], limit=1)
        if not config or not config.active:
            return None
        
        # Update usage statistics
        config.update_usage()
        
        return config

    def _json_response(self, data, status=200, error=None):
        """Return JSON response"""
        response_data = {
            'status': 'success' if status == 200 else 'error',
            'data': data if status == 200 else None,
            'error': error if error else None,
            'count': len(data) if isinstance(data, list) else (1 if data else 0),
        }
        return request.make_response(
            json.dumps(response_data, default=str),
            headers=[('Content-Type', 'application/json')],
            status=status
        )

    @http.route('/api/v1/uom', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_uom(self, api_key=None, limit=None, offset=0, **kwargs):
        """
        Get Unit of Measures
        
        Parameters:
        - api_key (required): API authentication key
        - limit: Maximum number of records to return (default: all)
        - offset: Number of records to skip (default: 0)
        
        Returns JSON with unit of measures data
        """
        try:
            # Authenticate
            config = self._authenticate(api_key)
            if not config:
                return self._json_response(
                    None,
                    status=401,
                    error='Invalid or missing API key'
                )
            
            # Get UoM records
            uom_env = request.env['uom.uom'].sudo()
            domain = []
            
            # Apply limit and offset
            limit = int(limit) if limit else None
            offset = int(offset) if offset else 0
            
            uoms = uom_env.search(domain, limit=limit, offset=offset, order='name')
            
            # Serialize data
            data = []
            for uom in uoms:
                data.append({
                    'id': uom.id,
                    'name': uom.name,
                    'category_id': {
                        'id': uom.category_id.id if uom.category_id else None,
                        'name': uom.category_id.name if uom.category_id else None,
                    },
                    'factor': uom.factor,
                    'factor_inv': uom.factor_inv,
                    'rounding': uom.rounding,
                    'uom_type': uom.uom_type,
                    'active': uom.active,
                })
            
            return self._json_response(data)
            
        except Exception as e:
            _logger.error(f"Error in get_uom: {str(e)}")
            return self._json_response(
                None,
                status=500,
                error=f'Internal server error: {str(e)}'
            )

    @http.route('/api/v1/products', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_products(self, api_key=None, limit=None, offset=0, active_only='true', **kwargs):
        """
        Get Products (Product Templates and Variants)
        
        Parameters:
        - api_key (required): API authentication key
        - limit: Maximum number of records to return (default: all)
        - offset: Number of records to skip (default: 0)
        - active_only: Return only active products (default: true)
        
        Returns JSON with products data including variants
        """
        try:
            # Authenticate
            config = self._authenticate(api_key)
            if not config:
                return self._json_response(
                    None,
                    status=401,
                    error='Invalid or missing API key'
                )
            
            # Get Product Templates
            product_env = request.env['product.template'].sudo()
            domain = []
            
            # Handle active_only parameter - can be string or boolean
            if active_only:
                if isinstance(active_only, bool):
                    active_filter = active_only
                elif isinstance(active_only, str):
                    active_filter = active_only.lower() not in ('false', '0', 'no', '')
                else:
                    active_filter = True
                
                if active_filter:
                    domain.append(('active', '=', True))
            
            # Apply limit and offset
            limit = int(limit) if limit else None
            offset = int(offset) if offset else 0
            
            products = product_env.search(domain, limit=limit, offset=offset, order='name')
            
            # Serialize data
            data = []
            for product in products:
                # Get product variants
                variants = []
                for variant in product.product_variant_ids:
                    variants.append({
                        'id': variant.id,
                        'default_code': variant.default_code or '',
                        'barcode': variant.barcode or '',
                        'weight': float(variant.weight) if variant.weight else 0.0,
                        'volume': float(variant.volume) if variant.volume else 0.0,
                    })
                
                # Get categories (categ_id is Many2one, so single category)
                categories = []
                if product.categ_id:
                    categories.append({
                        'id': product.categ_id.id,
                        'name': product.categ_id.complete_name or product.categ_id.name or '',
                    })
                
                # Get suppliers (vendors)
                suppliers = []
                for supplier in product.seller_ids:
                    if supplier.partner_id:  # Only add if partner exists
                        suppliers.append({
                            'id': supplier.partner_id.id,
                            'name': supplier.partner_id.name or '',
                            'price': float(supplier.price) if supplier.price else 0.0,
                            'currency_id': {
                                'id': supplier.currency_id.id if supplier.currency_id else None,
                                'name': supplier.currency_id.name if supplier.currency_id else None,
                            },
                            'min_qty': float(supplier.min_qty) if supplier.min_qty else 0.0,
                            'delay': int(supplier.delay) if supplier.delay else 0,
                        })
                
                product_data = {
                    'id': product.id,
                    'name': product.name or '',
                    'description': product.description or '',
                    'description_purchase': product.description_purchase or '',
                    'description_sale': product.description_sale or '',
                    'type': product.type or 'consu',  # 'consu', 'service', 'storable'
                    'categ_id': {
                        'id': product.categ_id.id if product.categ_id else None,
                        'name': product.categ_id.name if product.categ_id else None,
                    },
                    'categories': categories,
                    'list_price': float(product.list_price) if product.list_price else 0.0,
                    'standard_price': float(product.standard_price) if product.standard_price else 0.0,
                    'uom_id': {
                        'id': product.uom_id.id if product.uom_id else None,
                        'name': product.uom_id.name if product.uom_id else None,
                    },
                    'uom_po_id': {
                        'id': product.uom_po_id.id if product.uom_po_id else None,
                        'name': product.uom_po_id.name if product.uom_po_id else None,
                    },
                    'barcode': product.barcode or '',
                    'default_code': product.default_code or '',
                    'sale_ok': product.sale_ok or False,
                    'purchase_ok': product.purchase_ok or False,
                    'active': product.active or False,
                    'weight': float(product.weight) if product.weight else 0.0,
                    'volume': float(product.volume) if product.volume else 0.0,
                    'variants': variants,
                    'suppliers': suppliers,
                }
                
                # Add image if available
                if product.image_1920:
                    product_data['image_url'] = f'/web/image/product.template/{product.id}/image_1920'
                
                data.append(product_data)
            
            return self._json_response(data)
            
        except Exception as e:
            _logger.error(f"Error in get_products: {str(e)}")
            return self._json_response(
                None,
                status=500,
                error=f'Internal server error: {str(e)}'
            )

    @http.route('/api/v1/vendors', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def get_vendors(self, api_key=None, limit=None, offset=0, active_only='true', **kwargs):
        """
        Get Vendors (Supplier Partners)
        
        Parameters:
        - api_key (required): API authentication key
        - limit: Maximum number of records to return (default: all)
        - offset: Number of records to skip (default: 0)
        - active_only: Return only active vendors (default: true)
        
        Returns JSON with vendors data
        """
        try:
            # Authenticate
            config = self._authenticate(api_key)
            if not config:
                return self._json_response(
                    None,
                    status=401,
                    error='Invalid or missing API key'
                )
            
            # Get Vendor Partners (suppliers)
            partner_env = request.env['res.partner'].sudo()
            domain = [
                ('is_company', '=', True),
                ('supplier_rank', '>', 0),
            ]
            
            # Handle active_only parameter - can be string or boolean
            if active_only:
                if isinstance(active_only, bool):
                    active_filter = active_only
                elif isinstance(active_only, str):
                    active_filter = active_only.lower() not in ('false', '0', 'no', '')
                else:
                    active_filter = True
                
                if active_filter:
                    domain.append(('active', '=', True))
            
            # Apply limit and offset
            limit = int(limit) if limit else None
            offset = int(offset) if offset else 0
            
            vendors = partner_env.search(domain, limit=limit, offset=offset, order='name')
            
            # Serialize data
            data = []
            for vendor in vendors:
                # Get vendor's products from product.supplierinfo (seller_ids)
                # Search for supplierinfo records where this vendor is the partner
                supplierinfo_env = request.env['product.supplierinfo'].sudo()
                supplier_infos = supplierinfo_env.search([('partner_id', '=', vendor.id)])
                
                products = []
                for seller in supplier_infos:
                    # Get product from supplierinfo
                    product = seller.product_id or (seller.product_tmpl_id.product_variant_id if seller.product_tmpl_id else None)
                    if product:
                        products.append({
                            'id': product.id,
                            'name': product.name or '',
                            'product_code': seller.product_code or '',
                            'price': float(seller.price) if seller.price else 0.0,
                            'min_qty': float(seller.min_qty) if seller.min_qty else 0.0,
                            'delay': int(seller.delay) if seller.delay else 0,
                            'currency_id': {
                                'id': seller.currency_id.id if seller.currency_id else None,
                                'name': seller.currency_id.name if seller.currency_id else None,
                            },
                        })
                
                # Get fiscal position and tax information
                fiscal_position = vendor.property_account_position_id
                fiscal_position_data = None
                tax_mappings = []
                
                if fiscal_position:
                    fiscal_position_data = {
                        'id': fiscal_position.id,
                        'name': fiscal_position.name or '',
                        'active': fiscal_position.active,
                    }
                    
                    # Get tax mappings from fiscal position
                    for tax_mapping in fiscal_position.tax_ids:
                        tax_mapping_data = {
                            'tax_source': {
                                'id': tax_mapping.tax_src_id.id if tax_mapping.tax_src_id else None,
                                'name': tax_mapping.tax_src_id.name if tax_mapping.tax_src_id else '',
                                'amount': float(tax_mapping.tax_src_id.amount) if tax_mapping.tax_src_id and tax_mapping.tax_src_id.amount else 0.0,
                                'amount_type': tax_mapping.tax_src_id.amount_type if tax_mapping.tax_src_id else '',
                                'type_tax_use': tax_mapping.tax_src_id.type_tax_use if tax_mapping.tax_src_id else '',
                            },
                            'tax_destination': None,
                        }
                        
                        if tax_mapping.tax_dest_id:
                            tax_mapping_data['tax_destination'] = {
                                'id': tax_mapping.tax_dest_id.id,
                                'name': tax_mapping.tax_dest_id.name or '',
                                'amount': float(tax_mapping.tax_dest_id.amount) if tax_mapping.tax_dest_id.amount else 0.0,
                                'amount_type': tax_mapping.tax_dest_id.amount_type or '',
                                'type_tax_use': tax_mapping.tax_dest_id.type_tax_use or '',
                                'active': tax_mapping.tax_dest_active,
                            }
                        
                        tax_mappings.append(tax_mapping_data)
                
                vendor_data = {
                    'id': vendor.id,
                    'name': vendor.name,
                    'display_name': vendor.display_name,
                    'ref': vendor.ref or '',
                    'vat': vendor.vat or '',
                    'vat_number': vendor.vat or '',  # Explicit VAT number field
                    'company_registry': vendor.company_registry or '',  # Company registry number
                    'email': vendor.email or '',
                    'phone': vendor.phone or '',
                    'mobile': vendor.mobile or '',
                    'website': vendor.website or '',
                    'street': vendor.street or '',
                    'street2': vendor.street2 or '',
                    'city': vendor.city or '',
                    'state_id': {
                        'id': vendor.state_id.id if vendor.state_id else None,
                        'name': vendor.state_id.name if vendor.state_id else None,
                        'code': vendor.state_id.code if vendor.state_id else None,
                    },
                    'zip': vendor.zip or '',
                    'country_id': {
                        'id': vendor.country_id.id if vendor.country_id else None,
                        'name': vendor.country_id.name if vendor.country_id else None,
                        'code': vendor.country_id.code if vendor.country_id else None,
                    },
                    'supplier_rank': vendor.supplier_rank,
                    'active': vendor.active,
                    'fiscal_position': fiscal_position_data,
                    'tax_mappings': tax_mappings,
                    'products': products,
                }
                
                # Add image if available
                if vendor.image_1920:
                    vendor_data['image_url'] = f'/web/image/res.partner/{vendor.id}/image_1920'
                
                data.append(vendor_data)
            
            return self._json_response(data)
            
        except Exception as e:
            _logger.error(f"Error in get_vendors: {str(e)}")
            return self._json_response(
                None,
                status=500,
                error=f'Internal server error: {str(e)}'
            )

    @http.route('/api/v1/pos/orders', type='http', auth='none', methods=['GET', 'POST', 'OPTIONS'], csrf=False, cors='*')
    def create_pos_order(self, **kwargs):
        """
        Create POS Order from external API
        
        GET: Returns endpoint information
        POST: Creates a POS order in Odoo
        
        Expected JSON format (POST):
        {
            "api_key": "your-api-key",
            "session_id": 1,
            "partner_id": 1,  // optional
            "lines": [
                {
                    "product_id": 1,
                    "qty": 2.0,
                    "price_unit": 100.0,
                    "discount": 0.0
                }
            ],
            "payments": [
                {
                    "payment_method_id": 1,
                    "amount": 200.0
                }
            ],
            "date_order": "2024-01-01 10:00:00",  // optional, defaults to now
            "note": "Order note",  // optional
            "to_invoice": false  // optional
        }
        """
        # Handle OPTIONS request for CORS preflight
        if request.httprequest.method == 'OPTIONS':
            return request.make_response(
                '',
                headers=[
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type'),
                    ('Access-Control-Max-Age', '3600'),
                ],
                status=200
            )
        
        # Handle GET request - return endpoint info
        if request.httprequest.method == 'GET':
            return self._json_response({
                'endpoint': '/api/v1/pos/orders',
                'methods': ['GET', 'POST'],
                'description': 'Create POS Order from external API',
                'usage': 'Send POST request with JSON body containing order data'
            })
        
        # Handle POST request
        try:
            # Get JSON data from request body
            if request.httprequest.data:
                try:
                    data = json.loads(request.httprequest.data.decode('utf-8'))
                except (ValueError, UnicodeDecodeError) as e:
                    return self._json_response(
                        None,
                        status=400,
                        error=f'Invalid JSON format: {str(e)}'
                    )
            else:
                # Fallback to params if no body data
                data = request.params
            
            # Authenticate
            api_key = data.get('api_key') or kwargs.get('api_key')
            config = self._authenticate(api_key)
            if not config:
                return self._json_response(
                    None,
                    status=401,
                    error='Invalid or missing API key'
                )
            
            # Validate required fields
            if not data.get('session_id'):
                return self._json_response(
                    None,
                    status=400,
                    error='session_id is required'
                )
            
            if not data.get('lines') or not isinstance(data.get('lines'), list):
                return self._json_response(
                    None,
                    status=400,
                    error='lines array is required with at least one product'
                )
            
            if not data.get('payments') or not isinstance(data.get('payments'), list):
                return self._json_response(
                    None,
                    status=400,
                    error='payments array is required with at least one payment'
                )
            
            # Get POS session
            pos_session = request.env['pos.session'].sudo().browse(data['session_id'])
            if not pos_session.exists():
                return self._json_response(
                    None,
                    status=404,
                    error=f'POS session {data["session_id"]} not found'
                )
            
            if pos_session.state not in ['opened', 'opening_control']:
                return self._json_response(
                    None,
                    status=400,
                    error=f'POS session {pos_session.name} is not open (state: {pos_session.state})'
                )
            
            # Prepare order data
            order_vals = {
                'session_id': pos_session.id,
                'config_id': pos_session.config_id.id,
                'company_id': pos_session.config_id.company_id.id,
                'pricelist_id': pos_session.config_id.pricelist_id.id,
                'fiscal_position_id': pos_session.config_id.default_fiscal_position_id.id if pos_session.config_id.default_fiscal_position_id else False,
                'user_id': pos_session.user_id.id,
                'date_order': data.get('date_order') or fields.Datetime.now(),
                'partner_id': data.get('partner_id') or False,
                'to_invoice': data.get('to_invoice', False),
                'note': data.get('note', ''),
            }
            
            # Process order lines
            order_lines = []
            for line_data in data['lines']:
                if not line_data.get('product_id'):
                    continue
                
                product = request.env['product.product'].sudo().browse(line_data['product_id'])
                if not product.exists():
                    return self._json_response(
                        None,
                        status=404,
                        error=f'Product {line_data["product_id"]} not found'
                    )
                
                qty = float(line_data.get('qty', 1.0))
                price_unit = float(line_data.get('price_unit', product.list_price))
                discount = float(line_data.get('discount', 0.0))
                
                # Get tax information
                taxes = product.taxes_id.filtered(lambda t: t.company_id.id == pos_session.config_id.company_id.id)
                if order_vals.get('fiscal_position_id'):
                    fiscal_position = request.env['account.fiscal.position'].sudo().browse(order_vals['fiscal_position_id'])
                    taxes = fiscal_position.map_tax(taxes)
                
                # Calculate tax amount using proper tax computation (with discount)
                partner = request.env['res.partner'].browse(order_vals.get('partner_id')) if order_vals.get('partner_id') else False
                tax_results = taxes.compute_all(
                    price_unit * (1 - discount / 100.0), 
                    pos_session.config_id.currency_id, 
                    qty, 
                    product=product, 
                    partner=partner
                )
                price_subtotal = tax_results['total_excluded']
                price_subtotal_incl = tax_results['total_included']
                tax_amount = price_subtotal_incl - price_subtotal
                
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'qty': qty,
                    'price_unit': price_unit,
                    'discount': discount,
                    'price_subtotal': price_subtotal,
                    'price_subtotal_incl': price_subtotal_incl,
                    'tax_ids': [(6, 0, taxes.ids)],
                }))
            
            if not order_lines:
                return self._json_response(
                    None,
                    status=400,
                    error='No valid order lines created'
                )
            
            order_vals['lines'] = order_lines
            
            # Calculate order totals
            total_amount = sum(line[2]['price_subtotal_incl'] for line in order_lines)
            total_tax = sum(line[2]['price_subtotal_incl'] - line[2]['price_subtotal'] for line in order_lines)
            
            # Process payments
            payment_lines = []
            total_paid = 0.0
            for payment_data in data['payments']:
                if not payment_data.get('payment_method_id'):
                    continue
                
                payment_method = request.env['pos.payment.method'].sudo().browse(payment_data['payment_method_id'])
                if not payment_method.exists():
                    return self._json_response(
                        None,
                        status=404,
                        error=f'Payment method {payment_data["payment_method_id"]} not found'
                    )
                
                amount = float(payment_data.get('amount', 0.0))
                total_paid += amount
                
                payment_lines.append((0, 0, {
                    'payment_method_id': payment_method.id,
                    'amount': amount,
                }))
            
            if not payment_lines:
                return self._json_response(
                    None,
                    status=400,
                    error='No valid payment lines created'
                )
            
            order_vals['payment_ids'] = payment_lines
            order_vals['amount_total'] = total_amount
            order_vals['amount_tax'] = total_tax
            order_vals['amount_paid'] = total_paid
            order_vals['amount_return'] = max(0.0, total_paid - total_amount)
            
            # Create the POS order
            pos_order = request.env['pos.order'].sudo().create(order_vals)
            
            # If order should be paid, set state to paid
            if total_paid >= total_amount and data.get('state') != 'draft':
                pos_order.action_pos_order_paid()
            
            # Return success response
            return self._json_response({
                'id': pos_order.id,
                'name': pos_order.name,
                'pos_reference': pos_order.pos_reference,
                'amount_total': pos_order.amount_total,
                'amount_paid': pos_order.amount_paid,
                'state': pos_order.state,
                'date_order': str(pos_order.date_order),
            })
            
        except Exception as e:
            _logger.error(f"Error creating POS order: {str(e)}", exc_info=True)
            return self._json_response(
                None,
                status=500,
                error=f'Internal server error: {str(e)}'
            )

    @http.route('/api/v1/webhook/pos-order', type='http', auth='none', methods=['GET', 'POST', 'OPTIONS'], csrf=False, cors='*')
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
        if request.httprequest.method == 'OPTIONS':
            return request.make_response(
                '',
                headers=[
                    ('Access-Control-Allow-Origin', '*'),
                    ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                    ('Access-Control-Allow-Headers', 'Content-Type'),
                    ('Access-Control-Max-Age', '3600'),
                ],
                status=200
            )
        
        # Handle GET request - return endpoint info
        if request.httprequest.method == 'GET':
            return self._json_response({
                'endpoint': '/api/v1/webhook/pos-order',
                'methods': ['GET', 'POST', 'OPTIONS'],
                'description': 'Webhook endpoint to create and confirm POS orders from external systems',
                'usage': 'Send POST request with JSON body containing order data',
                'status': 'active'
            })
        
        try:
            # Get JSON data from request body
            if request.httprequest.data:
                try:
                    data = json.loads(request.httprequest.data.decode('utf-8'))
                except (ValueError, UnicodeDecodeError) as e:
                    return self._json_response(
                        None,
                        status=400,
                        error=f'Invalid JSON format: {str(e)}'
                    )
            else:
                return self._json_response(
                    None,
                    status=400,
                    error='Request body is required'
                )
            
            # Authenticate - API key can be in header or body
            api_key = request.httprequest.headers.get('X-API-Key') or data.get('api_key')
            config = self._authenticate(api_key)
            if not config:
                return self._json_response(
                    None,
                    status=401,
                    error='Invalid or missing API key'
                )
            
            # Validate required fields
            required_fields = ['OrderID', 'OrderItems', 'CheckoutDetails', 'AmountTotal', 'AmountPaid']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return self._json_response(
                    None,
                    status=400,
                    error=f'Missing required fields: {", ".join(missing_fields)}'
                )
            
            # Get or create default POS session (you may want to make this configurable)
            pos_session = request.env['pos.session'].sudo().search([
                ('state', '=', 'opened')
            ], limit=1, order='id desc')
            
            if not pos_session:
                return self._json_response(
                    None,
                    status=400,
                    error='No open POS session found. Please open a POS session first.'
                )
            
            # Validate data consistency
            amount_total = float(data.get('AmountTotal', 0))
            amount_paid = float(str(data.get('AmountPaid', 0)).replace(',', ''))
            grand_total = float(data.get('GrandTotal', 0))
            tax = float(data.get('Tax', 0))
            tax_percent = float(data.get('TaxPercent', 0))
            amount_discount = float(data.get('AmountDiscount', 0))
            balance_amount = float(data.get('BalanceAmount', 0))
            
            # Calculate expected totals from order items
            calculated_total = 0.0
            calculated_tax = 0.0
            
            for item in data.get('OrderItems', []):
                item_price = float(item.get('Price', 0))
                item_qty = float(item.get('Quantity', 1))
                item_discount = float(item.get('DiscountAmount', 0))
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
                    error=f'Data inconsistency: Calculated total ({calculated_total_with_tax}) does not match GrandTotal ({grand_total})'
                )
            
            if abs(amount_paid - grand_total) > rounding * 10 and balance_amount > rounding:
                return self._json_response(
                    None,
                    status=400,
                    error=f'Data inconsistency: AmountPaid ({amount_paid}) + BalanceAmount ({balance_amount}) should equal GrandTotal ({grand_total})'
                )
            
            # Prepare order lines
            order_lines = []
            product_env = request.env['product.product'].sudo()
            
            for order_item in data.get('OrderItems', []):
                item_name = order_item.get('ItemName', '').strip()
                item_id = order_item.get('ItemID', 0)
                package_id = order_item.get('PackageID', 0)
                price = float(order_item.get('Price', 0))
                quantity = float(order_item.get('Quantity', 1))
                discount_amount = float(order_item.get('DiscountAmount', 0))
                
                # Find product by ItemID (if it's a valid Odoo product ID) or by name
                product = None
                if item_id and item_id > 0:
                    product = product_env.browse(item_id)
                    if not product.exists():
                        product = None
                
                if not product and item_name:
                    # Search by name
                    product = product_env.search([
                        ('name', '=', item_name),
                        ('sale_ok', '=', True),
                        ('available_in_pos', '=', True)
                    ], limit=1)
                    
                    if not product:
                        # Try case-insensitive search
                        product = product_env.search([
                            ('name', 'ilike', item_name),
                            ('sale_ok', '=', True),
                            ('available_in_pos', '=', True)
                        ], limit=1)
                
                if not product:
                    return self._json_response(
                        None,
                        status=404,
                        error=f'Product not found: ItemName="{item_name}", ItemID={item_id}'
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
                    partner=partner
                )
                
                price_subtotal = tax_results['total_excluded']
                price_subtotal_incl = tax_results['total_included']
                
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'qty': quantity,
                    'price_unit': price,
                    'discount': discount_percent,
                    'price_subtotal': price_subtotal,
                    'price_subtotal_incl': price_subtotal_incl,
                    'tax_ids': [(6, 0, taxes.ids)],
                }))
                
                # Handle OrderDetailPackages - these are components that need to be consumed
                order_detail_packages = order_item.get('OrderDetailPackages', [])
                if order_detail_packages:
                    # For each package item, create a consumption line or stock move
                    # This depends on your business logic - you might want to create
                    # separate order lines for components or handle them as BOM consumption
                    for package_item in order_detail_packages:
                        package_item_name = package_item.get('ItemName', '').strip()
                        package_item_id = package_item.get('ItemID', 0)
                        package_qty = float(package_item.get('Quantity', 0))
                        package_price = float(package_item.get('Price', 0))
                        
                        if package_qty > 0:
                            # Find the component product
                            component_product = None
                            if package_item_id and package_item_id > 0:
                                component_product = product_env.browse(package_item_id)
                                if not component_product.exists():
                                    component_product = None
                            
                            if not component_product and package_item_name:
                                component_product = product_env.search([
                                    ('name', '=', package_item_name),
                                    ('type', 'in', ['product', 'consu'])
                                ], limit=1)
                            
                            # If component found, you might want to create a consumption line
                            # For now, we'll log it - you can extend this based on your needs
                            if component_product:
                                _logger.info(
                                    f'Package component: {component_product.name} x {package_qty} '
                                    f'for order item {item_name}'
                                )
            
            if not order_lines:
                return self._json_response(
                    None,
                    status=400,
                    error='No valid order lines created'
                )
            
            # Process payments from CheckoutDetails
            payment_lines = []
            total_paid = 0.0
            
            for checkout in data.get('CheckoutDetails', []):
                payment_mode = checkout.get('PaymentMode', 1)
                amount = float(str(checkout.get('AmountPaid', 0)).replace(',', ''))
                card_type = checkout.get('CardType', 'Cash')
                reference_id = checkout.get('ReferenceID', '')
                
                if amount <= 0:
                    continue
                
                # Find payment method by name or create mapping
                # PaymentMode: 1 = Cash, others might be different payment methods
                payment_method = None
                
                if payment_mode == 1 or card_type == 'Cash':
                    # Find cash payment method
                    payment_method = pos_session.payment_method_ids.filtered(
                        lambda p: p.is_cash_count
                    )[:1]
                
                if not payment_method:
                    # Try to find by name
                    payment_method = pos_session.payment_method_ids.filtered(
                        lambda p: card_type.lower() in p.name.lower()
                    )[:1]
                
                if not payment_method:
                    # Get first available payment method
                    payment_method = pos_session.payment_method_ids[:1]
                
                if not payment_method:
                    return self._json_response(
                        None,
                        status=400,
                        error=f'No payment method found for PaymentMode={payment_mode}, CardType={card_type}'
                    )
                
                total_paid += amount
                payment_lines.append((0, 0, {
                    'payment_method_id': payment_method.id,
                    'amount': amount,
                    'payment_date': fields.Datetime.now(),
                }))
            
            if not payment_lines:
                return self._json_response(
                    None,
                    status=400,
                    error='No valid payment lines created'
                )
            
            # Validate payment amount matches
            if abs(total_paid - amount_paid) > rounding:
                return self._json_response(
                    None,
                    status=400,
                    error=f'Payment inconsistency: Sum of CheckoutDetails ({total_paid}) does not match AmountPaid ({amount_paid})'
                )
            
            # Calculate order totals from lines
            calculated_total = sum(line[2]['price_subtotal_incl'] for line in order_lines)
            calculated_tax = sum(
                line[2]['price_subtotal_incl'] - line[2]['price_subtotal']
                for line in order_lines
            )
            
            # Prepare order values
            order_vals = {
                'session_id': pos_session.id,
                'config_id': pos_session.config_id.id,
                'company_id': pos_session.config_id.company_id.id,
                'pricelist_id': pos_session.config_id.pricelist_id.id,
                'fiscal_position_id': pos_session.config_id.default_fiscal_position_id.id if pos_session.config_id.default_fiscal_position_id else False,
                'user_id': pos_session.user_id.id,
                'date_order': fields.Datetime.now(),
                'partner_id': False,  # No customer by default
                'to_invoice': False,
                'note': f'External Order ID: {data.get("OrderID")}',
                'lines': order_lines,
                'payment_ids': payment_lines,
                'amount_total': calculated_total,
                'amount_tax': calculated_tax,
                'amount_paid': total_paid,
                'amount_return': max(0.0, total_paid - calculated_total),
            }
            
            # Create the POS order
            pos_order = request.env['pos.order'].sudo().create(order_vals)
            
            # Confirm the order (mark as paid)
            try:
                pos_order.action_pos_order_paid()
            except Exception as e:
                _logger.error(f'Error confirming POS order: {str(e)}', exc_info=True)
                return self._json_response(
                    None,
                    status=500,
                    error=f'Failed to confirm order: {str(e)}'
                )
            
            # Create picking for inventory consumption (if needed)
            try:
                pos_order._create_order_picking()
            except Exception as e:
                _logger.warning(f'Could not create picking for order {pos_order.name}: {str(e)}')
            
            # Return success response
            return self._json_response({
                'id': pos_order.id,
                'name': pos_order.name,
                'pos_reference': pos_order.pos_reference,
                'amount_total': pos_order.amount_total,
                'amount_paid': pos_order.amount_paid,
                'amount_tax': pos_order.amount_tax,
                'state': pos_order.state,
                'date_order': str(pos_order.date_order),
                'external_order_id': data.get('OrderID'),
            })
            
        except Exception as e:
            _logger.error(f"Error in webhook_pos_order: {str(e)}", exc_info=True)
            return self._json_response(
                None,
                status=500,
                error=f'Internal server error: {str(e)}'
            )

    @http.route('/api/v1/health', type='http', auth='none', methods=['GET'], csrf=False, cors='*')
    def health_check(self, **kwargs):
        """Health check endpoint"""
        return self._json_response({
            'message': 'API is running',
            'version': '1.0',
        })

