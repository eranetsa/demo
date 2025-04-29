# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class mmRampingWizard(models.TransientModel):
    _name = "mm.ramping.wizard"

    accounting_date = fields.Date(string='Accounting Date', default=fields.Date.context_today)
    start_date = fields.Date(string="Start Date",)
    end_date = fields.Date(string="End Date")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    letter_of_guarantee_id = fields.Many2one('mm.letter.of.guarantee')
    expense_value = fields.Monetary(string='Expense Value', )
    ramping_value = fields.Monetary(string='Ramping Value', )
    ramping = fields.Boolean(string='Ramping')
    inv_ramping = fields.Boolean()
    status = fields.Selection(
        string='Status',
        selection=[('pc', 'Partially covered'),
                   ('fc', 'Fully covered'),
                   ],
        required=False, related='letter_of_guarantee_id.status')

    @api.onchange('letter_of_guarantee_id')
    def _onchange_letter_of_guarantee_id(self):
        if self.letter_of_guarantee_id.is_ramping:
            self.inv_ramping = True
        else:
            self.inv_ramping = False

    def action_ramping(self):
        if self.letter_of_guarantee_id.type == 'apl':
            let_guar_adv_pay_id = int(
                self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.let_guar_adv_pay_id'))
            account_account = self.env['account.account'].search([('id', '=', let_guar_adv_pay_id)])

        if self.letter_of_guarantee_id.type == 'es':
            init_let_gua_id = int(
                self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_gua_id'))
            account_account = self.env['account.account'].search([('id', '=', init_let_gua_id)])

        if self.letter_of_guarantee_id.type == 'fs':
            final_let_guar_id = int(
                self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.final_let_guar_id'))
            account_account = self.env['account.account'].search([('id', '=', final_let_guar_id)])

        vals = {
            'ref': self.letter_of_guarantee_id.name,
            'journal_id': self.letter_of_guarantee_id.journal_id.id,
            'date': self.accounting_date,
            'notes': self.letter_of_guarantee_id.notes,

        }
        entry = self.env['account.move'].create(vals)
        if entry:
            lst = []
            # for line in self.letter_of_guarantee_id.letter_of_guarantee_ids:
            val = (0, 0, {
                'account_id': self.letter_of_guarantee_id.journal_id.expense_account_id.id,
                'debit': self.expense_value,
                'credit': 0.00,
            })
            lst.append(val)
            val = (0, 0, {
                'account_id': self.letter_of_guarantee_id.journal_id.insurance_account_id.id,
                'debit': self.ramping_value,
                'credit': 0.00,
            })
            lst.append(val)
            val = (0, 0, {
                'account_id': self.letter_of_guarantee_id.journal_id.default_account_id.id,
                'debit': 0.00,
                'credit': self.expense_value + self.ramping_value,
            })
            lst.append(val)

            entry.line_ids = lst
            lines = []
            val2 = {
                'link_id': self.letter_of_guarantee_id.id,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'ramping': self.ramping,
                'status': 'fc',
                'move_id': entry.id,
            }
            lines.append((0, 0, val2))
            self.letter_of_guarantee_id.extension_ids = lines
            self.letter_of_guarantee_id.is_ramping = True
            self.letter_of_guarantee_id.state = 'ramping'
            self.letter_of_guarantee_id.remaining_value_wiz += self.ramping_value
            self.letter_of_guarantee_id.move_ids = [(4, entry.id)]
            entry.letter_of_guarantee_id = self.letter_of_guarantee_id.id
            return {
                'name': 'Journal Entries',
                'domain': [('id', '=', entry.id)],
                'view_type': 'form',
                'res_model': 'account.move',
                'view_id': False,
                'view_mode': 'list,form',
                'type': 'ir.actions.act_window'
            }