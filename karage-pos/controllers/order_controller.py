from odoo import http
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class OrderController(http.Controller):
    @http.route('/api/karage/handleOrder', type='json', auth='public', methods=['POST'], csrf=False)
    def handle_order(self, **kwargs):
        """
        Handle complete order processing from Karage POS using custom workflow
        
        Expected JSON structure:
        {
            "LocationID": int,
            "CustomerID": int,
            "CustomerName": str,
            "CustomerContact": str,
            "AmountTotal": float,
            "OrderDetails": [
                {
                    "ItemID": int,
                    "Name": str,
                    "Quantity": int,
                    "Price": float,
                    "Cost": float,
                    "itemType": str,
                    "DiscountAmount": float,
                    ...
                }
            ],
            "OrderCheckoutDetails": [
                {
                    "PaymentMode": int,
                    "AmountPaid": float,
                    "CardType": str,
                    "CardHolderName": str,
                    ...
                }
            ],
            "OrderTakerID": str,
            "CheckoutDate": str,
            "Remark": str,
            ...
        }
        """
        log = None
        try:
            data = request.httprequest.json or {}
            
            # Log the incoming request for audit purposes
            log = request.env['karage.request.logger'].sudo().create({
                'url': request.httprequest.url,
                'headers': json.dumps(dict(request.httprequest.headers)),
                'body': json.dumps(data),
            })
            
            _logger.info(f"Processing Karage order for LocationID: {data.get('LocationID')}")
            
            # Process the order using the custom order service
            order_service = request.env['karage.order.service'].sudo()
            result = order_service.process_order(data)
            
            # Add log ID to result for tracking
            result['log_id'] = log.id
            result['api_version'] = '2.0'  # Indicate custom processing
            
            if result.get('success'):
                _logger.info(f"Successfully processed Karage order: {result.get('sale_order_name')}")
            else:
                _logger.error(f"Failed to process Karage order: {result.get('error')}")
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in handle_order endpoint: {str(e)}")
            return {
                'success': False,
                'error': f'Internal server error: {str(e)}',
                'log_id': log.id if log else None,
                'api_version': '2.0'
            }
