from odoo import models, fields, api, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    let_guar_adv_pay_id = fields.Many2one('account.account', string="Advance payment letter")
    init_let_gua_id = fields.Many2one('account.account', string="Elementary Letter")
    final_let_guar_id = fields.Many2one('account.account', string="Final Letter")

    let_guar_insurance_id = fields.Many2one('account.account', string="Advance payment insurance account")
    init_let_insurance_id = fields.Many2one('account.account', string="Elementary insurance account")
    final_let_insurance_id = fields.Many2one('account.account', string="Final insurance account")

    def set_values(self):
        """Save field values in ir.config_parameter"""
        res = super().set_values()
        params = self.env['ir.config_parameter'].sudo()

        params.set_param("mm_accounting_customization.let_guar_adv_pay_id", self.let_guar_adv_pay_id.id or False)
        params.set_param("mm_accounting_customization.init_let_gua_id", self.init_let_gua_id.id or False)
        params.set_param("mm_accounting_customization.final_let_guar_id", self.final_let_guar_id.id or False)

        params.set_param("mm_accounting_customization.let_guar_insurance_id", self.let_guar_insurance_id.id or False)
        params.set_param("mm_accounting_customization.init_let_insurance_id", self.init_let_insurance_id.id or False)
        params.set_param("mm_accounting_customization.final_let_insurance_id", self.final_let_insurance_id.id or False)

        return res

    @api.model
    def get_values(self):
        """Retrieve field values from ir.config_parameter"""
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()

        let_guar_adv_pay_id = params.get_param('mm_accounting_customization.let_guar_adv_pay_id', False)
        init_let_gua_id = params.get_param('mm_accounting_customization.init_let_gua_id', False)
        final_let_guar_id = params.get_param('mm_accounting_customization.final_let_guar_id', False)

        let_guar_insurance_id = params.get_param('mm_accounting_customization.let_guar_insurance_id', False)
        init_let_insurance_id = params.get_param('mm_accounting_customization.init_let_insurance_id', False)
        final_let_insurance_id = params.get_param('mm_accounting_customization.final_let_insurance_id', False)

        res.update(
            let_guar_adv_pay_id=self.env['account.account'].browse(int(let_guar_adv_pay_id)) if let_guar_adv_pay_id else False,
            init_let_gua_id=self.env['account.account'].browse(int(init_let_gua_id)) if init_let_gua_id else False,
            final_let_guar_id=self.env['account.account'].browse(int(final_let_guar_id)) if final_let_guar_id else False,

            let_guar_insurance_id=self.env['account.account'].browse(int(let_guar_insurance_id)) if let_guar_insurance_id else False,
            init_let_insurance_id=self.env['account.account'].browse(int(init_let_insurance_id)) if init_let_insurance_id else False,
            final_let_insurance_id=self.env['account.account'].browse(int(final_let_insurance_id)) if final_let_insurance_id else False,
        )

        return res
