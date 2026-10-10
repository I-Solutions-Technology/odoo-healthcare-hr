from odoo import fields, models


class AllowanceType(models.Model):
    _inherit = 'healthcare.allowance.type'

    payslip_input_type_id = fields.Many2one(
        'hr.payslip.input.type', string='Payslip Input',
        domain=[('healthcare_source_type', '!=', False)],
        help="Payslip input receiving this allowance. Empty = 'Other Allowance'.")
