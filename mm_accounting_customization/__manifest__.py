# -*- coding: utf-8 -*-
{
    'name': "mm_accounting_customization",
    'author': "3m-itsolutions",
    'website': "3mitsolutions.info@gmail.com",
    'category': 'Uncategorized',
    'version': '18.0',
    'depends': ['base', 'account', 'account_accountant', 'stock', 'hr', 'sale', 'sale_management', 'stock_account', 'account_reports', 'sales_team', 'stock_landed_costs'],
    # always load
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/extension_wizard.xml',
        'wizard/ramping_wizard.xml',
        'wizard/insurance_reduction_wizard.xml',
        'wizard/cash_guarantee_wizard.xml',
        'views/account_inherit.xml',
        'views/letter_of_guarantee.xml',
        'data/ir_sequence.xml',
        'views/insurance.xml',
        'views/sales_inherit.xml',
        'views/stock_valuation.xml',
        'views/res_config_settings_views.xml',

    ],
}
