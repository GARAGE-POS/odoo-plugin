
# Copyright <2025> Mohammad Abu Musa <m.abumusa@karage.co>
# License AGPL-3
{
    "name": "Karage POS",
    "summary": "Integrate Karage POS with Odoo",
    "version": "1.0.0",
    "development_status": "Alpha",
    "category": "Sales",
    "website": "https://karage.co",
    "author": "Karage",
    "maintainers": ["mabumusa1"],
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    #"pre_init_hook": "pre_init_hook",
    #"post_init_hook": "post_init_hook",
    #"post_load": "post_load",
    #"uninstall_hook": "uninstall_hook",    
    "depends": ['base', 'sale', 'stock', 'product', 'account', 'stock_account', 'point_of_sale'],
    "data": [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/pos_config_data.xml',
        'data/payment_method_data.xml',
        'data/sequence_data.xml',
        'data/demo_products_data.xml',
        'views/pos_config_views.xml',
        'views/pos_order_views.xml',
        'views/pos_session_views.xml',
        'views/monitoring_views.xml',
        'views/menu_views.xml',
    ],
}
