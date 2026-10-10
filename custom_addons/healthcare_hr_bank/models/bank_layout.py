from odoo import fields, models

COLUMN_FIELDS = [
    ('employee_number', 'Employee Number'),
    ('employee_name', 'Employee Name'),
    ('arabic_name', 'Arabic Name'),
    ('national_id', 'National ID'),
    ('bank_name', 'Bank Name'),
    ('bank_bic', 'Bank BIC / SWIFT'),
    ('iban', 'IBAN'),
    ('account_number', 'Account Number'),
    ('amount', 'Net Salary'),
    ('currency', 'Currency'),
    ('reference', 'Reference'),
    ('payment_date', 'Payment Date'),
    ('branch_code', 'Branch Code'),
    ('constant', 'Constant Value'),
]


class BankLayout(models.Model):
    _name = 'healthcare.payroll.bank.layout'
    _description = 'Payroll Bank File Layout'
    _order = 'name'

    name = fields.Char(required=True)
    file_format = fields.Selection([('csv', 'CSV'), ('txt', 'Fixed-width TXT'), ('xlsx', 'Excel (XLSX)')],
                                   required=True, default='csv')
    delimiter = fields.Char(default=',', size=3)
    include_header = fields.Boolean(default=True)
    encoding = fields.Selection([('utf-8', 'UTF-8'), ('utf-8-sig', 'UTF-8 with BOM (Excel)'),
                                 ('cp1256', 'Windows-1256 (Arabic)'), ('ascii', 'ASCII')], default='utf-8', required=True)
    decimal_places = fields.Integer(default=2)
    amount_without_separator = fields.Boolean(help="Write 1234.50 as 123450 (common in fixed-width bank files).")
    date_format = fields.Char(default='%Y-%m-%d', required=True)
    line_ending = fields.Selection([('lf', 'LF'), ('crlf', 'CRLF')], default='crlf', required=True)
    api_provider = fields.Selection([('none', 'File Only')], default='none', required=True,
                                    help="Extension point: a bank connector module adds its provider here and "
                                         "implements _send_<provider> on the batch.")
    column_ids = fields.One2many('healthcare.payroll.bank.layout.column', 'layout_id', string='Columns', copy=True)
    company_id = fields.Many2one('res.company')
    active = fields.Boolean(default=True)


class BankLayoutColumn(models.Model):
    _name = 'healthcare.payroll.bank.layout.column'
    _description = 'Payroll Bank File Column'
    _order = 'sequence, id'

    layout_id = fields.Many2one('healthcare.payroll.bank.layout', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    header = fields.Char(required=True)
    field = fields.Selection(COLUMN_FIELDS, required=True)
    constant_value = fields.Char()
    width = fields.Integer(help="Fixed-width TXT only.")
    alignment = fields.Selection([('left', 'Left'), ('right', 'Right')], default='left')
    pad_char = fields.Char(default=' ', size=1)
