# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class mmCashGuaranteeWizard(models.TransientModel):
    _name = "mm.insurance.reduction.wizard"

    letter_of_guarantee_id = fields.Many2one('mm.letter.of.guarantee')
    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', '=', 'bank')])
    insurance_amount = fields.Float(string='Insurance Amount')
    expense_amount = fields.Float(string='Expense Amount')

    def action_insurance_reduction(self):
        var = self.letter_of_guarantee_id.remaining_value - self.insurance_amount
        bank_amount = self.insurance_amount - self.expense_amount
        if var >= 0:
            vals = {
                'ref': self.letter_of_guarantee_id.name,
                'journal_id': self.journal_id.id,
                'date': self.letter_of_guarantee_id.date,
                'notes': self.letter_of_guarantee_id.notes,

            }
            entry = self.env['account.move'].create(vals)
            if entry:
                lst = []
                val = (0, 0, {
                    'account_id': self.journal_id.insurance_account_id.id,
                    'debit': 0.00,
                    'credit': self.insurance_amount,
                })
                lst.append(val)
                val = (0, 0, {
                    'account_id': self.journal_id.expense_account_id.id,
                    'debit': self.expense_amount,
                    'credit': 0.00,
                })
                lst.append(val)
                val = (0, 0, {
                    'account_id': self.journal_id.default_account_id.id,
                    'debit': bank_amount,
                    'credit': 0.00,
                })
                lst.append(val)
                entry.line_ids = lst
                self.letter_of_guarantee_id.move_ids = [(4, entry.id)]
                self.letter_of_guarantee_id.reduced += self.insurance_amount
                entry.letter_of_guarantee_id = self.letter_of_guarantee_id.id
        else:
            raise ValidationError(_('Insurance Amount < 0'))
