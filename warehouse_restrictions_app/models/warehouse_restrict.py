# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResUsers(models.Model):
    _inherit = "res.users"

    restrict_location = fields.Boolean(string="Restrict Location")
    restrict_warehouse_operation = fields.Boolean(string="Restrict Operation")
    restrict_stock_warehouse_operation = fields.Boolean(string="Restrict Stock Warehouse")
    picking_type_ids = fields.Many2many('stock.picking.type', string="Warehouse Operation")
    available_location_ids = fields.Many2many('stock.location', string='Allowed Locations')
    available_warehouse_ids = fields.Many2many('stock.warehouse', string='Allowed Warehouse')

    def write(self, vals):
        if 'available_location_ids' in vals:
            self.env['ir.model.access'].call_cache_clearing_methods()
            # self.env['ir.rule'].clear_caches()
        # self.has_group.clear_cache(self)

        if 'picking_type_ids' in vals:
            self.env['ir.model.access'].call_cache_clearing_methods()
            # self.env['ir.rule'].clear_caches()
        # self.has_group.clear_cache(self)

        if 'available_warehouse_ids' in vals:
            self.env['ir.model.access'].call_cache_clearing_methods()
            # self.env['ir.rule'].clear_caches()
        # self.has_group.clear_cache(self)

        self.env['ir.model.access'].call_cache_clearing_methods()
        # self.env['ir.rule'].clear_caches()
        # self.has_group.clear_cache(self)

        return super(ResUsers, self).write(vals)

    @api.onchange('restrict_location', 'restrict_warehouse_operation', 'restrict_stock_warehouse_operation')
    def onchange_restrict_location(self):
        if self.restrict_location == False:
            self.available_location_ids = [(6, 0, [])]
        if self.restrict_warehouse_operation == False:
            self.picking_type_ids = [(6, 0, [])]
        if self.restrict_stock_warehouse_operation == False:
            self.available_warehouse_ids = [(6, 0, [])]
