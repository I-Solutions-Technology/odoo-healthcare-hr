from odoo import fields, models

SOURCE_TYPES = [
    ('night_allowance', 'Night Allowance'),
    ('weekend_allowance', 'Weekend Allowance'),
    ('holiday_allowance', 'Holiday Allowance'),
    ('on_call', 'On Call'),
    ('allowance', 'Other Allowance'),
    ('overtime', 'Overtime'),
    ('bonus', 'Bonus'),
    ('deduction', 'Deduction'),
    ('loan_installment', 'Loan Installment'),
    ('advance', 'Salary Advance'),
]


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    healthcare_source_type = fields.Selection(
        SOURCE_TYPES, help="Set on the input types managed by the Healthcare HR suite.")
    healthcare_is_deduction = fields.Boolean(help="Reduces the net salary.")
