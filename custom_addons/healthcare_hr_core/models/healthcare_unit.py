from odoo import api, fields, models


class HealthcareUnit(models.Model):
    """Clinical or administrative unit inside a department (ICU bay, ER triage, OR 1 ...)."""
    _name = 'healthcare.hr.unit'
    _description = 'Healthcare Unit'
    _inherit = ['mail.thread']
    _order = 'branch_id, department_id, name'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('healthcare.hr.branch', string='Branch', required=True, index=True,
                                check_company=True, tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True, index=True,
                                    check_company=True, tracking=True)
    parent_id = fields.Many2one('healthcare.hr.unit', string='Parent Unit', check_company=True)
    manager_id = fields.Many2one('hr.employee', string='Unit Manager', check_company=True, tracking=True)
    unit_type = fields.Selection([
        ('clinical', 'Clinical'),
        ('critical_care', 'Critical Care'),
        ('emergency', 'Emergency'),
        ('surgical', 'Surgical / Operating Room'),
        ('diagnostic', 'Diagnostic'),
        ('support', 'Support'),
        ('administrative', 'Administrative'),
    ], default='clinical', required=True)
    active = fields.Boolean(default=True)

    _code_branch_uniq = models.Constraint(
        'unique (code, branch_id)',
        'The unit code must be unique per branch.',
    )

    @api.onchange('department_id')
    def _onchange_department_id(self):
        if self.department_id.healthcare_branch_id:
            self.branch_id = self.department_id.healthcare_branch_id
