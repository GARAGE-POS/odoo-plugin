# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ==========================================
    # POS Configuration Section
    # ==========================================

    account_default_pos_receivable_account_id = fields.Many2one(
        'account.account',
        string='Default POS Receivable Account',
        related='company_id.account_default_pos_receivable_account_id',
        readonly=False,
        help='Default receivable account used for POS payments. '
             'This is a temporary account used to track POS customer payments.'
    )

    external_pos_config_id = fields.Many2one(
        'pos.config',
        string='External POS Configuration',
        config_parameter='karage_pos.external_pos_config_id',
        help='Select the POS configuration to use for webhook orders. '
             'This is required for the webhook integration to work.'
    )

    acceptable_session_states = fields.Char(
        string='Acceptable Session States',
        default='opened,opening_control',
        config_parameter='karage_pos.acceptable_session_states',
        help='Comma-separated list of valid POS session states. '
             'Only sessions in these states will accept webhook orders. '
             'Default: "opened,opening_control"'
    )

    # ==========================================
    # Session Auto-Close Configuration
    # ==========================================

    auto_close_sessions = fields.Boolean(
        string='Auto-Close Idle Sessions',
        default=True,
        config_parameter='karage_pos.auto_close_sessions',
        help='Automatically close POS sessions after a period of inactivity. '
             'When enabled, sessions with no new orders for the configured '
             'timeout period will be automatically closed by a scheduled job.'
    )

    session_idle_timeout_minutes = fields.Integer(
        string='Session Idle Timeout (minutes)',
        default=60,
        config_parameter='karage_pos.session_idle_timeout_minutes',
        help='Number of minutes of inactivity before a session is automatically closed. '
             'Default: 60 minutes (1 hour). Set to 0 to disable auto-closing.'
    )

    # ==========================================
    # Payment Configuration Section
    # ==========================================

    fallback_payment_mode = fields.Char(
        string='Default Payment Mode',
        default='1',
        config_parameter='karage_pos.fallback_payment_mode',
        help='Default external payment mode code when not provided in webhook. Default: 1'
    )

    fallback_payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='Default Payment Method',
        config_parameter='karage_pos.fallback_payment_method_id',
        help='Fallback POS payment method when no mapping exists for the external payment code.'
    )

    # ==========================================
    # Order Processing Section
    # ==========================================

    external_order_source_code = fields.Char(
        string='External Order Source Code',
        default='karage_pos_webhook',
        config_parameter='karage_pos.external_order_source_code',
        help='Identifier stored on orders received via webhook. '
             'Used to track order source. Default: "karage_pos_webhook"'
    )

    consistency_check_multiplier = fields.Char(
        string='Consistency Check Multiplier',
        default='10.0',
        config_parameter='karage_pos.consistency_check_multiplier',
        help='Multiplier applied to currency rounding for data consistency checks. '
             'Higher values allow larger tolerances. Default: 10.0'
    )

    tax_calculation_priority = fields.Selection(
        [('percent_first', 'Use Tax Percent First'),
         ('amount_first', 'Use Tax Amount First')],
        string='Tax Calculation Priority',
        default='percent_first',
        config_parameter='karage_pos.tax_calculation_priority',
        help='When both tax percent and tax amount are provided, which to use first. '
             'Default: Use tax percent if available.'
    )

    # ==========================================
    # Product Validation Section
    # ==========================================

    product_require_sale_ok = fields.Boolean(
        string='Require Sale OK',
        default=True,
        config_parameter='karage_pos.product_require_sale_ok',
        help='Only accept products where "Can be Sold" is enabled. Default: True'
    )

    product_require_available_in_pos = fields.Boolean(
        string='Require Available in POS',
        default=True,
        config_parameter='karage_pos.product_require_available_in_pos',
        help='Only accept products where "Available in POS" is enabled. Default: True'
    )

    enforce_product_company_match = fields.Boolean(
        string='Enforce Product Company Match',
        default=True,
        config_parameter='karage_pos.enforce_product_company_match',
        help='Require products to belong to the same company as the POS session. Default: True'
    )

    # ==========================================
    # API & Logging Section
    # ==========================================

    api_key_scopes = fields.Char(
        string='API Key Scopes',
        default='rpc,odoo.addons.base.models.res_users',
        config_parameter='karage_pos.api_key_scopes',
        help='Comma-separated list of API key scopes to try for authentication. '
             'Default: "rpc,odoo.addons.base.models.res_users"'
    )

    log_key_truncation_length = fields.Char(
        string='Log Key Truncation Length',
        default='20',
        config_parameter='karage_pos.log_key_truncation_length',
        help='Number of characters to show when logging idempotency keys (for privacy). Default: 20'
    )

    # ==========================================
    # Existing Settings (unchanged)
    # ==========================================

    # Idempotency configuration
    idempotency_processing_timeout = fields.Char(
        string='Idempotency Processing Timeout (minutes)',
        default='5',
        config_parameter='karage_pos.idempotency_processing_timeout',
        help='Maximum time a request can stay in "processing" status before being considered stuck. '
             'After this timeout, the request can be retried. Default: 5 minutes.'
    )

    idempotency_retention_days = fields.Char(
        string='Idempotency Record Retention (days)',
        default='30',
        config_parameter='karage_pos.idempotency_retention_days',
        help='Number of days to keep idempotency records before automatic cleanup. '
             'Completed and failed records older than this will be deleted. '
             'Default: 30 days. Set to 0 to disable automatic cleanup.'
    )

    # Bulk sync configuration
    bulk_sync_max_orders = fields.Char(
        string='Bulk Sync Max Orders',
        default='1000',
        config_parameter='karage_pos.bulk_sync_max_orders',
        help='Maximum number of orders allowed in a single bulk sync request. '
             'Default: 1000 orders.'
    )

    # Order validation configuration
    valid_order_statuses = fields.Char(
        string='Valid Order Statuses',
        default='103',
        config_parameter='karage_pos.valid_order_statuses',
        help='Comma-separated list of valid OrderStatus values from external POS system. '
             'Only orders with these status codes will be accepted. '
             'Example: "103,104" to accept multiple statuses. Default: "103" (completed orders).'
    )
