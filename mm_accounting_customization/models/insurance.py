# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class mmInsurance(models.Model):
    _name = 'mm.insurance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def unlink(self):
        for loan in self:
            if loan.state not in ('draft', 'cancel'):
                raise UserError(
                    'You cannot delete a Insurance which is not in draft or cancelled state')
        return super(mmInsurance, self).unlink()

    name = fields.Char(string='Reference', copy=False, readonly=True, default=lambda self: self._generate_reference())
    partner_id = fields.Many2one('res.partner', 'Customer')
    journal_id = fields.Many2one('account.journal', string='Payment Journal')
    recovery_journal_id = fields.Many2one('account.journal', string='Recovery Journal', domain=[('type', '=', 'bank')])
    start_date = fields.Date(string="Start Date",)
    end_date = fields.Date(string="End Date")
    insurance_ids = fields.One2many('mm.insurance.line', 'link_id',)
    letter_of_guarantee = fields.Boolean(string='Letter Of Guarantee ?', )
    type = fields.Selection(
        string='Type',
        selection=[('apl', 'Advance payment Insurance'),
                   ('es', 'Elementary Insurance'),
                   ('fs', 'Final Insurance'),
                   ],
        required=False, )

    status = fields.Selection(
        string='Status',
        selection=[('pc', 'Partially covered'),
                   ('fc', 'Fully covered'),
                   ],
        required=False, )

    insurance_type = fields.Selection(
        string='Insurance Type',
        selection=[('check', 'Check'),
                   ('other', 'Other'),
                   ],
        required=False, )
    # debit_account_id = fields.Many2one('account.account', 'Debit Account')
    # credit_account_id = fields.Many2one('account.account', 'Credit Account')
    state = fields.Selection(
        string='Status',
        selection=[('draft', 'Draft'),
                   ('approve', 'Approved'),
                   ('recovery', 'Recovery'),
                   ('recovery_request', 'Recovery Request'),
                   ('insurance_confiscation', 'Insurance Confiscation'),
                   ('cancel', 'Cancel'),
                   ], default='draft',
        required=False, )
    move_id = fields.Many2one('account.move', 'Journal Entry')
    move_ids = fields.Many2many('account.move', 'move_ids11', 'move_ids111', 'move_ids1111', 'Journal Entry')
    is_insurance_confiscation = fields.Boolean()
    is_recovery = fields.Boolean()
    date = fields.Date(string='Date')
    writeoff_account_id = fields.Many2one('account.account', string="Difference Account", copy=False,)
    writeoff_amount = fields.Float()
    accounting_date = fields.Date("Account Date", tracking=True)
    letter_amount = fields.Float(string='Letter Amount', compute='_compute_get_letter_amount')
    notes = fields.Text(string="Notes",)
    is_group_access_seq = fields.Boolean(compute='_compute_access_seq')
    
    @api.model
    def _generate_reference(self):
        return self.env['ir.sequence'].next_by_code('mm.insurance') or 'INSU00001'
    def _compute_access_seq(self):
        for rec in self:
            rec.is_group_access_seq = False
            if self.env.user.has_groups('mm_accounting_customization.group_access_seq'):
                rec.is_group_access_seq = True

    def _compute_get_letter_amount(self):
        for rec in self:
            account_account = 0
            amount = 0
            if rec.type == 'apl':
                let_guar_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.let_guar_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', let_guar_insurance_id)])

            if rec.type == 'es':
                init_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', init_let_insurance_id)])

            if rec.type == 'fs':
                final_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.final_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_insurance_id)])
            for line in rec.insurance_ids:
                if account_account.id == line.account_id.id:
                    amount += line.debit
                    amount += line.credit
            rec.letter_amount = amount

    @api.onchange('journal_id', 'name', 'partner_id')
    def _onchange_journal_id(self):
        currency = self.env.ref('base.EGP')
        return {'domain': {'journal_id': ['|', ('currency_id', '=', currency.id), ('currency_id', '=', False), ('type', 'in', ['bank', 'cash'])]}}

    @api.onchange('type', 'writeoff_account_id')
    def _onchange_writeoff_account_id(self):
        if self.writeoff_account_id and self.type and self.partner_id:
            self.insurance_ids = [(5, 0, 0)]
            if self.type == 'apl':
                line1 = [{
                    'account_id': self.partner_id.property_account_receivable_id.id,
                    'credit': self.writeoff_amount,
                }]

                line2 = [{
                    'account_id': self.writeoff_account_id.id,
                    'debit': self.writeoff_amount,

                }]

                line_ids = line1 + line2
                self.insurance_ids = [(0, 0, x) for x in line_ids]

            if self.type == 'es':
                line1 = [{
                    'account_id': self.partner_id.property_account_receivable_id.id,
                    'credit': self.writeoff_amount,
                }]

                line2 = [{
                    'account_id': self.writeoff_account_id.id,
                    'debit': self.writeoff_amount,

                }]
                line_ids = line1 + line2
                self.insurance_ids = [(0, 0, x) for x in line_ids]

            if self.type == 'fs':
                line1 = [{
                    'account_id': self.partner_id.property_account_receivable_id.id,
                    'credit': self.writeoff_amount,
                }]

                line2 = [{
                    'account_id': self.writeoff_account_id.id,
                    'debit': self.writeoff_amount,

                }]

                line_ids = line1 + line2
                self.insurance_ids = [(0, 0, x) for x in line_ids]

    @api.onchange('type', 'journal_id')
    def _onchange_type(self):
        if self.journal_id and self.type:
            self.insurance_ids = [(5, 0, 0)]
            if self.type == 'apl':
                let_guar_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.let_guar_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', let_guar_insurance_id)])

                line1 = [{
                    'account_id': account_account.id,
                }]
                line2 = [{
                    'account_id': self.journal_id.default_account_id.id,
                }]
                line_ids = line1 + line2
                self.insurance_ids = [(0, 0, x) for x in line_ids]

            if self.type == 'es':
                init_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', init_let_insurance_id)])

                line1 = [{
                    'account_id': account_account.id,
                }]
                line2 = [{
                    'account_id': self.journal_id.default_account_id.id,
                }]
                line_ids = line1 + line2
                self.insurance_ids = [(0, 0, x) for x in line_ids]

            if self.type == 'fs':
                final_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.final_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_insurance_id)])

                line1 = [{
                    'account_id': account_account.id,
                }]

                line2 = [{
                    'account_id': self.journal_id.default_account_id.id,
                }]
                line_ids = line1 + line2
                self.insurance_ids = [(0, 0, x) for x in line_ids]

    def action_approve(self):
        self.state = 'approve'
        self.action_create_journal_entries()

    def action_draft(self):
        self.state = 'draft'

    def action_recovery_request(self):
        self.state = 'recovery_request'

    def action_create_journal_entries(self):
        for le in self:
            vals = {
                'ref': le.name,
                'journal_id': le.journal_id.id,
                'date': le.date,
            }
            entry = self.env['account.move'].create(vals)
            if entry:
                lst = []
                for line in le.insurance_ids:
                    if line.credit == 0:
                        val = (0, 0, {
                            'account_id': line.account_id.id,
                            'partner_id': le.partner_id.id,
                            'debit': line.debit,
                            'credit': line.credit,
                        })
                        lst.append(val)
                    if line.debit == 0:
                        val = (0, 0, {
                            'account_id': line.account_id.id,
                            'partner_id': le.partner_id.id,
                            'debit': line.debit,
                            'credit': line.credit,
                        })
                        lst.append(val)
                entry.line_ids = lst
                entry.state = 'posted'
                le.move_ids = [(4, entry.id)]

    def action_cancel(self):
        self.state = 'cancel'

    def action_insurance_confiscation(self):
        for le in self:
            account_account = 0
            if self.type == 'apl':
                let_guar_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.let_guar_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', let_guar_insurance_id)])

            if self.type == 'es':
                init_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', init_let_insurance_id)])

            if self.type == 'fs':
                final_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.final_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_insurance_id)])

            vals = {
                'ref': le.name,
                'journal_id': le.journal_id.id,
                'date': le.date,
            }
            entry = self.env['account.move'].create(vals)
            if account_account and self.type:
                if entry:
                    lst = []
                    debit = 0
                    credit = 0
                    for line in le.insurance_ids:
                        debit += line.debit
                        credit += line.credit
                    val = (0, 0, {
                        'account_id': account_account.id,
                        'debit': 0.00,
                        'credit': credit,
                    })
                    lst.append(val)
                    val = (0, 0, {
                        'account_id': le.journal_id.expense_account_id.id,
                        'debit': debit,
                        'credit': 0.00,
                    })
                    lst.append(val)
                    entry.line_ids = lst
                    le.is_insurance_confiscation = True
                    le.move_ids = [(4, entry.id)]
                    le.state = 'insurance_confiscation'
                    return {
                        'name': 'Journal Entries',
                        'domain': [('id', '=', entry.id)],
                        'view_type': 'form',
                        'res_model': 'account.move',
                        'view_id': False,
                        'view_mode': 'list,form',
                        'type': 'ir.actions.act_window'
                    }

    journal_entries_count = fields.Integer(compute='get_journal_entries_count')

    # @api.onchange('insurance_ids')
    # def onchange_insurance_ids(self):
    #     for line in self.insurance_ids:
    #         if not line.credit_account_id:
    #             line.credit_account_id = self.journal_id.default_account_id.id

    def open_journal_entries(self):
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.move_ids.ids)],
        }

    def get_journal_entries_count(self):
        count = self.env['account.move'].search_count([('id', 'in', self.move_ids.ids)])
        self.journal_entries_count = count

    def action_recovery_create_journal_entries(self):
        for le in self:
            account_account = 0
            if self.type == 'apl':
                let_guar_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param(
                    'mm_accounting_customization.let_guar_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', let_guar_insurance_id)])

            if self.type == 'es':
                init_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param(
                    'mm_accounting_customization.init_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', init_let_insurance_id)])

            if self.type == 'fs':
                final_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param(
                    'mm_accounting_customization.final_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_insurance_id)])

            pdc_treussury_id = int(self.env['ir.config_parameter'].sudo().get_param(
                'sh_pdc.pdc_treussury'))
            pdc_treussury = self.env['account.account'].search([('id', '=', pdc_treussury_id)])

            vals = {
                'ref': le.name,
                'journal_id': le.recovery_journal_id.id,
                'date': le.date,
            }
            entry = self.env['account.move'].create(vals)
            if account_account and self.type:
                if entry:
                    lst = []
                    debit = 0
                    credit = 0
                    for line in le.insurance_ids:
                        debit += line.debit
                        credit += line.credit
                    val = (0, 0, {
                        'account_id': account_account.id,
                        'debit': 0.00,
                        'credit': credit,
                    })
                    lst.append(val)
                    val = (0, 0, {
                        'account_id': pdc_treussury.id,
                        'debit': debit,
                        'credit': 0.00,
                    })
                    lst.append(val)
                    entry.line_ids = lst
                    print("lst", lst)
                    print("line_ids", entry.line_ids)
                    le.move_ids = [(4, entry.id)]
                    le.is_recovery = True
                    le.state = 'recovery'
                    return {
                        'name': 'Journal Entries',
                        'domain': [('id', '=', entry.id)],
                        'view_type': 'form',
                        'res_model': 'account.move',
                        'view_id': False,
                        'view_mode': 'list,form',
                        'type': 'ir.actions.act_window'
                    }

    def action_recovery(self):
        for le in self:
            account_account = 0
            if self.type == 'apl':
                let_guar_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param(
                    'mm_accounting_customization.let_guar_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', let_guar_insurance_id)])

            if self.type == 'es':
                init_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param(
                    'mm_accounting_customization.init_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', init_let_insurance_id)])

            if self.type == 'fs':
                final_let_insurance_id = int(self.env['ir.config_parameter'].sudo().get_param(
                    'mm_accounting_customization.final_let_insurance_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_insurance_id)])

            is_done = False
            is_deposited = False
            for line in le.pdc_payment_ids:
                if line.state == 'done':
                    is_done = True
                elif line.state == 'deposited':
                    is_deposited = True

            if le.recovery_journal_id:
                if le.payment_type == 'cheque':
                    if is_done:
                        vals = {
                            'ref': le.name,
                            'journal_id': le.recovery_journal_id.id,
                            'date': le.accounting_date,
                        }
                        entry = self.env['account.move'].create(vals)
                        if account_account and self.type:
                            if entry:
                                lst = []
                                debit = 0
                                credit = 0
                                for line in le.insurance_ids:
                                    debit += line.debit
                                    credit += line.credit
                                val = (0, 0, {
                                    'account_id': account_account.id,
                                    'debit': 0.00,
                                    'credit': credit,
                                })
                                lst.append(val)
                                val = (0, 0, {
                                    'account_id': le.recovery_journal_id.default_account_id.id,
                                    'debit': debit,
                                    'credit': 0.00,
                                })
                                lst.append(val)
                                entry.line_ids = lst
                                le.move_ids = [(4, entry.id)]
                                le.is_recovery = True
                                le.state = 'recovery'
                                return {
                                    'name': 'Journal Entries',
                                    'domain': [('id', '=', entry.id)],
                                    'view_type': 'form',
                                    'res_model': 'account.move',
                                    'view_id': False,
                                    'view_mode': 'list,form',
                                    'type': 'ir.actions.act_window'
                                }
                    elif is_deposited:
                        vals = {
                            'ref': le.name,
                            'journal_id': le.recovery_journal_id.id,
                            'date': le.date,
                        }
                        entry = self.env['account.move'].create(vals)
                        if account_account and self.type:
                            if entry:
                                lst = []
                                for line in le.insurance_ids:
                                    if line.credit == 0:
                                        val = (0, 0, {
                                            'account_id': account_account.id,
                                            'debit': line.credit,
                                            'credit': line.debit,
                                        })
                                        lst.append(val)
                                    if line.debit == 0:
                                        val = (0, 0, {
                                            'account_id': le.recovery_journal_id.pay_acc.id,
                                            'debit': line.credit,
                                            'credit': line.debit,
                                        })
                                        lst.append(val)
                                entry.line_ids = lst
                                le.move_ids = [(4, entry.id)]
                                le.is_recovery = True
                                le.state = 'recovery'
                                return {
                                    'name': 'Journal Entries',
                                    'domain': [('id', '=', entry.id)],
                                    'view_type': 'form',
                                    'res_model': 'account.move',
                                    'view_id': False,
                                    'view_mode': 'list,form',
                                    'type': 'ir.actions.act_window'
                                }
                else:
                    vals = {
                        'ref': le.name,
                        'journal_id': le.recovery_journal_id.id,
                        'date': le.accounting_date,
                    }
                    entry = self.env['account.move'].create(vals)
                    if account_account and self.type:
                        if entry:
                            lst = []
                            debit = 0
                            credit = 0
                            for line in le.insurance_ids:
                                debit += line.debit
                                credit += line.credit
                            val = (0, 0, {
                                'account_id': account_account.id,
                                'debit': 0.00,
                                'credit': credit,
                            })
                            lst.append(val)
                            val = (0, 0, {
                                'account_id': le.recovery_journal_id.default_account_id.id,
                                'debit': debit,
                                'credit': 0.00,
                            })
                            lst.append(val)
                            entry.line_ids = lst
                            le.move_ids = [(4, entry.id)]
                            le.is_recovery = True
                            le.state = 'recovery'
                            return {
                                'name': 'Journal Entries',
                                'domain': [('id', '=', entry.id)],
                                'view_type': 'form',
                                'res_model': 'account.move',
                                'view_id': False,
                                'view_mode': 'list,form',
                                'type': 'ir.actions.act_window'
                            }

            else:
                raise ValidationError(_('Add Recovery Journal'))


class InsuranceLine(models.Model):
    _name = 'mm.insurance.line'

    link_id = fields.Many2one('mm.insurance')
    account_id = fields.Many2one('account.account', 'Account')
    debit = fields.Float(string='Debit')
    credit = fields.Float(string='Credit')