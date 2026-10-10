from odoo import fields, models


class ClearanceDepartment(models.Model):
    _name = 'healthcare.hr.clearance.department'
    _description = 'Clearance Department'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    responsible_user_id = fields.Many2one('res.users', string='Responsible',
                                          help="Empty: the employee's department manager (for the 'DEPT' code) "
                                               "or the company HR alert responsible.")
    mandatory = fields.Boolean(default=True)
    checklist = fields.Text(help="What must be returned or verified.", translate=True)
    company_id = fields.Many2one('res.company', help="Empty = all companies.")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique (code, company_id)', 'The clearance department code must be unique.')
