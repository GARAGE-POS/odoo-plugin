# -*- coding: utf-8 -*-
{
    'name': 'API Integration',
    'version': '18.0.1.0.0',
    'category': 'API',
    'summary': 'REST API endpoints for pushing Unit of Measures, Products, and Vendors',
    'description': """
        API Integration Module
        ======================
        
        This module provides REST API endpoints to push data from Odoo:
        
        * Unit of Measures (UoM)
        * Products (Product Templates and Variants)
        * Vendors (Supplier Partners)
        
        Features:
        - RESTful API endpoints
        - JSON format responses
        - API key authentication
        - Comprehensive documentation
        - Error handling and logging
    """,
    'author': 'SOFT GUIDE TECHNOLOGY',
    'website': 'https://www.softguidetech.com',
    'depends': [
        'base',
        'product',
        'purchase',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/api_security.xml',
        'views/api_config_views.xml',
        'views/external_order_sync_views.xml',
        'data/cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

