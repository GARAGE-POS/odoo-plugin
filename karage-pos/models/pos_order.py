from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Karage-specific fields
    karage_order_id = fields.Char(
        string='Karage Order ID',
        help='Original order ID from Karage POS system'
    )
    karage_location_id = fields.Integer(
        string='Karage Location ID',
        help='Location ID from Karage POS system'
    )
    karage_order_data = fields.Text(
        string='Original Order Data',
        help='Complete original order data from Karage API for reference'
    )

    @api.model
    def process_karage_order(self, order_data):
        """
        Process a complete order from Karage POS using standard POS workflow
        
        Args:
            order_data (dict): Complete order data from POS
            
        Returns:
            dict: Processing result with pos_order_id and status
        """
        try:
            # Log the request
            self._log_karage_request(order_data)
            
            # Validate order data
            self._validate_karage_order_data(order_data)
            
            # Get POS configuration for this location
            location_id = order_data.get('LocationID')
            pos_config = self.env['pos.config'].get_config_for_location(location_id)
            
            # Get or create session
            pos_session = pos_config.get_karage_session()
            
            # Create/get customer
            partner = self._get_or_create_customer_karage(order_data)
            
            # Create POS order
            pos_order = self._create_karage_pos_order(order_data, pos_session, partner)
            
            # Process order lines
            self._process_karage_order_lines(pos_order, order_data.get('OrderDetails', []))
            
            # Process payments
            self._process_karage_payments(pos_order, order_data.get('OrderCheckoutDetails', []))
            
            # Recalculate all amounts based on lines and payments
            pos_order._compute_prices()
            
            # Pay the order to trigger invoice and stock moves
            pos_order.action_pos_order_paid()
            
            # Generate invoice if configured
            if pos_config.karage_auto_invoice and pos_order.to_invoice:
                pos_order._generate_pos_order_invoice()
            
            return {
                'success': True,
                'pos_order_id': pos_order.id,
                'pos_order_name': pos_order.name,
                'session_id': pos_session.id,
                'invoice_id': pos_order.account_move.id if pos_order.account_move else None,
                'message': 'Order processed successfully using standard POS workflow'
            }
            
        except Exception as e:
            _logger.error(f"Error processing Karage order: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _log_karage_request(self, order_data):
        """Log the incoming API request"""
        self.env['karage.request.logger'].create({
            'url': '/api/karage/handleOrder',
            'body': str(order_data),
            'headers': '{}',
            'timestamp': fields.Datetime.now(),
        })

    def _validate_karage_order_data(self, order_data):
        """Validate required fields in order data"""
        # Check LocationID specifically (0 is a valid LocationID)
        if 'LocationID' not in order_data:
            raise ValidationError("Missing required field: LocationID")
            
        # Check OrderDetails
        if not order_data.get('OrderDetails'):
            raise ValidationError("Order must contain at least one item")

    def _get_or_create_customer_karage(self, order_data):
        """Get or create customer based on Karage order data"""
        partner_model = self.env['res.partner']
        
        # Try to find existing customer by CustomerID
        customer_id = order_data.get('CustomerID', 0)
        if customer_id and customer_id > 0:
            partner = partner_model.search([('ref', '=', str(customer_id))], limit=1)
            if partner:
                return partner
        
        # Create new customer or use default
        customer_name = order_data.get('CustomerName', '').strip()
        if customer_name:
            partner = partner_model.create({
                'name': customer_name,
                'ref': str(customer_id) if customer_id > 0 else None,
                'phone': order_data.get('CustomerContact', ''),
                'is_company': False,
                'customer_rank': 1,
            })
            return partner
        else:
            # Use default walk-in customer
            default_customer = partner_model.search([('name', '=', 'Walk-in Customer')], limit=1)
            if not default_customer:
                default_customer = partner_model.create({
                    'name': 'Walk-in Customer',
                    'is_company': False,
                    'customer_rank': 1,
                })
            return default_customer

    def _create_karage_pos_order(self, order_data, pos_session, partner):
        """Create POS order from Karage order data"""
        order_vals = {
            'session_id': pos_session.id,
            'partner_id': partner.id,
            'pricelist_id': pos_session.config_id.pricelist_id.id,
            'fiscal_position_id': partner.property_account_position_id.id if partner.property_account_position_id else False,
            'karage_order_id': str(order_data.get('OrderTakerID', '')),
            'karage_location_id': order_data.get('LocationID'),
            'karage_order_data': str(order_data),
            'to_invoice': True,  # Always create invoice for proper accounting
            'general_note': order_data.get('Remark', ''),
            # Initialize required amount fields with defaults
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        }
        
        return self.create(order_vals)

    def _process_karage_order_lines(self, pos_order, order_details):
        """Process order line items using standard POS order lines"""
        for detail in order_details:
            product = self._get_or_create_product_karage(detail)
            
            # Create POS order line with required fields
            quantity = detail.get('Quantity', 1)
            price_unit = detail.get('Price', 0)
            discount = self._calculate_discount_percent_karage(detail)
            
            line_vals = {
                'order_id': pos_order.id,
                'product_id': product.id,
                'qty': quantity,
                'price_unit': price_unit,
                'discount': discount,
                'full_product_name': detail.get('Name', product.name),
                'price_subtotal': price_unit * quantity * (1 - discount / 100),
                'price_subtotal_incl': price_unit * quantity * (1 - discount / 100),  # Assuming no tax
            }
            
            self.env['pos.order.line'].create(line_vals)

    def _get_or_create_product_karage(self, order_detail):
        """Get or create product based on Karage order detail"""
        product_model = self.env['product.product']
        
        # Try to find existing product by ItemID
        item_id = order_detail.get('ItemID')
        if item_id:
            product = product_model.search([('default_code', '=', str(item_id))], limit=1)
            if product:
                return product
        
        # Create new product
        product_vals = {
            'name': order_detail.get('Name', f"Product {item_id}"),
            'default_code': str(item_id) if item_id else None,
            'type': 'consu',  # Consumable product for proper inventory
            'is_storable': True,  # Enable inventory tracking
            'list_price': order_detail.get('Price', 0),
            'standard_price': order_detail.get('Cost', 0),
            'categ_id': self._get_karage_product_category(order_detail.get('itemType')),
            'available_in_pos': True,
        }
        
        return product_model.create(product_vals)

    def _get_karage_product_category(self, item_type):
        """Get or create product category for Karage items"""
        if not item_type:
            # Return Karage default category
            try:
                return self.env.ref('karage-pos.product_category_karage').id
            except ValueError:
                # Create default category if it doesn't exist
                default_category = self.env['product.category'].create({
                    'name': 'Karage POS'
                })
                return default_category.id
            
        category = self.env['product.category'].search([('name', '=', item_type)], limit=1)
        if not category:
            try:
                parent_id = self.env.ref('karage-pos.product_category_karage').id
            except ValueError:
                # Create parent category first
                parent_category = self.env['product.category'].create({
                    'name': 'Karage POS'
                })
                parent_id = parent_category.id
                
            category = self.env['product.category'].create({
                'name': item_type,
                'parent_id': parent_id
            })
        return category.id

    def _calculate_discount_percent_karage(self, order_detail):
        """Calculate discount percentage from Karage order detail"""
        price = order_detail.get('Price', 0)
        discount_amount = order_detail.get('DiscountAmount', 0)
        
        if price > 0 and discount_amount > 0:
            return (discount_amount / price) * 100
        return 0

    def _process_karage_payments(self, pos_order, checkout_details):
        """Process payment information using standard POS payments"""
        if not checkout_details:
            return
            
        for payment_detail in checkout_details:
            payment_method = self._get_karage_payment_method(payment_detail, pos_order.session_id)
            amount_paid = payment_detail.get('AmountPaid', 0)
            
            if amount_paid > 0:
                payment_vals = {
                    'pos_order_id': pos_order.id,
                    'payment_method_id': payment_method.id,
                    'amount': amount_paid,
                    'card_type': payment_detail.get('CardType', ''),
                    'cardholder_name': payment_detail.get('CardHolderName', ''),
                    'transaction_id': payment_detail.get('CardNumber', ''),
                }
                
                self.env['pos.payment'].create(payment_vals)

    def _get_karage_payment_method(self, payment_detail, pos_session=None):
        """Get appropriate payment method based on Karage payment data"""
        card_type = payment_detail.get('CardType', '').lower()
        
        # Use the provided session to find available payment methods
        if pos_session and pos_session.config_id.payment_method_ids:
            available_methods = pos_session.config_id.payment_method_ids
            
            # Look for cash method first
            if 'cash' in card_type:
                cash_method = available_methods.filtered(lambda pm: 'cash' in pm.name.lower())
                if cash_method:
                    return cash_method[0]
            
            # Look for card method
            if 'card' in card_type or 'credit' in card_type or 'debit' in card_type:
                card_method = available_methods.filtered(lambda pm: 'card' in pm.name.lower())
                if card_method:
                    return card_method[0]
            
            # Default to first available method
            if available_methods:
                return available_methods[0]
        
        # Fallback: Look for any payment method
        if 'cash' in card_type:
            cash_method = self.env['pos.payment.method'].search([('name', 'ilike', 'cash')], limit=1)
            if cash_method:
                return cash_method
        
        # Default to any available payment method
        any_method = self.env['pos.payment.method'].search([], limit=1)
        if any_method:
            return any_method
            
        # Last resort: create a basic cash method
        return self._get_or_create_cash_payment_method()

    def _get_or_create_cash_payment_method(self):
        """Get or create a basic cash payment method"""
        # Look for any cash payment method
        cash_method = self.env['pos.payment.method'].search([('name', '=', 'Cash')], limit=1)
        
        if not cash_method:
            # Create a basic cash journal first
            cash_journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
            if not cash_journal:
                cash_journal = self.env['account.journal'].create({
                    'name': 'Cash',
                    'code': 'CSH1',
                    'type': 'cash',
                })
            
            # Create cash payment method
            cash_method = self.env['pos.payment.method'].create({
                'name': 'Cash',
                'is_cash_count': True,
                'cash_journal_id': cash_journal.id,
            })
            
        return cash_method
    
    def action_view_invoice(self):
        """Action to view the generated invoice"""
        self.ensure_one()
        if self.account_move:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Invoice',
                'res_model': 'account.move',
                'res_id': self.account_move.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return False
    
    def action_view_picking(self):
        """Action to view related stock moves"""
        self.ensure_one()
        stock_moves = self.env['stock.move'].search([
            ('origin', '=', self.name)
        ])
        
        if stock_moves:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Stock Moves',
                'res_model': 'stock.move',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', stock_moves.ids)],
                'target': 'current',
            }
        return False