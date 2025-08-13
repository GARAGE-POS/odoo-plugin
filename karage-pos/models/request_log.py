
from odoo import api, fields, models

class RequestLog(models.Model):
    _name = 'karage.request.log'
    _description = 'Web Request Log'

    method = fields.Char(string='HTTP Method')
    url = fields.Char(string='Request URL')
    headers = fields.Text(string='Request Headers')
    body = fields.Text(string='Request Body')
    response = fields.Text(string='Response')
    status_code = fields.Char(string='Status Code')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now)
