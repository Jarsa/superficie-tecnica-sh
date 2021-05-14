# Copyright 2021, Jarsa Sistemas, S.A. de C.V.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, models, fields, tools, _
from odoo.tools.xml_utils import _check_with_xsd

import logging
import re
import base64
import json
import requests
import random
import string

from lxml import etree
from lxml.objectify import fromstring
from datetime import datetime
from io import BytesIO
from zeep import Client
from zeep.transports import Transport
from json.decoder import JSONDecodeError

_logger = logging.getLogger(__name__)


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _check_discounts(self, discounts):
        has_100_percent = False
        for rec in discounts:
            if rec == 100:
                has_100_percent = True
        return has_100_percent

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        ''' Doesn't check if the config is correct so you need to call _l10n_mx_edi_check_config first.
        :param invoice:
        :return:
        '''
        cfdi_date = datetime.combine(
            fields.Datetime.from_string(invoice.invoice_date),
            invoice.l10n_mx_edi_post_time.time(),
        ).strftime('%Y-%m-%dT%H:%M:%S')

        cfdi_values = {
            **self._l10n_mx_edi_get_common_cfdi_values(invoice),
            'document_type': 'I' if invoice.move_type == 'out_invoice' else 'E',
            'currency_name': invoice.currency_id.name,
            'payment_method_code': (invoice.l10n_mx_edi_payment_method_id.code or '').replace('NA', '99'),
            'payment_policy': invoice.l10n_mx_edi_payment_policy,
            'cfdi_date': cfdi_date,
        }

        # ==== Invoice Values ====

        invoice_lines = invoice.invoice_line_ids.filtered(lambda inv: not inv.display_type)

        if invoice.currency_id == invoice.company_currency_id:
            cfdi_values['currency_conversion_rate'] = None
        else:
            sign = 1 if invoice.move_type in ('out_invoice', 'out_receipt', 'in_refund') else -1
            total_amount_currency = sign * invoice.amount_total
            total_balance = invoice.amount_total_signed
            discounts = invoice.invoice_line_ids.mapped('discount')
            has_100_percent = self._check_discounts(discounts)
            if not has_100_percent:
                cfdi_values['currency_conversion_rate'] = total_balance / total_amount_currency
            else:
                rate = invoice.currency_id._get_rates(
                    self.env.company, invoice.invoice_date)
                cfdi_values['currency_conversion_rate'] = 1 / rate[2]

        if invoice.partner_bank_id:
            digits = [s for s in invoice.partner_bank_id.acc_number if s.isdigit()]
            acc_4number = ''.join(digits)[-4:]
            cfdi_values['account_4num'] = acc_4number if len(acc_4number) == 4 else None
        else:
            cfdi_values['account_4num'] = None

        if cfdi_values['customer'].country_id.l10n_mx_edi_code != 'MEX' and cfdi_values['customer_rfc'] not in ('XEXX010101000', 'XAXX010101000'):
            cfdi_values['customer_fiscal_residence'] = cfdi_values['customer'].country_id.l10n_mx_edi_code
        else:
            cfdi_values['customer_fiscal_residence'] = None

        # ==== Invoice lines ====

        cfdi_values['invoice_line_values'] = []
        for line in invoice_lines:
            cfdi_values['invoice_line_values'].append(self._l10n_mx_edi_get_invoice_line_cfdi_values(invoice, line))

        # ==== Totals ====

        cfdi_values['total_amount_untaxed_wo_discount'] = sum(vals['total_wo_discount'] for vals in cfdi_values['invoice_line_values'])
        cfdi_values['total_amount_untaxed_discount'] = sum(vals['discount_amount'] for vals in cfdi_values['invoice_line_values'])

        # ==== Taxes ====

        cfdi_values['tax_details_transferred'] = {}
        cfdi_values['tax_details_withholding'] = {}
        for vals in cfdi_values['invoice_line_values']:
            for tax_res in vals['tax_details_transferred']:
                cfdi_values['tax_details_transferred'].setdefault(tax_res['tax'], {
                    'tax': tax_res['tax'],
                    'tax_type': tax_res['tax_type'],
                    'tax_amount': tax_res['tax_amount'],
                    'tax_name': tax_res['tax_name'],
                    'total': 0.0,
                })
                cfdi_values['tax_details_transferred'][tax_res['tax']]['total'] += tax_res['total']
            for tax_res in vals['tax_details_withholding']:
                cfdi_values['tax_details_withholding'].setdefault(tax_res['tax'], {
                    'tax': tax_res['tax'],
                    'tax_type': tax_res['tax_type'],
                    'tax_amount': tax_res['tax_amount'],
                    'tax_name': tax_res['tax_name'],
                    'total': 0.0,
                })
                cfdi_values['tax_details_withholding'][tax_res['tax']]['total'] += tax_res['total']

        cfdi_values['tax_details_transferred'] = list(cfdi_values['tax_details_transferred'].values())
        cfdi_values['tax_details_withholding'] = list(cfdi_values['tax_details_withholding'].values())
        cfdi_values['total_tax_details_transferred'] = sum(vals['total'] for vals in cfdi_values['tax_details_transferred'])
        cfdi_values['total_tax_details_withholding'] = sum(vals['total'] for vals in cfdi_values['tax_details_withholding'])

        return cfdi_values
