# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import ast


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    sales_man_id = fields.Many2one('hr.employee', string="Sales Man",)
