from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    healthcare_branch_id = fields.Many2one('healthcare.hr.branch', string='Branch', index=True,
                                           check_company=True, tracking=True)
    healthcare_department_type = fields.Selection([
        ('clinical', 'Clinical'),
        ('nursing', 'Nursing'),
        ('diagnostic', 'Diagnostic'),
        ('pharmacy', 'Pharmacy'),
        ('support', 'Support Services'),
        ('administrative', 'Administrative'),
    ], string='Healthcare Type')
    healthcare_unit_ids = fields.One2many('healthcare.hr.unit', 'department_id', string='Units')
