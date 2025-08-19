from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class KarageProductSync(models.TransientModel):
    """Handle product synchronization between Karage POS and Odoo"""
    _name = 'karage.product.sync'
    _description = 'Karage Product Synchronization Service'

    @api.model
    def sync_product_stock(self, item_id, location_id, quantity_sold):
        """
        Update product stock after a sale
        
        Args:
            item_id (int): Karage ItemID
            location_id (int): Karage LocationID
            quantity_sold (int): Quantity that was sold
            
        Returns:
            dict: Sync result
        """
        try:
            # Find the product
            product = self._get_product_by_item_id(item_id)
            if not product:
                return {
                    'success': False,
                    'error': f'Product with ItemID {item_id} not found'
                }
            
            # Get or create stock location
            stock_location = self._get_stock_location(location_id)
            
            # Update stock levels
            self._update_stock_levels(product, stock_location, quantity_sold)
            
            return {
                'success': True,
                'product_id': product.id,
                'product_name': product.name,
                'location_id': stock_location.id,
                'quantity_updated': quantity_sold
            }
            
        except Exception as e:
            _logger.error(f"Error syncing product stock: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_product_by_item_id(self, item_id):
        """Get product by Karage ItemID"""
        return self.env['product.product'].search([
            ('default_code', '=', str(item_id))
        ], limit=1)

    def _get_stock_location(self, location_id):
        """Get or create stock location for Karage location"""
        location_name = f"Karage Location {location_id}"
        
        # Try to find existing location
        location = self.env['stock.location'].search([
            ('name', '=', location_name),
            ('usage', '=', 'internal')
        ], limit=1)
        
        if not location:
            # Create new location under main warehouse
            warehouse = self.env['stock.warehouse'].search([], limit=1)
            parent_location = warehouse.lot_stock_id if warehouse else self.env.ref('stock.stock_location_stock')
            
            location = self.env['stock.location'].create({
                'name': location_name,
                'usage': 'internal',
                'location_id': parent_location.id,
                'barcode': f'KARAGE_LOC_{location_id}',
            })
            
        return location

    def _update_stock_levels(self, product, location, quantity_sold):
        """Update stock levels after sale"""
        # Create stock move to represent the sale
        stock_move_vals = {
            'name': f'Karage POS Sale - {product.name}',
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': quantity_sold,
            'location_id': location.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'state': 'done',
            'date': fields.Datetime.now(),
            'origin': 'Karage POS',
        }
        
        stock_move = self.env['stock.move'].create(stock_move_vals)
        stock_move._action_done()

    @api.model
    def bulk_sync_products(self, order_details, location_id):
        """
        Sync multiple products from an order
        
        Args:
            order_details (list): List of order detail items
            location_id (int): Karage LocationID
            
        Returns:
            dict: Bulk sync results
        """
        results = []
        errors = []
        
        for detail in order_details:
            item_id = detail.get('ItemID')
            quantity = detail.get('Quantity', 1)
            
            if not item_id:
                errors.append(f"Missing ItemID in order detail: {detail}")
                continue
                
            result = self.sync_product_stock(item_id, location_id, quantity)
            results.append(result)
            
            if not result.get('success'):
                errors.append(result.get('error', 'Unknown error'))
        
        return {
            'success': len(errors) == 0,
            'results': results,
            'errors': errors,
            'total_items': len(order_details),
            'successful_syncs': len([r for r in results if r.get('success')])
        }