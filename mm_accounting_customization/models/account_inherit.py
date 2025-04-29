# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import ast
from odoo.tools.misc import format_date
from collections import defaultdict
import datetime
from odoo.exceptions import ValidationError
from odoo.addons.stock_landed_costs.models import product

SPLIT_METHOD = [
    ('equal', 'Equal'),
    ('by_quantity', 'By Quantity'),
    ('by_current_cost_price', 'By Current Cost'),
    ('by_weight', 'By Weight'),
    ('by_volume', 'By Volume'),
]

class ProductTemplate(models.Model):
    _inherit = "product.template"

    split_method = fields.Selection(
        selection=SPLIT_METHOD, string='Split Method', default='by_current_cost_price',
        help="Equal : Cost will be equally divided.\n"
             "By Quantity : Cost will be divided according to product's quantity.\n"
             "By Current cost : Cost will be divided according to product's current cost.\n"
             "By Weight : Cost will be divided depending on its weight.\n"
             "By Volume : Cost will be divided depending on its volume.")

class LandedCostLine(models.Model):
    _inherit = 'stock.landed.cost.lines'

    split_method = fields.Selection(product.SPLIT_METHOD, string='Split Method', required=True, default='by_current_cost_price')



class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    portal_id = fields.Char(string='Portal ID')
    letter_of_guarantee_id = fields.Many2one('mm.letter.of.guarantee')
    insurance_ids = fields.Many2many('mm.insurance')
    notes = fields.Text(string="Notes",)
    is_group_access_seq = fields.Boolean(compute='_compute_access_seq')

    def _compute_access_seq(self):
        for rec in self:
            rec.is_group_access_seq = False
            if self.env.user.has_groups('mm_accounting_customization.group_access_seq'):
                rec.is_group_access_seq = True

    def get_cash_guarantee(self):
        return {
            'name': 'Cash Guarantee',
            'domain': [('id', 'in', self.insurance_ids.ids)],
            'view_type': 'form',
            'res_model': 'mm.insurance',
            'view_id': False,
            'view_mode': 'list,form',
            'type': 'ir.actions.act_window'
        }

    cash_guarantee_count = fields.Integer(compute='_compute_cash_guarantee_count')

    def _compute_cash_guarantee_count(self):
        self.cash_guarantee_count = self.env['mm.insurance'].search_count([('id', 'in', self.insurance_ids.ids)])

    def button_cancel(self):
        for move in self:
            move.letter_of_guarantee_id.state = 'approve'
            move.letter_of_guarantee_id.is_extension = False
            move.letter_of_guarantee_id.is_recovery = False
            move.letter_of_guarantee_id.is_seepage = False
        return super(AccountMoveInherit, self).button_cancel()

    @api.onchange('date')
    def _onchange_mm_date(self):
        for rec in self:
            if rec.date:
                d1 = fields.Date.today()
                d2 = rec.date
                if d2.year < d1.year and not self.env.user.has_group('mm_accounting_customization.group_edit_accounting_date'):
                    raise ValidationError(_("You Can Not Enter The Date Before This Year"))


class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    portal_id = fields.Char(string='Portal ID', related="move_id.portal_id")


class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'

    portal_id = fields.Text(string='Portal ID')
    run_compute = fields.Boolean(compute='_compute_get_reconciled_invoice_ids')

    def _compute_get_reconciled_invoice_ids(self):
        for rec in self:
            rec.portal_id = ''
            rec.run_compute = True
            if rec.reconciled_invoice_ids:
                for inv in rec.reconciled_invoice_ids:
                    rec.portal_id += str(inv.portal_id) + ', '


class AccountPaymentRegisterInherit(models.TransientModel):
    _inherit = 'account.payment.register'

    name = fields.Char(string='Reference')
    partner_id = fields.Many2one('res.partner', 'Customer')
    start_date = fields.Date(string="Start Date", )
    end_date = fields.Date(string="End Date")
    type = fields.Selection(
        string='Type',
        selection=[('apl', 'Advance payment Cash Guarantee'),
                   ('es', 'Elementary Cash Guarantee'),
                   ('fs', 'Final Cash Guarantee'),
                   ],
        required=False, default='fs')

    status = fields.Selection(
        string='Status',
        selection=[('pc', 'Partially covered'),
                   ('fc', 'Fully covered'),
                   ],
        required=False, )
    move_mm_test_id = fields.Many2one('account.move')
    mm_payment_type = fields.Selection(string='Payment Type',
                                    selection=[
                                        ('normal', 'Normal'),
                                        ('cheque', 'Cheque'),
                                    ],
                                    required=False, default='normal')
    notes = fields.Text(string="Notes",)

    def action_cash_guarantee(self):
        account_move = self.env['account.move'].search([('name', '=', self.communication)])

        vals = {
            'journal_id': self.journal_id.id,
            'partner_id': self.partner_id.id,
            'writeoff_account_id': self.writeoff_account_id.id,
            'writeoff_amount': self.payment_difference,
            'date': self.payment_date,
            'name': self.communication,
            'move_id': account_move.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'type': self.type,
            'payment_type': self.mm_payment_type,
            'notes': self.notes,
        }
        insurance = self.env['mm.insurance'].create(vals)
        insurance.state = 'approve'
        insurance._onchange_writeoff_account_id()
        self.move_mm_test_id.insurance_ids = [(4, insurance.id)]

    # def action_create_payments(self):
    #     result = super(AccountPaymentRegisterInherit, self).action_create_payments()
    #     self.action_cash_guarantee()
    #     return result


class StockMoveLineInherit(models.Model):
    _inherit = 'stock.move.line'

    picking_partner_id = fields.Many2one(related='picking_id.partner_id', readonly=True, store=True)
    lst_price = fields.Float(string='Sales Price', compute='_compute_gst_cost')
    standard_price = fields.Float('Cost', compute='_compute_set_price')
    cost_per_unit = fields.Float('Cost Per-unit',  compute='_compute_gst_cost')
    total_cost = fields.Float('Total Cost',  compute='_compute_gst_cost')
    is_has_cost = fields.Boolean(compute='_compute_is_has_cost')

    def _compute_is_has_cost(self):
        for rec in self:
            if self.env.user.has_groups("mm_accounting_customization.group_access_cost"):
                rec.is_has_cost = True
            else:
                rec.is_has_cost = False

    def _compute_set_price(self):
        for rec in self:
            # rec.lst_price = 0
            rec.standard_price = 0
            stock_picking = self.env['stock.picking'].search([('name', '=', rec.reference)])
            if stock_picking.picking_type_id.code == 'internal':
                # rec.lst_price = 0
                rec.standard_price = 0
            else:
                if stock_picking.picking_type_id.code == 'incoming' and stock_picking.picking_type_id.name != 'Returns':
                    # rec.lst_price = 0
                    rec.standard_price = rec.product_id.standard_price

                elif stock_picking.picking_type_id.code == 'outgoing':
                    # rec.lst_price = rec.product_id.lst_price
                    rec.standard_price = 0

                if stock_picking.picking_type_id.code == 'incoming' and stock_picking.picking_type_id.name == 'Returns' and rec.location_id == self.env.ref("stock.stock_location_customers"):
                    # rec.lst_price = - rec.product_id.lst_price
                    rec.standard_price = 0

                if stock_picking.picking_type_id.code == 'incoming' and stock_picking.picking_type_id.name == 'Returns' and rec.location_id == self.env.ref("stock.stock_location_suppliers"):
                    # rec.lst_price = 0
                    rec.standard_price = rec.product_id.standard_price

    def _compute_gst_cost(self):
        for rec in self:
            rec.cost_per_unit = 0
            rec.total_cost = 0
            rec.lst_price = 0
            stock_valuation = self.env['stock.valuation.layer'].search([('reference', '=', rec.reference), ('product_id', '=', rec.product_id.id)])
            if stock_valuation and rec.location_dest_id.usage == 'internal':
                rec.total_cost = sum(stock_valuation.mapped('value'))
                # rec.qty_done = sum(stock_valuation.mapped('quantity'))
                if rec.qty_done != 0:
                    rec.cost_per_unit = rec.total_cost / rec.qty_done
                # rec.cost_per_unit = sum(stock_valuation.mapped('unit_cost'))

            sale_order_line = self.env['sale.order.line'].search([('order_id.name', '=', rec.origin), ('product_id', '=', rec.product_id.id)])
            if sale_order_line:
                rec.lst_price = sum(sale_order_line.mapped('price_subtotal'))


class StockMoveInherit(models.Model):
    _inherit = 'stock.move'

    lst_price = fields.Float(string='Sales Price', compute='_compute_set_price')
    standard_price = fields.Float('Cost', compute='_compute_set_price' )
    is_has_cost = fields.Boolean(compute='_compute_is_has_cost')

    def _compute_is_has_cost(self):
        for rec in self:
            if self.env.user.has_groups("mm_accounting_customization.group_access_cost"):
                rec.is_has_cost = True
            else:
                rec.is_has_cost = False

    def _compute_set_price(self):
        for rec in self:
            rec.lst_price = 0
            rec.standard_price = 0
            stock_picking = self.env['stock.picking'].search([('name', '=', rec.reference)])
            if stock_picking.picking_type_id.code == 'internal':
                rec.lst_price = 0
                rec.standard_price = 0
            else:
                if stock_picking.picking_type_id.code == 'incoming' and stock_picking.picking_type_id.name != 'Returns':
                    rec.lst_price = 0
                    rec.standard_price = rec.product_id.standard_price

                elif stock_picking.picking_type_id.code == 'outgoing':
                    rec.lst_price = rec.product_id.lst_price
                    rec.standard_price = 0

                if stock_picking.picking_type_id.code == 'incoming' and stock_picking.picking_type_id.name == 'Returns' and rec.location_id == self.env.ref("stock.stock_location_customers"):
                    rec.lst_price = - rec.product_id.lst_price
                    rec.standard_price = 0

                if stock_picking.picking_type_id.code == 'incoming' and stock_picking.picking_type_id.name == 'Returns' and rec.location_id == self.env.ref("stock.stock_location_suppliers"):
                    rec.lst_price = 0
                    rec.standard_price = rec.product_id.standard_price


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    is_has_cost = fields.Boolean(compute='_compute_is_has_cost')

    def _compute_is_has_cost(self):
        for rec in self:
            if self.env.user.has_groups("mm_accounting_customization.group_access_cost"):
                rec.is_has_cost = True
            else:
                rec.is_has_cost = False


class ProductProductInherit(models.Model):
    _inherit = 'product.product'

    is_has_cost = fields.Boolean(compute='_compute_is_has_cost')

    def _compute_is_has_cost(self):
        for rec in self:
            if self.env.user.has_groups("mm_accounting_customization.group_access_cost"):
                rec.is_has_cost = True
            else:
                rec.is_has_cost = False


class AccountJournal(models.Model):
    _inherit = "account.journal"

    insurance_account_id = fields.Many2one('account.account', 'Insurance Account')
    bank_facility_account_id = fields.Many2one('account.account', 'Bank facility Account')
    expense_account_id = fields.Many2one('account.account', 'Expense Account')

    def open_letter_of_guarantee_action(self):
        action_ref = 'mm_accounting_customization.mm_letter_of_guarantee_action'
        action = self.env['ir.actions.act_window']._for_xml_id(action_ref)
        action['context'] = dict(ast.literal_eval(action.get('context')), default_journal_id=self.id, search_default_journal_id=self.id)
        action['views'] = [(False, 'list'),(False,'form')]
        return action

    def open_insurance_action(self):
        action_ref = 'mm_accounting_customization.mm_insurance_action'
        action = self.env['ir.actions.act_window']._for_xml_id(action_ref)
        action['context'] = dict(ast.literal_eval(action.get('context')), default_journal_id=self.id, search_default_journal_id=self.id)
        action['views'] = [(False, 'list'),(False,'form')]
        return action


class StockValuationLayerInherit(models.Model):
    _inherit = "stock.valuation.layer"

    reference = fields.Char(string='Reference', related='stock_move_id.reference')


class SaleOrderInherit(models.Model):
    _inherit = "sale.order"

    is_look_sales = fields.Boolean(compute='_compute_is_look_sales')

    def _compute_is_look_sales(self):
        for rec in self:
            rec.is_look_sales = False
            if self.env.user.has_group('sale.group_auto_done_setting'):
                if self.env.user.has_group('sales_team.group_sale_salesman_all_leads') or self.env.user.has_group('sales_team.group_sale_salesman') or self.env.user.has_group('sales_team.group_sale_manager'):
                    rec.is_look_sales = True


# class AccountPartnerLedgerInherit(models.AbstractModel):
#     _inherit = "account.partner.ledger"
#
#     @api.model
#     def _do_query(self, options, expanded_partner=None):
#         ''' Execute the queries, perform all the computation and return partners_results,
#         a lists of tuple (partner, fetched_values) sorted by the table's model _order:
#             - partner is a res.parter record.
#             - fetched_values is a dictionary containing:
#                 - sum:                              {'debit': float, 'credit': float, 'balance': float}
#                 - (optional) initial_balance:       {'debit': float, 'credit': float, 'balance': float}
#                 - (optional) lines:                 [line_vals_1, line_vals_2, ...]
#         :param options:             The report options.
#         :param expanded_account:    An optional account.account record that must be specified when expanding a line
#                                     with of without the load more.
#         :param fetch_lines:         A flag to fetch the account.move.lines or not (the 'lines' key in accounts_values).
#         :return:                    (accounts_values, taxes_results)
#         '''
#         def assign_sum(row):
#             key = row['key']
#             fields = ['balance', 'debit', 'credit'] if key == 'sum' else ['balance']
#             if any(not company_currency.is_zero(row[field]) for field in fields):
#                 groupby_partners.setdefault(row['groupby'], defaultdict(lambda: defaultdict(float)))
#                 for field in fields:
#                     groupby_partners[row['groupby']][key][field] += row[field]
#
#         company_currency = self.env.company.currency_id
#
#         # flush the tables that gonna be queried
#         self.env['account.move.line'].flush(fnames=self.env['account.move.line']._fields)
#         self.env['account.move'].flush(fnames=self.env['account.move']._fields)
#         self.env['account.partial.reconcile'].flush(fnames=self.env['account.partial.reconcile']._fields)
#
#         # Execute the queries and dispatch the results.
#         query, params = self._get_query_sums(options, expanded_partner=expanded_partner)
#
#         groupby_partners = {}
#
#         self._cr.execute(query, params)
#         for res in self._cr.dictfetchall():
#             assign_sum(res)
#
#         # Fetch the lines of unfolded accounts.
#         unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])
#         if expanded_partner or unfold_all or options['unfolded_lines']:
#             query, params = self._get_query_amls(options, expanded_partner=expanded_partner)
#             self._cr.execute(query, params)
#             for res in self._cr.dictfetchall():
#                 if res['partner_id'] not in groupby_partners:
#                     continue
#                 groupby_partners[res['partner_id']].setdefault('lines', [])
#                 groupby_partners[res['partner_id']]['lines'].append(res)
#
#             query, params = self._get_lines_without_partner(options, expanded_partner=expanded_partner)
#             self._cr.execute(query, params)
#             for row in self._cr.dictfetchall():
#                 # don't show lines of partners not expanded
#                 if row['partner_id'] in groupby_partners:
#                     groupby_partners[row['partner_id']].setdefault('lines', [])
#                     row['class'] = ' text-muted'
#                     groupby_partners[row['partner_id']]['lines'].append(row)
#                 if None in groupby_partners:
#                     # reconciled lines without partners are fetched to be displayed under the matched partner
#                     # and thus but be inversed to be displayed under the unknown partner
#                     none_row = row.copy()
#                     none_row['class'] = ' text-muted'
#                     none_row['debit'] = row['credit']
#                     none_row['credit'] = row['debit']
#                     none_row['amount_currency'] = row['amount_currency']
#                     none_row['balance'] = -row['balance']
#                     groupby_partners[None].setdefault('lines', [])
#                     groupby_partners[None]['lines'].append(none_row)
#
#         # correct the sums per partner, for the lines without partner reconciled with a line having a partner
#         query, params = self._get_sums_without_partner(options, expanded_partner=expanded_partner)
#         self._cr.execute(query, params)
#         total = total_debit = total_credit = total_amount_currency = total_initial_balance = 0
#         for row in self._cr.dictfetchall():
#             key = row['key']
#             total_debit += key == 'sum' and row['debit'] or 0
#             total_credit += key == 'sum' and row['credit'] or 0
#             total_amount_currency += key == 'sum' and row['amount_currency'] or 0
#             total_initial_balance += key == 'initial_balance' and row['balance'] or 0
#             total += key == 'sum' and row['balance'] or 0
#             if None not in groupby_partners and not (expanded_partner or unfold_all or options['unfolded_lines']):
#                 groupby_partners.setdefault(None, {})
#             if row['groupby'] not in groupby_partners:
#                 continue
#             assign_sum(row)
#
#         if None in groupby_partners:
#             if 'sum' not in groupby_partners[None]:
#                 groupby_partners[None].setdefault('sum', {'debit': 0, 'credit': 0, 'amount_currency': 0, 'balance': 0})
#             if 'initial_balance' not in groupby_partners[None]:
#                 groupby_partners[None].setdefault('initial_balance', {'balance': 0})
#             #debit/credit are inversed for the unknown partner as the computation is made regarding the balance of the known partner
#             groupby_partners[None]['sum']['debit'] += total_credit
#             groupby_partners[None]['sum']['credit'] += total_debit
#             groupby_partners[None]['sum']['amount_currency'] += total_amount_currency
#             groupby_partners[None]['sum']['balance'] -= total
#             groupby_partners[None]['initial_balance']['balance'] -= total_initial_balance
#
#         # Retrieve the partners to browse.
#         # groupby_partners.keys() contains all account ids affected by:
#         # - the amls in the current period.
#         # - the amls affecting the initial balance.
#         # Note a search is done instead of a browse to preserve the table ordering.
#         if expanded_partner:
#             partners = expanded_partner
#         elif groupby_partners:
#             partners = self.env['res.partner'].with_context(active_test=False).search([('id', 'in', list(groupby_partners.keys()))])
#         else:
#             partners = []
#
#         # Add 'Partner Unknown' if needed
#         if None in groupby_partners.keys():
#             partners = [p for p in partners] + [None]
#         return [(partner, groupby_partners[partner.id if partner else None]) for partner in partners]
#
#     @api.model
#     def _get_partner_ledger_lines(self, options, line_id=None):
#         ''' Get lines for the whole report or for a specific line.
#         :param options: The report options.
#         :return:        A list of lines, each one represented by a dictionary.
#         '''
#         lines = []
#         unfold_all = options.get('unfold_all') or (self._context.get('print_mode') and not options['unfolded_lines'])
#
#         expanded_partner = line_id and self.env['res.partner'].browse(int(line_id[8:]))
#         partners_results = self._do_query(options, expanded_partner=expanded_partner)
#
#         total_initial_balance = total_debit = total_credit = total_amount_currency = total_balance = 0.0
#         for partner, results in partners_results:
#             is_unfolded = 'partner_%s' % (partner.id if partner else 0) in options['unfolded_lines']
#
#             # res.partner record line.
#             partner_sum = results.get('sum', {})
#             partner_init_bal = results.get('initial_balance', {})
#
#             initial_balance = partner_init_bal.get('balance', 0.0)
#             debit = partner_sum.get('debit', 0.0)
#             credit = partner_sum.get('credit', 0.0)
#             amount_currency = partner_sum.get('amount_currency', 0.0)
#             balance = initial_balance + partner_sum.get('balance', 0.0)
#             print("partner_sum.get('amount_currency', 0.0)", partner_sum.get('amount_currency', 0.0))
#             lines.append(self._get_report_line_partner(options, partner, initial_balance, debit, credit, amount_currency, balance))
#
#             total_initial_balance += initial_balance
#             total_debit += debit
#             total_credit += credit
#             total_amount_currency += amount_currency
#             total_balance += balance
#
#             if unfold_all or is_unfolded:
#                 cumulated_balance = initial_balance
#
#                 # account.move.line record lines.
#                 amls = results.get('lines', [])
#
#                 load_more_remaining = len(amls)
#                 load_more_counter = self._context.get('print_mode') and load_more_remaining or self.MAX_LINES
#
#                 for aml in amls:
#                     # Don't show more line than load_more_counter.
#                     if load_more_counter == 0:
#                         break
#
#                     cumulated_init_balance = cumulated_balance
#                     cumulated_balance += aml['balance']
#                     lines.append(self._get_report_line_move_line(options, partner, aml, cumulated_init_balance, cumulated_balance))
#
#                     load_more_remaining -= 1
#                     load_more_counter -= 1
#
#                 if load_more_remaining > 0:
#                     # Load more line.
#                     lines.append(self._get_report_line_load_more(
#                         options,
#                         partner,
#                         self.MAX_LINES,
#                         load_more_remaining,
#                         cumulated_balance,
#                     ))
#
#         if not line_id:
#             print("total_amount_currency", total_amount_currency)
#             # Report total line.
#             lines.append(self._get_report_line_total(
#                 options,
#                 total_initial_balance,
#                 total_debit,
#                 total_credit,
#                 total_amount_currency,
#                 total_balance
#             ))
#         return lines
#
#     def _get_report_line_partner(self, options, partner, initial_balance, debit, credit, amount_currency, balance):
#         company_currency = self.env.company.currency_id
#         unfold_all = self._context.get('print_mode') and not options.get('unfolded_lines')
#
#         columns = [
#             {'name': self.format_value(initial_balance), 'class': 'number'},
#             {'name': self.format_value(debit), 'class': 'number'},
#             {'name': self.format_value(credit), 'class': 'number'},
#         ]
#         if self.env.user.has_groups('base.group_multi_currency'):
#             columns.append({'name': self.format_value(amount_currency), 'class': 'number'},)
#         columns.append({'name': self.format_value(balance), 'class': 'number'})
#
#         return {
#             'id': 'partner_%s' % (partner.id if partner else 0),
#             'partner_id': partner.id if partner else None,
#             'name': partner is not None and (partner.name or '')[:128] or _('Unknown Partner'),
#             'columns': columns,
#             'level': 2,
#             'trust': partner.trust if partner else None,
#             'unfoldable': not company_currency.is_zero(debit) or not company_currency.is_zero(credit),
#             'unfolded': 'partner_%s' % (partner.id if partner else 0) in options['unfolded_lines'] or unfold_all,
#             'colspan': 6,
#         }
#
#
#     @api.model
#     def _get_report_line_total(self, options, initial_balance, debit, credit, amount_currency, balance):
#         columns = [
#             {'name': self.format_value(initial_balance), 'class': 'number'},
#             {'name': self.format_value(debit), 'class': 'number'},
#             {'name': self.format_value(credit), 'class': 'number'},
#         ]
#         if self.env.user.has_groups('base.group_multi_currency'):
#             columns.append({'name': self.format_value(amount_currency), 'class': 'number'},)
#         columns.append({'name': self.format_value(balance), 'class': 'number'})
#         return {
#             'id': 'partner_ledger_total_%s' % self.env.company.id,
#             'name': _('Total'),
#             'class': 'total',
#             'level': 1,
#             'columns': columns,
#             'colspan': 6,
#         }
