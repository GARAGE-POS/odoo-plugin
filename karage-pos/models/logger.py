from odoo import fields, models

class RequestLog(models.Model):
    _name = 'karage.request.logger'
    _description = 'Logs the incoming requests and save them to the database, this model used for auditing and should be cleand up every period of time via another cron'

    url = fields.Char(string='Request URL')
    headers = fields.Text(string='Request Headers')
    body = fields.Text(string='Request Body')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now)
