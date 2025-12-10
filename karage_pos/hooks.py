# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)

# Payment methods to create (without journals - admin must configure)
PAYMENT_METHODS = [
    {'name': 'Cash', 'is_cash_count': True},
    {'name': 'Bank', 'is_cash_count': False},
    {'name': 'Customer Account', 'is_cash_count': False},
    {'name': 'Tamara', 'is_cash_count': False},
    {'name': 'Tabby', 'is_cash_count': False},
    {'name': 'Visa', 'is_cash_count': False},
    {'name': 'Mada', 'is_cash_count': False},
]


def post_init_hook(env):
    """
    Post-installation hook to create default POS configuration.

    This runs once after module installation and creates:
    - Default Karage POS configuration (one per company)
    - Required payment methods (without journals)
    - Sets default config parameters
    """
    _logger.info("Running Karage POS post-installation hook...")

    try:
        # Process each company
        companies = env['res.company'].search([])
        created_pos_ids = []

        for company in companies:
            pos_config = _create_default_pos_for_company(env, company)
            if pos_config:
                created_pos_ids.append(pos_config.id)

        # Set the first created POS as the default external POS config
        if created_pos_ids:
            env['ir.config_parameter'].sudo().set_param(
                'karage_pos.external_pos_config_id',
                str(created_pos_ids[0])
            )
            _logger.info(f"Set external_pos_config_id to {created_pos_ids[0]}")

        _logger.info("Karage POS post-installation completed successfully!")

    except Exception as e:
        _logger.error(f"Error in Karage POS post-installation hook: {str(e)}", exc_info=True)
        # Don't raise - let installation complete even if hook fails
        # Admin can manually configure


def _create_default_pos_for_company(env, company):
    """
    Create default Karage POS configuration for a specific company.

    :param env: Odoo environment
    :param company: res.company record
    :return: pos.config record or None
    """
    _logger.info(f"Processing company: {company.name} (ID: {company.id})")

    # Check if default POS already exists for this company (idempotency)
    existing_default = env['pos.config'].search([
        ('is_karage_default_pos', '=', True),
        ('company_id', '=', company.id),
    ], limit=1)

    if existing_default:
        _logger.info(
            f"Default Karage POS already exists for {company.name}: "
            f"{existing_default.name} (ID: {existing_default.id})"
        )
        return existing_default

    # Get or create pricelist
    pricelist = _get_or_create_pricelist(env, company)

    # Create payment methods (without journals)
    payment_method_ids = _create_payment_methods(env, company)

    # Get default picking type (warehouse)
    picking_type = env['stock.picking.type'].search([
        ('code', '=', 'outgoing'),
        ('warehouse_id.company_id', '=', company.id)
    ], limit=1)

    if not picking_type:
        _logger.warning(
            f"No outgoing picking type found for {company.name}. "
            "POS may need manual warehouse configuration."
        )

    # Find company-specific journals
    # POS journal (sale type for orders)
    pos_journal = env['account.journal'].search([
        ('type', '=', 'sale'),
        ('company_id', '=', company.id),
    ], limit=1)

    # Invoice journal (sale type for invoices)
    invoice_journal = env['account.journal'].search([
        ('type', '=', 'sale'),
        ('company_id', '=', company.id),
    ], limit=1)

    if not pos_journal:
        _logger.warning(
            f"No sales journal found for {company.name}. "
            "POS may need manual journal configuration."
        )

    # Create the default POS configuration
    # Explicitly set journal_id and invoice_journal_id to prevent Odoo
    # from using default journals from other companies
    # Note: module_pos_discount cannot be set during post_init_hook as it triggers
    # module installation. Admin can enable it later in POS settings.
    pos_config_vals = {
        'name': 'KARAGE - Default POS',
        'is_karage_default_pos': True,
        'company_id': company.id,
        'pricelist_id': pricelist.id if pricelist else False,
        'payment_method_ids': [(6, 0, payment_method_ids)],
        'iface_tax_included': 'total',  # Prices include tax
        'picking_type_id': picking_type.id if picking_type else False,
        'journal_id': pos_journal.id if pos_journal else False,
        'invoice_journal_id': invoice_journal.id if invoice_journal else False,
    }

    pos_config = env['pos.config'].create(pos_config_vals)
    _logger.info(
        f"Created default Karage POS for {company.name}: "
        f"{pos_config.name} (ID: {pos_config.id})"
    )

    return pos_config


def _get_or_create_pricelist(env, company):
    """Get existing pricelist or create a default one for the company."""
    pricelist = env['product.pricelist'].search([
        '|',
        ('company_id', '=', company.id),
        ('company_id', '=', False),
    ], limit=1)

    if not pricelist:
        pricelist = env['product.pricelist'].create({
            'name': f'{company.name} - Default Pricelist',
            'company_id': company.id,
            'currency_id': company.currency_id.id,
        })
        _logger.info(f"Created default pricelist: {pricelist.name}")

    return pricelist


def _create_payment_methods(env, company):
    """
    Create POS payment methods without journal assignment.

    Creates NEW payment methods with "Karage - " prefix to avoid conflicts
    with existing payment methods (cash methods can only be used in one POS).

    :param env: Odoo environment
    :param company: res.company record
    :return: List of payment method IDs
    """
    payment_method_ids = []

    for pm_data in PAYMENT_METHODS:
        # Use "Karage - " prefix to create unique payment methods
        karage_name = f"Karage - {pm_data['name']}"

        # Check if Karage payment method already exists
        existing = env['pos.payment.method'].search([
            ('name', '=', karage_name),
            ('company_id', '=', company.id),
        ], limit=1)

        if existing:
            _logger.info(f"Payment method already exists: {karage_name}")
            payment_method_ids.append(existing.id)
            continue

        # Create payment method WITHOUT journal_id
        # Admin must manually assign journals after installation
        pm = env['pos.payment.method'].create({
            'name': karage_name,
            'is_cash_count': pm_data['is_cash_count'],
            'company_id': company.id,
            # journal_id intentionally left empty - admin must configure
        })
        payment_method_ids.append(pm.id)
        _logger.info(f"Created payment method: {karage_name} (ID: {pm.id})")

    return payment_method_ids
