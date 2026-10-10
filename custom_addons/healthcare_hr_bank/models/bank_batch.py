import base64
import csv
import io
import logging

import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankBatch(models.Model):
    _name = 'healthcare.payroll.bank.batch'
    _description = 'Payroll Bank Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(default=lambda self: self.env._('New'), readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    layout_id = fields.Many2one('healthcare.payroll.bank.layout', required=True, tracking=True)
    payment_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    date_from = fields.Date(string='Payslips From')
    date_to = fields.Date(string='Payslips To')
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Pay Run', check_company=True)
    branch_id = fields.Many2one('healthcare.hr.branch', check_company=True)
    reference = fields.Char(help="Batch reference communicated to the bank.")
    line_ids = fields.One2many('healthcare.payroll.bank.line', 'batch_id', string='Lines')
    total_amount = fields.Monetary(compute='_compute_totals', store=True)
    line_count = fields.Integer(compute='_compute_totals', store=True)
    error_count = fields.Integer(compute='_compute_totals', store=True)
    export_file = fields.Binary(readonly=True, attachment=True, copy=False)
    export_filename = fields.Char(readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'), ('generated', 'Generated'), ('exported', 'Exported'), ('sent', 'Sent to Bank'),
        ('done', 'Done'), ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New')) == self.env._('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('healthcare.payroll.bank.batch') or '/'
        return super().create(vals_list)

    @api.depends('line_ids.amount', 'line_ids.state')
    def _compute_totals(self):
        for batch in self:
            valid = batch.line_ids.filtered(lambda l: l.state == 'valid')
            batch.total_amount = sum(valid.mapped('amount'))
            batch.line_count = len(valid)
            batch.error_count = len(batch.line_ids.filtered(lambda l: l.state == 'error'))

    def _payslip_domain(self):
        self.ensure_one()
        domain = [('company_id', '=', self.company_id.id), ('state', 'in', ('validated', 'paid')), ('net_wage', '>', 0)]
        if self.payslip_run_id:
            domain.append(('payslip_run_id', '=', self.payslip_run_id.id))
        if self.date_from:
            domain.append(('date_to', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_to', '<=', self.date_to))
        if self.branch_id:
            domain.append(('healthcare_branch_id', 'child_of', self.branch_id.id))
        return domain

    def action_generate_lines(self):
        """(Re)build the lines. Payslips already exported in another active batch are skipped."""
        Line = self.env['healthcare.payroll.bank.line']
        for batch in self:
            if batch.state not in ('draft', 'generated'):
                raise UserError(self.env._('Only draft batches can be regenerated.'))
            batch.line_ids.unlink()
            payslips = self.env['hr.payslip'].search(batch._payslip_domain())
            taken = Line.search([('payslip_id', 'in', payslips.ids),
                                 ('batch_id.state', 'not in', ('cancelled',)), ('batch_id', '!=', batch.id)]).payslip_id
            vals = []
            for slip in payslips - taken:
                employee = slip.employee_id.sudo()
                account = employee.primary_bank_account_id
                error = False
                if not account:
                    error = self.env._('No bank account on the employee.')
                elif not account.allow_out_payment:
                    error = self.env._('Bank account not trusted (enable "Send Money" after verification).')
                vals.append({
                    'batch_id': batch.id, 'payslip_id': slip.id, 'employee_id': employee.id,
                    'bank_account_id': account.id or False, 'amount': slip.net_wage,
                    'reference': f'{batch.reference or batch.name}/{employee.employee_number or employee.id}',
                    'state': 'error' if error else 'valid', 'error_message': error,
                })
            Line.create(vals)
            batch.state = 'generated'

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _column_value(self, column, line):
        layout = self.layout_id
        employee = line.employee_id.sudo()
        account = line.bank_account_id.sudo()
        field = column.field
        if field == 'amount':
            value = f'{line.amount:.{layout.decimal_places}f}'
            return value.replace('.', '') if layout.amount_without_separator else value
        values = {
            'employee_number': employee.employee_number or '',
            'employee_name': employee.name or '',
            'arabic_name': employee.arabic_name or '',
            'national_id': employee.identification_id or '',
            'bank_name': account.bank_id.name or '',
            'bank_bic': account.bank_id.bic or '',
            'iban': account.acc_number.replace(' ', '') if account.acc_type == 'iban' else '',
            'account_number': (account.acc_number or '').replace(' ', ''),
            'currency': self.currency_id.name or '',
            'reference': line.reference or '',
            'payment_date': self.payment_date.strftime(layout.date_format),
            'branch_code': employee.healthcare_branch_id.code or '',
            'constant': column.constant_value or '',
        }
        return values.get(field, '')

    def _rows(self):
        self.ensure_one()
        columns = self.layout_id.column_ids
        lines = self.line_ids.filtered(lambda l: l.state == 'valid')
        return columns, [[self._column_value(col, line) for col in columns] for line in lines]

    def _render_csv(self):
        columns, rows = self._rows()
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=self.layout_id.delimiter or ',',
                            lineterminator='\r\n' if self.layout_id.line_ending == 'crlf' else '\n')
        if self.layout_id.include_header:
            writer.writerow(columns.mapped('header'))
        writer.writerows(rows)
        return buffer.getvalue().encode(self.layout_id.encoding, errors='replace'), 'csv'

    def _render_txt(self):
        columns, rows = self._rows()
        eol = '\r\n' if self.layout_id.line_ending == 'crlf' else '\n'

        def fit(col, value):
            value = str(value)
            if not col.width:
                return value
            value = value[:col.width]
            pad = col.pad_char or ' '
            return value.rjust(col.width, pad) if col.alignment == 'right' else value.ljust(col.width, pad)

        out = []
        if self.layout_id.include_header:
            out.append(''.join(fit(col, col.header) for col in columns))
        out += [''.join(fit(col, value) for col, value in zip(columns, row)) for row in rows]
        return (eol.join(out) + eol).encode(self.layout_id.encoding, errors='replace'), 'txt'

    def _render_xlsx(self):
        columns, rows = self._rows()
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet('Salaries')
        bold = workbook.add_format({'bold': True})
        row_index = 0
        if self.layout_id.include_header:
            for col_index, column in enumerate(columns):
                sheet.write(0, col_index, column.header, bold)
            row_index = 1
        for row in rows:
            for col_index, (column, value) in enumerate(zip(columns, row)):
                if column.field == 'amount' and not self.layout_id.amount_without_separator:
                    sheet.write_number(row_index, col_index, float(value))
                else:
                    sheet.write_string(row_index, col_index, str(value))
            row_index += 1
        workbook.close()
        return buffer.getvalue(), 'xlsx'

    def action_export(self):
        for batch in self:
            if batch.state not in ('generated', 'exported'):
                raise UserError(self.env._('Generate the lines first.'))
            if batch.error_count:
                raise UserError(self.env._('%s line(s) have errors: fix the bank accounts or remove the lines.',
                                           batch.error_count))
            if not batch.line_count:
                raise UserError(self.env._('Nothing to export.'))
            content, extension = getattr(batch, f'_render_{batch.layout_id.file_format}')()
            batch.write({
                'export_file': base64.b64encode(content),
                'export_filename': f'{batch.name.replace("/", "_")}.{extension}',
                'state': 'exported',
            })
            batch.message_post(body=self.env._('Bank file exported: %(n)s line(s), total %(total)s.',
                                               n=batch.line_count, total=batch.total_amount))
        return True

    def action_send_to_bank(self):
        for batch in self:
            if batch.state != 'exported':
                raise UserError(self.env._('Export the file first.'))
            batch._send_to_bank()

    def _send_to_bank(self):
        """API extension point: implement _send_<provider>(self) in a connector module."""
        self.ensure_one()
        provider = self.layout_id.api_provider
        if provider == 'none':
            raise UserError(self.env._('This layout is file-only: upload the exported file to the bank portal, '
                                       'then mark the batch as sent.'))
        method = getattr(self, f'_send_{provider}', None)
        if not method:
            raise UserError(self.env._('No connector installed for provider %s.', provider))
        try:
            method()
        except UserError:
            raise
        except Exception as error:
            _logger.exception('Bank API error for batch %s', self.name)
            raise UserError(self.env._('The bank rejected the batch: %s', error))
        self.state = 'sent'

    def action_mark_sent(self):
        self.filtered(lambda b: b.state == 'exported').write({'state': 'sent'})

    def action_done(self):
        for batch in self.filtered(lambda b: b.state == 'sent'):
            batch.line_ids.filtered(lambda l: l.state == 'valid').payslip_id.filtered(
                lambda s: s.state == 'validated').action_payslip_paid()
            batch.state = 'done'

    def action_cancel(self):
        self.filtered(lambda b: b.state != 'done').write({'state': 'cancelled'})

    def action_draft(self):
        self.filtered(lambda b: b.state in ('generated', 'exported', 'cancelled')).write(
            {'state': 'draft', 'export_file': False, 'export_filename': False})


class BankLine(models.Model):
    _name = 'healthcare.payroll.bank.line'
    _description = 'Payroll Bank Line'
    _order = 'employee_id'

    batch_id = fields.Many2one('healthcare.payroll.bank.batch', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True)
    currency_id = fields.Many2one(related='batch_id.currency_id')
    payslip_id = fields.Many2one('hr.payslip', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    bank_account_id = fields.Many2one('res.partner.bank', string='Bank Account')
    bank_id = fields.Many2one(related='bank_account_id.bank_id', string='Bank')
    iban = fields.Char(compute='_compute_account_numbers', string='IBAN')
    account_number = fields.Char(compute='_compute_account_numbers')
    amount = fields.Monetary(string='Net Salary')
    reference = fields.Char()
    state = fields.Selection([('valid', 'Valid'), ('error', 'Error')], default='valid', required=True)
    error_message = fields.Char()

    @api.depends('bank_account_id')
    def _compute_account_numbers(self):
        for line in self:
            account = line.bank_account_id.sudo()
            line.account_number = account.acc_number or False
            line.iban = account.acc_number if account.acc_type == 'iban' else False
