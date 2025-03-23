# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class LetterOfGuarantee(models.Model):
    _name = 'mm.letter.of.guarantee'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', copy=False, readonly=True, default=lambda self: self._generate_reference())
    partner_id = fields.Many2one('res.partner', 'Customer')
    journal_id = fields.Many2one('account.journal', string='Payment Journal')
    insurance_account_id = fields.Many2one('account.account', 'Insurance Account', related='journal_id.insurance_account_id')
    start_date = fields.Date(string="Start Date",)
    end_date = fields.Date(string="End Date")
    letter_of_guarantee_ids = fields.One2many('mm.letter.of.guarantee.line', 'link_id',)
    extension_ids = fields.One2many('mm.extension.line', 'link_id',)
    letter_of_guarantee = fields.Boolean(string='Letter Of Guarantee ?', )
    # active_id = fields.Many2one('mm.extension.wizard', string="Active ID")
    type = fields.Selection(
        string='Type',
        selection=[('apl', 'Advance payment letter'),
                   ('es', 'Elementary Letter'),
                   ('fs', 'Final Letter'),
                   ],
        required=False, )

    status = fields.Selection(
        string='Status',
        selection=[('pc', 'Partially covered'),
                   ('fc', 'Fully covered'),
                   ],
        required=False, )

    state = fields.Selection(
        string='Status',
        selection=[('draft', 'Draft'),
                   ('approve', 'Approved'),
                   ('recovery', 'Recovery'),
                   ('extension', 'Extension'),
                   ('ramping', 'Ramping'),
                   ('seepage', 'Seepage'),
                   ('cancel', 'Cancel'),

                   ], default='draft',
        required=False, )
    move_id = fields.Many2one('account.move', 'Journal Entry')
    move_ids = fields.Many2many('account.move', 'move_ids01', 'move_ids001', 'move_ids0001', 'Journal Entry')
    date = fields.Date(string='Date')
    is_extension = fields.Boolean()
    is_recovery = fields.Boolean()
    is_seepage = fields.Boolean()
    run_compute = fields.Boolean(compute='_compute_set_move_ids')
    final_insurance_account = fields.Float(compute='_compute_final_insurance_account', string='Final Insurance Account')
    reduced = fields.Float(string='Reduced')
    remaining_value = fields.Float(string='Final Insurance Amount', compute='_compute_remaining_value')
    remaining_value_wiz = fields.Float()
    recovery_expense = fields.Float(string='Recovery Expense')
    letter_amount = fields.Float(string='Letter Amount', compute='_compute_get_letter_amount')
    is_ramping = fields.Boolean()
    notes = fields.Text(string="Notes",)
    is_group_access_seq = fields.Boolean(compute='_compute_access_seq')
    @api.model
    def _generate_reference(self):
        return self.env['ir.sequence'].next_by_code('mm.letter.of.guarantee') or 'LOG00001'
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
                let_guar_adv_pay_id = int(
                    self.env['ir.config_parameter'].sudo().get_param(
                        'mm_accounting_customization.let_guar_adv_pay_id'))
                account_account = self.env['account.account'].search([('id', '=', let_guar_adv_pay_id)])

            if rec.type == 'es':
                init_let_gua_id = int(
                    self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_gua_id'))
                account_account = self.env['account.account'].search([('id', '=', init_let_gua_id)])

            if rec.type == 'fs':
                final_let_guar_id = int(
                    self.env['ir.config_parameter'].sudo().get_param(
                        'mm_accounting_customization.final_let_guar_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_guar_id)])
            for line in rec.letter_of_guarantee_ids:
                if account_account.id == line.account_id.id:
                    amount += line.debit
                    amount += line.credit
            rec.letter_amount = amount

    def unlink(self):
        for loan in self:
            if loan.state not in ('draft', 'cancel'):
                raise UserError('You cannot delete a Letter Of Guarantee which is not in draft or cancelled state')
        return super(LetterOfGuarantee, self).unlink()

    def _compute_remaining_value(self):
        for rec in self:
            rec.remaining_value = (rec.final_insurance_account - rec.reduced) + rec.remaining_value_wiz

    def _compute_final_insurance_account(self):
        for rec in self:
            rec.final_insurance_account = 0
            for line in rec.letter_of_guarantee_ids:
                if rec.journal_id.insurance_account_id.id == line.account_id.id:
                    if line.debit:
                        rec.final_insurance_account += line.debit

            for ext in rec.extension_ids:
                if ext.ramping:
                    if ext.move_id.state != 'cancel':
                        for lin in ext.move_id.invoice_line_ids:
                            if rec.journal_id.insurance_account_id.id == lin.account_id.id:
                                if lin.debit:
                                    rec.final_insurance_account += lin.debit


    @api.onchange('journal_id', 'name', 'partner_id')
    def _onchange_journal_id(self):
        # raise UserError("ddddd")
        currency = self.env.ref('base.EGP')
        return {'domain': {'journal_id': ['|', ('currency_id', '=', currency.id), ('currency_id', '=', False), ('type', '=', 'bank')]}}

    @api.onchange('type', 'status', 'journal_id')
    def _onchange_type_status(self):
        # raise UserError("2222")
        if self.journal_id and self.status and self.type:
            self.letter_of_guarantee_ids = [(5, 0, 0)]
            if self.status == 'fc':
                if self.type == 'apl':
                    let_guar_adv_pay_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.let_guar_adv_pay_id'))
                    account_account = self.env['account.account'].search([('id', '=', let_guar_adv_pay_id)])

                    line1 = [{
                        'account_id': account_account.id,
                    }]

                    line2 = [{
                        'account_id': self.journal_id.expense_account_id.id,
                    }]
                    line3 = [{
                        'account_id': self.journal_id.default_account_id.id,
                    }]
                    line_ids = line1 + line2 + line3
                    self.letter_of_guarantee_ids = [(0, 0, x) for x in line_ids]

                if self.type == 'es':
                    init_let_gua_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_gua_id'))
                    account_account = self.env['account.account'].search([('id', '=', init_let_gua_id)])

                    line1 = [{
                        'account_id': account_account.id,
                    }]

                    line2 = [{
                        'account_id': self.journal_id.expense_account_id.id,
                    }]
                    line3 = [{
                        'account_id': self.journal_id.default_account_id.id,
                    }]
                    line_ids = line1 + line2 + line3
                    self.letter_of_guarantee_ids = [(0, 0, x) for x in line_ids]

                if self.type == 'fs':
                    final_let_guar_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.final_let_guar_id'))
                    account_account = self.env['account.account'].search([('id', '=', final_let_guar_id)])

                    line1 = [{
                        'account_id': account_account.id,
                    }]

                    line2 = [{
                        'account_id': self.journal_id.expense_account_id.id,
                    }]
                    line3 = [{
                        'account_id': self.journal_id.default_account_id.id,
                    }]
                    line_ids = line1 + line2 + line3
                    self.letter_of_guarantee_ids = [(0, 0, x) for x in line_ids]

            elif self.status == 'pc':
                if self.type == 'apl':
                    let_guar_adv_pay_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.let_guar_adv_pay_id'))
                    account_account = self.env['account.account'].search([('id', '=', let_guar_adv_pay_id)])

                    line1 = [{
                        'account_id': account_account.id,
                    }]

                    line2 = [{
                        'account_id': self.journal_id.expense_account_id.id,
                    }]
                    line3 = [{
                        'account_id': self.journal_id.insurance_account_id.id,
                    }]

                    line4 = [{
                        'account_id': self.journal_id.default_account_id.id,
                    }]

                    line5 = [{
                        'account_id': self.journal_id.bank_facility_account_id.id,
                    }]
                    line_ids = line1 + line2 + line3 + line4 + line5
                    self.letter_of_guarantee_ids = [(0, 0, x) for x in line_ids]

                if self.type == 'es':
                    init_let_gua_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_gua_id'))
                    account_account = self.env['account.account'].search([('id', '=', init_let_gua_id)])

                    line1 = [{
                        'account_id': account_account.id,
                    }]

                    line2 = [{
                        'account_id': self.journal_id.expense_account_id.id,
                    }]
                    line3 = [{
                        'account_id': self.journal_id.insurance_account_id.id,
                    }]

                    line4 = [{
                        'account_id': self.journal_id.default_account_id.id,
                    }]

                    line5 = [{
                        'account_id': self.journal_id.bank_facility_account_id.id,
                    }]
                    line_ids = line1 + line2 + line3 + line4 + line5
                    self.letter_of_guarantee_ids = [(0, 0, x) for x in line_ids]

                if self.type == 'fs':
                    final_let_guar_id = int(self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.final_let_guar_id'))
                    account_account = self.env['account.account'].search([('id', '=', final_let_guar_id)])
                    line1 = [{
                        'account_id': account_account.id,
                    }]

                    line2 = [{
                        'account_id': self.journal_id.expense_account_id.id,
                    }]
                    line3 = [{
                        'account_id': self.journal_id.insurance_account_id.id,
                    }]

                    line4 = [{
                        'account_id': self.journal_id.default_account_id.id,
                    }]

                    line5 = [{
                        'account_id': self.journal_id.bank_facility_account_id.id,
                    }]
                    line_ids = line1 + line2 + line3 + line4 + line5
                    self.letter_of_guarantee_ids = [(0, 0, x) for x in line_ids]


    def action_approve(self):
        self.state = 'approve'
        self.action_create_journal_entries()

    def action_draft(self):
        self.state = 'draft'

    def action_cancel(self):
        self.state = 'cancel'

    def _compute_set_move_ids(self):
        for rec in self:
            rec.run_compute = False
            if rec.move_id:
                rec.move_ids = [(4, rec.move_id.id)]

    def action_create_journal_entries(self):
        for le in self:
            vals = {
                'ref': le.name,
                'journal_id': le.journal_id.id,
                'date': le.date,
                'notes': le.notes,
            }
            entry = self.env['account.move'].create(vals)
            if entry:
                lst = []
                for line in le.letter_of_guarantee_ids:
                    if line.credit == 0:
                        val = (0, 0, {
                            'account_id': line.account_id.id,
                            'debit': line.debit,
                            'credit': line.credit,
                        })
                        lst.append(val)
                    if line.debit == 0:
                        val = (0, 0, {
                            'account_id': line.account_id.id,
                            'debit': line.debit,
                            'credit': line.credit,
                        })
                        lst.append(val)
                entry.line_ids = lst
                entry.state = 'posted'
                le.move_ids = [(4, entry.id)]

    def action_insurance_reduction(self):
        for rec in self:
            if rec.remaining_value > 0:
                self.ensure_one()
                view = self.env.ref('mm_accounting_customization.mm_insurance_reduction_wizard_from_view')
                return {
                    'name': _('Insurance Reduction'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'mm.insurance.reduction.wizard',
                    'views': [(view.id, 'form')],
                    'view_id': view.id,
                    'target': 'new',
                    'context': dict(self.env.context, default_journal_id=self.journal_id.id, default_letter_of_guarantee_id=self.id),
                }
            else:
                raise ValidationError(_('Remaining value Final Insurance Account <= 0'))

    def action_recovery(self):
        for le in self:
            if self.status == 'pc':
                vals = {
                    'ref': le.name,
                    'journal_id': le.journal_id.id,
                    'date': fields.Date.today(),
                    'notes': le.notes,

                }
                entry = self.env['account.move'].create(vals)
                if entry:
                    lst = []
                    for line in le.letter_of_guarantee_ids:
                        var = self.remaining_value - self.recovery_expense
                        if self.journal_id.default_account_id.id == line.account_id.id:
                            if var > 0:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': var,
                                    'credit': 0,
                                })
                                lst.append(val)
                            if var < 0:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': 0,
                                    'credit': -var,
                                })
                                lst.append(val)
                        else:
                            if line.debit == 0:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': line.credit,
                                    'credit': line.debit,
                                })
                                lst.append(val)
                            if line.credit == 0:
                                if self.journal_id.insurance_account_id.id == line.account_id.id:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': 0,
                                        'credit': self.remaining_value,
                                    })
                                    lst.append(val)
                                elif self.journal_id.expense_account_id.id == line.account_id.id:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': self.recovery_expense,
                                        'credit': 0,
                                    })
                                    lst.append(val)
                                else:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': line.credit,
                                        'credit': line.debit,
                                    })
                                    lst.append(val)

                    print("liist", lst)

                    entry.line_ids = lst
                    le.is_recovery = True
                    le.move_ids = [(4, entry.id)]
                    entry.letter_of_guarantee_id = le.id

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
            elif self.status == 'fc':
                account_account = 0
                amount = 0
                if self.type == 'apl':
                    let_guar_adv_pay_id = int(
                        self.env['ir.config_parameter'].sudo().get_param(
                            'mm_accounting_customization.let_guar_adv_pay_id'))
                    account_account = self.env['account.account'].search([('id', '=', let_guar_adv_pay_id)])

                if self.type == 'es':
                    init_let_gua_id = int(
                        self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_gua_id'))
                    account_account = self.env['account.account'].search([('id', '=', init_let_gua_id)])

                if self.type == 'fs':
                    final_let_guar_id = int(
                        self.env['ir.config_parameter'].sudo().get_param(
                            'mm_accounting_customization.final_let_guar_id'))
                    account_account = self.env['account.account'].search([('id', '=', final_let_guar_id)])

                vals = {
                    'ref': le.name,
                    'journal_id': le.journal_id.id,
                    'date': fields.Date.today(),
                    'notes': le.notes,
                }
                entry = self.env['account.move'].create(vals)
                if entry:
                    lst = []
                    for line in le.letter_of_guarantee_ids:
                        if account_account.id == line.account_id.id:
                            amount += line.debit
                    var = amount - self.recovery_expense
                    for line in le.letter_of_guarantee_ids:
                        if line.debit == 0:
                            if self.journal_id.default_account_id.id == line.account_id.id:
                                if var > 0:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': var,
                                        'credit': 0,
                                    })
                                    lst.append(val)
                                if var < 0:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': 0,
                                        'credit': -var,
                                    })
                                    lst.append(val)

                        if line.credit == 0:
                            if account_account.id == line.account_id.id:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': line.credit,
                                    'credit': line.debit,
                                })
                                lst.append(val)
                            elif self.journal_id.expense_account_id.id == line.account_id.id:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': self.recovery_expense,
                                    'credit': 0,
                                })
                                lst.append(val)
                    entry.line_ids = lst
                    le.is_recovery = True
                    le.move_ids = [(4, entry.id)]
                    entry.letter_of_guarantee_id = le.id
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

    def action_seepage(self):
        for le in self:
            account_account = 0
            if self.type == 'apl':
                let_guar_adv_pay_id = int(
                    self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.let_guar_adv_pay_id'))
                account_account = self.env['account.account'].search([('id', '=', let_guar_adv_pay_id)])

            if self.type == 'es':
                init_let_gua_id = int(
                    self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.init_let_gua_id'))
                account_account = self.env['account.account'].search([('id', '=', init_let_gua_id)])

            if self.type == 'fs':
                final_let_guar_id = int(
                    self.env['ir.config_parameter'].sudo().get_param('mm_accounting_customization.final_let_guar_id'))
                account_account = self.env['account.account'].search([('id', '=', final_let_guar_id)])
            if self.status == 'pc':
                vals = {
                    'ref': le.name,
                    'journal_id': le.journal_id.id,
                    'date': fields.Date.today(),
                    'notes': le.notes,
                }
                entry = self.env['account.move'].create(vals)
                if entry:
                    lst = []
                    amount = 0
                    for line0 in le.letter_of_guarantee_ids:
                        if account_account.id == line0.account_id.id:
                            amount += line0.debit

                    for line in le.letter_of_guarantee_ids:
                        var = self.remaining_value - amount
                        if self.journal_id.default_account_id.id == line.account_id.id:
                            if var > 0:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': var,
                                    'credit': 0,
                                })
                                lst.append(val)
                            if var < 0:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': 0,
                                    'credit': -var,
                                })
                                lst.append(val)
                        else:
                            if line.debit == 0:
                                val = (0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': line.credit,
                                    'credit': line.debit,
                                })
                                lst.append(val)
                            if line.credit == 0:
                                if self.journal_id.insurance_account_id.id == line.account_id.id:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': 0,
                                        'credit': self.remaining_value,
                                    })
                                    lst.append(val)
                                elif self.journal_id.expense_account_id.id == line.account_id.id:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': amount,
                                        'credit': 0,
                                    })
                                    lst.append(val)
                                else:
                                    val = (0, 0, {
                                        'account_id': line.account_id.id,
                                        'debit': line.credit,
                                        'credit': line.debit,
                                    })
                                    lst.append(val)

                    entry.line_ids = lst
                    le.is_seepage = True
                    le.move_ids = [(4, entry.id)]
                    entry.letter_of_guarantee_id = le.id

                    le.state = 'seepage'
                    return {
                        'name': 'Journal Entries',
                        'domain': [('id', '=', entry.id)],
                        'view_type': 'form',
                        'res_model': 'account.move',
                        'view_id': False,
                        'view_mode': 'list,form',
                        'type': 'ir.actions.act_window'
                    }
            elif self.status == 'fc':
                vals = {
                    'ref': le.name,
                    'journal_id': le.journal_id.id,
                    'date': fields.Date.today(),
                    'notes': le.notes,
                }
                entry = self.env['account.move'].create(vals)
                if account_account and self.type:
                    if entry:
                        lst = []
                        debit = 0
                        credit = 0
                        amount = 0
                        for line in le.letter_of_guarantee_ids:
                            debit += line.debit
                            credit += line.credit

                        for line in le.letter_of_guarantee_ids:
                            if account_account.id == line.account_id.id:
                                amount += line.debit

                        val = (0, 0, {
                            'account_id': account_account.id,
                            'debit': 0.00,
                            'credit': amount,
                        })
                        lst.append(val)
                        val = (0, 0, {
                            'account_id': le.journal_id.expense_account_id.id,
                            'debit': amount,
                            'credit': 0.00,
                        })
                        lst.append(val)
                        entry.line_ids = lst
                        le.is_seepage = True
                        le.move_ids = [(4, entry.id)]
                        entry.letter_of_guarantee_id = le.id
                        le.state = 'seepage'
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

    # @api.onchange('letter_of_guarantee_ids')
    # def onchange_letter_of_guarantee_ids(self):
    #     for line in self.letter_of_guarantee_ids:
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
    

class LetterOfGuaranteeLine(models.Model):
    _name = 'mm.letter.of.guarantee.line'
    
    link_id = fields.Many2one('mm.letter.of.guarantee')
    account_id = fields.Many2one('account.account', 'Account')
    debit = fields.Float(string='Debit')
    credit = fields.Float(string='Credit')


class GsExtensionLine(models.TransientModel):
    _name = "mm.extension.line"

    link_id = fields.Many2one('mm.letter.of.guarantee')
    start_date = fields.Date(string="Start Date",)
    end_date = fields.Date(string="End Date")
    ramping = fields.Boolean(string='Ramping')
    status = fields.Selection(
        string='Status',
        selection=[('pc', 'Partially covered'),
                   ('fc', 'Fully covered'),
                   ],
        required=False, )
    move_id = fields.Many2one('account.move', 'Journal Entry')
