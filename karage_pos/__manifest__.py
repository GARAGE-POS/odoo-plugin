{
    "name": "Karage POS",
    "summary": "REST API endpoints for syncing orders from Karage o Odoo",
    "version": "1.0.0",
    "development_status": "Alpha",
    "category": "Sales",
    "website": "https://karage.co",
    "author": "Karage",
    "maintainers": ["mabumusa1"],
    "license": "AGPL-3",
    "description": "REST API endpoints for syncing orders from Karage to Odoo",
    "depends": [
        "base",
        "product",
        "purchase",
        "point_of_sale",
        "account",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/webhook_log_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}
