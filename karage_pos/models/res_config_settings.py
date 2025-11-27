# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Idempotency configuration
    idempotency_processing_timeout = fields.Integer(
        string='Idempotency Processing Timeout (minutes)',
        default=5,
        config_parameter='karage_pos.idempotency_processing_timeout',
        help='Maximum time a request can stay in "processing" status before being considered stuck. '
             'After this timeout, the request can be retried. Default: 5 minutes.'
    )

    idempotency_retention_days = fields.Integer(
        string='Idempotency Record Retention (days)',
        default=30,
        config_parameter='karage_pos.idempotency_retention_days',
        help='Number of days to keep idempotency records before automatic cleanup. '
             'Completed and failed records older than this will be deleted. '
             'Default: 30 days. Set to 0 to disable automatic cleanup.'
    )
