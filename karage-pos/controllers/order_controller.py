from odoo import http
from odoo.http import request, Response
import json

class OrderController(http.Controller):
    @http.route('/api/karage/handleOrder', type='json', auth='public', methods=['POST'], csrf=False)
    def handle_order(self, **kwargs):
        print("Aabbaaaaaaaaaaa")
        data = request.httprequest.json
        # Validate required fields
        required_fields = ['ItemID', 'OrderID', 'LocationID']
        missing = [field for field in required_fields if field not in data]
        if missing:
            return {'error': f'Missing fields: {", ".join(missing)}'}

        # Log the request
        log = request.env['karage.request.log'].sudo().create({
            'method': request.httprequest.method,
            'url': request.httprequest.url,
            'headers': json.dumps(dict(request.httprequest.headers)),
            'body': json.dumps(data),
            'response': '',  # You can fill this after processing if needed
            'status_code': '',  # You can fill this after processing if needed
        })
        return {'success': True, 'log_id': log.id}
