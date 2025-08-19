from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class KarageOrderService(models.TransientModel):
    """Service class to handle Karage POS order processing"""
    _name = 'karage.order.service'
    _description = 'Karage Order Processing Service'

    @api.model
    def process_order(self, order_data):
        """
        Process a complete order from Karage POS
        
        Args:
            order_data (dict): Complete order data from POS
            
        Returns:
            dict: Processing result with sale_order_id and status
        """
        try:
            # Validate order data
            self._validate_order_data(order_data)
            
            # Create/get customer
            partner = self._get_or_create_customer(order_data)
            
            # Create sale order
            sale_order = self._create_sale_order(order_data, partner)
            
            # Process order lines
            self._process_order_lines(sale_order, order_data.get('OrderDetails', []))
            
            # Process payments
            self._process_payments(sale_order, order_data.get('OrderCheckoutDetails', []))
            
            # Confirm the order to update inventory
            if sale_order.state == 'draft':
                sale_order.action_confirm()
            
            # Sync inventory using our custom sync service
            sync_result = self._sync_inventory(order_data)
                
            return {
                'success': True,
                'sale_order_id': sale_order.id,
                'sale_order_name': sale_order.name,
                'inventory_sync': sync_result,
                'message': 'Order processed successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error processing Karage order: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _validate_order_data(self, order_data):
        """Validate required fields in order data"""
        required_fields = ['LocationID', 'OrderDetails']
        missing_fields = [field for field in required_fields if not order_data.get(field)]
        
        if missing_fields:
            raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
            
        if not order_data.get('OrderDetails'):
            raise ValidationError("Order must contain at least one item")

    def _get_or_create_customer(self, order_data):
        """Get or create customer based on order data"""
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

    def _create_sale_order(self, order_data, partner):
        """Create sales order from order data"""
        sale_order_vals = {
            'partner_id': partner.id,
            'date_order': fields.Datetime.now(),
            'origin': f"Karage POS - Location {order_data.get('LocationID')}",
            'note': order_data.get('Remark', ''),
        }
        
        return self.env['sale.order'].create(sale_order_vals)

    def _process_order_lines(self, sale_order, order_details):
        """Process order line items"""
        for detail in order_details:
            product = self._get_or_create_product(detail)
            
            # Create sale order line
            line_vals = {
                'order_id': sale_order.id,
                'product_id': product.id,
                'product_uom_qty': detail.get('Quantity', 1),
                'price_unit': detail.get('Price', 0),
                'discount': self._calculate_discount_percent(detail),
                'name': detail.get('Name', product.name),
            }
            
            self.env['sale.order.line'].create(line_vals)

    def _get_or_create_product(self, order_detail):
        """Get or create product based on order detail"""
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
            'type': 'consu',  # Goods/stockable product
            'list_price': order_detail.get('Price', 0),
            'standard_price': order_detail.get('Cost', 0),
            'categ_id': self._get_product_category(order_detail.get('itemType')),
        }
        
        return product_model.create(product_vals)

    def _get_product_category(self, item_type):
        """Get or create product category"""
        if not item_type:
            # Return default category
            default_category = self.env['product.category'].search([], limit=1)
            return default_category.id if default_category else 1
            
        category = self.env['product.category'].search([('name', '=', item_type)], limit=1)
        if not category:
            category = self.env['product.category'].create({'name': item_type})
        return category.id

    def _calculate_discount_percent(self, order_detail):
        """Calculate discount percentage from order detail"""
        price = order_detail.get('Price', 0)
        discount_amount = order_detail.get('DiscountAmount', 0)
        
        if price > 0 and discount_amount > 0:
            return (discount_amount / price) * 100
        return 0

    def _process_payments(self, sale_order, checkout_details):
        """Process payment information (for reference)"""
        # Note: In Odoo, payments are typically handled separately after invoicing
        # This method can be used to store payment references or create invoices
        
        total_paid = sum(detail.get('AmountPaid', 0) for detail in checkout_details)
        
        # You might want to add payment information to the order notes
        if checkout_details:
            payment_info = []
            for payment in checkout_details:
                payment_mode = payment.get('CardType', 'Unknown')
                amount = payment.get('AmountPaid', 0)
                payment_info.append(f"{payment_mode}: {amount}")
            
            payment_note = f"POS Payments: {', '.join(payment_info)}"
            if sale_order.note:
                sale_order.note += f"\n{payment_note}"
            else:
                sale_order.note = payment_note

    def _sync_inventory(self, order_data):
        """Sync inventory levels using the product sync service"""
        location_id = order_data.get('LocationID')
        order_details = order_data.get('OrderDetails', [])
        
        if not location_id or not order_details:
            return {'success': False, 'error': 'Missing location or order details for inventory sync'}
        
        sync_service = self.env['karage.product.sync']
        return sync_service.bulk_sync_products(order_details, location_id)