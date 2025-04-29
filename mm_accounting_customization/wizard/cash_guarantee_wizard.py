# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class mmCashGuaranteeWizard(models.TransientModel):
    _name = "mm.cash.guarantee.wizard"

    name = fields.Char(string='Reference')
    partner_id = fields.Many2one('res.partner', 'Customer')
    journal_id = fields.Many2one('account.journal', string='Payment Journal',)
    start_date = fields.Date(string="Start Date", )
    end_date = fields.Date(string="End Date")
    type = fields.Selection(
        string='Type',
        selection=[('apl', 'Advance payment Insurance'),
                   ('es', 'Elementary Insurance'),
                   ('fs', 'Final Insurance'),
                   ],
        required=False, default='fs')

    status = fields.Selection(
        string='Status',
        selection=[('pc', 'Partially covered'),
                   ('fc', 'Fully covered'),
                   ],
        required=False, )
    date = fields.Date(string='Date')
    move_id = fields.Many2one('account.move', 'Journal Entry')
    writeoff_account_id = fields.Many2one('account.account', string="Difference Account", copy=False,)
    writeoff_amount = fields.Float()
    test_amount = fields.Float()
    mm_payment_type = fields.Selection(string='Payment Type',
                                    selection=[
                                        ('normal', 'Normal'),
                                        ('cheque', 'Cheque'),
                                    ],
                                    required=False, default='normal')
    notes = fields.Text(string="Notes",)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        final_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'mm_accounting_customization.final_let_insurance_id'))
        account_account = self.env['account.account'].search([('id', '=', final_let_insurance_id)])
        self.writeoff_account_id = account_account.id

        journal = self.env['account.journal'].search([('code', '=', "MISC")], limit=1)
        self.journal_id = journal.id

    @api.onchange('move_id')
    def onchange_move_id(self):
        if self.move_id:
            self.writeoff_amount = self.move_id.amount_residual
            self.test_amount = self.move_id.amount_residual

    @api.onchange('writeoff_amount')
    def onchange_writeoff_amount(self):
        if self.writeoff_amount > self.test_amount:
            raise ValidationError(_("Writeoff Amount greater than Amount Due"))

    def action_cash_guarantee(self):
        vals = {
            'name': self.name,
            'partner_id': self.partner_id.id,
            'move_id': self.move_id.id,

            'writeoff_account_id': self.writeoff_account_id.id,
            'writeoff_amount': self.writeoff_amount,
            'payment_type': self.mm_payment_type,

            'journal_id': self.journal_id.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'type': self.type,
            'date': self.date,
            'notes': self.notes,
        }
        insurance = self.env['mm.insurance'].create(vals)
        insurance.state = 'approve'
        insurance._onchange_writeoff_account_id()
        self.action_create_journal_entries()
        # self.move_id.payment_state = 'paid'
        self.move_id.insurance_ids = [(4, insurance.id)]

    def action_create_journal_entries(self):
        for le in self:
            vals = {
                'ref': le.name,
                'journal_id': le.journal_id.id,
                'date': le.date,
            }
            entry = self.env['account.move'].create(vals)
            if entry:
                final_let_insurance_id = int(
                    self.env['ir.config_parameter'].sudo().get_param(
                        'mm_accounting_customization.final_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_insurance_id)])
                lst = []
                val = (0, 0, {
                    'account_id': account_account.id,
                    'debit': self.writeoff_amount,
                })
                lst.append(val)
                val = (0, 0, {
                    'account_id': self.partner_id.property_account_receivable_id.id,
                    'partner_id': self.partner_id.id,
                    'credit': self.writeoff_amount,

                })
                lst.append(val)
                entry.line_ids = lst
                entry.state = 'posted'
                # le.move_ids = [(4, entry.id)]
    #
    # def payments_create(self):
    #     # invoice_object = self
    #
    #     # cliente = self.env['res.partner'].search([('id', '=', self.partner_id.id)])
    #     # ctx = dict(
    #     #     active_ids=invoice_object.ids,  # Use ids and not id (it has to be a list)
    #     #     active_model='account.move',
    #     # )
    #     # Payment = self.env['account.payment']
    #
    #     vals = {
    #         'payment_type': 'inbound',
    #         'partner_type': 'customer',
    #         'partner_id': self.partner_id.id,
    #         'payment_method_line_id': 1,
    #         'amount': self.writeoff_amount,
    #         'currency_id': self.move_id.currency_id.id,
    #         'journal_id': self.journal_id.id,
    #     }
    #     # payment.post()
    #
    #     payment_id = self.env['account.payment'].create(vals)
    #     # wizard = self.env['account.payment.register'].with_context(ctx).create(values)
    #     # wizard._create_payments()
    #
    # def create_payment_new(self):
    #     ctx = {'active_model': 'account.move', 'active_ids': self.ids, 'journal_id': self.journal_id.id}
    #     payment_register = self.env['account.payment.register'].with_context(**ctx).create({
    #         'amount': self.writeoff_amount,
    #         'currency_id': self.move_id.currency_id.id,
    #     })
    #     payment_register.action_create_payments()