from odoo import fields, models

class RequestLog(models.Model):
    _name = 'karage.request.logger'
    _description = 'Karage API Request Logger'
    _order = 'timestamp desc'
    
    url = fields.Char(string='Request URL', required=True)
    headers = fields.Text(string='Request Headers')
    body = fields.Text(string='Request Body')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True)
