# Copyright 2021, Jarsa
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
{
    'name': 'Invoice Report for Superficie Tecnica',
    'summary': 'Customizations of Invoice Report',
    'version': '12.0.1.0.0',
    'category': 'Report',
    'website': 'https://www.jarsa.com.mx/',
    'author': 'Jarsa',
    'license': 'LGPL-3',
    'depends': [
        'l10n_mx_edi_transfer_external_trade',
    ],
    'data': [
        'reports/report_account_invoice.xml',
        'views/account_move_view.xml',
    ],
}
