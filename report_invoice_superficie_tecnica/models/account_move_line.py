# Copyright 2020, Jarsa Sistemas, S.A. de C.V.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import fields, models, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    raw_material = fields.Float()
    value_added = fields.Float(store=True, compute="_compute_bank_line_count")

    @api.onchange('raw_material', 'price_subtotal')
    def _compute_bank_line_count(self):
        for rec in self:
            rec.value_added = rec.price_subtotal - rec.raw_material

