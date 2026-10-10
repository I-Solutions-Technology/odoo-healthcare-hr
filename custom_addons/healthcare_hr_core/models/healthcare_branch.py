from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HealthcareBranch(models.Model):
    """Hospital, clinic, medical centre or branch.

    A single model carries the Company -> Hospital/Clinic -> Branch levels: a record
    without parent is a facility (hospital, clinic, medical centre) and its children are
    its branches. Departments and units hang below.
    """
    _name = 'healthcare.hr.branch'
    _description = 'Healthcare Facility / Branch'
    _inherit = ['mail.thread']
    _parent_store = True
    _order = 'complete_name'
    _rec_name = 'complete_name'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, tracking=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True, recursive=True)
    code = fields.Char(required=True, tracking=True, help="Short code used on schedules, exports and biometric devices.")
    branch_type = fields.Selection([
        ('hospital', 'Hospital'),
        ('clinic', 'Clinic'),
        ('medical_center', 'Medical Center'),
        ('branch', 'Branch'),
    ], required=True, default='branch', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    parent_id = fields.Many2one('healthcare.hr.branch', string='Parent Facility', index=True, ondelete='restrict',
                                check_company=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('healthcare.hr.branch', 'parent_id', string='Branches')
    manager_id = fields.Many2one('hr.employee', string='Manager', check_company=True, tracking=True)
    department_ids = fields.One2many('hr.department', 'healthcare_branch_id', string='Departments')
    address_id = fields.Many2one('res.partner', string='Address')
    tz = fields.Selection(related='company_id.partner_id.tz', readonly=True)
    active = fields.Boolean(default=True)
    employee_count = fields.Integer(compute='_compute_employee_count')

    _code_company_uniq = models.Constraint(
        'unique (code, company_id)',
        'The branch code must be unique per company.',
    )

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for branch in self:
            if branch.parent_id:
                branch.complete_name = f'{branch.parent_id.complete_name} / {branch.name}'
            else:
                branch.complete_name = branch.name

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if self._has_cycle():
            raise ValidationError(self.env._('You cannot create recursive facility hierarchies.'))

    def _compute_employee_count(self):
        counts = dict(self.env['hr.employee']._read_group(
            [('healthcare_branch_id', 'child_of', self.ids)], ['healthcare_branch_id'], ['__count']))
        for branch in self:
            branch.employee_count = sum(
                count for b, count in counts.items() if b and b.parent_path.startswith(branch.parent_path))

    def action_view_employees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'kanban,list,form',
            'domain': [('healthcare_branch_id', 'child_of', self.id)],
            'context': {'default_healthcare_branch_id': self.id},
        }
