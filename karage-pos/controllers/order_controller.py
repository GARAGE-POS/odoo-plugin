from odoo import http
from odoo.http import request, Response
import json

class OrderController(http.Controller):
    @http.route('/api/karage/handleOrder', type='json', auth='public', methods=['POST'], csrf=False)
    def handle_order(self, **kwargs):
        data = request.httprequest.json
        required_fields = ['ItemID', 'OrderID', 'LocationID']
        missing = [field for field in required_fields if field not in data]
        if missing:
            return {'error': f'Missing fields: {", ".join(missing)}'}

        # Log the request
        log = request.env['karage.request.logger'].sudo().create({
            'url': request.httprequest.url,
            'headers': json.dumps(dict(request.httprequest.headers)),
            'body': json.dumps(data),
        })
        return {'success': True, 'id': log.id}
