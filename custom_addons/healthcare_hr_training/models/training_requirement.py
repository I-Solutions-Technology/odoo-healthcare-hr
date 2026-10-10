from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.healthcare_hr_core.models.hr_employee import EMPLOYEE_CATEGORIES


class TrainingRequirement(models.Model):
    """One line of the Training Requirement Matrix.

    The scope is the intersection of the filled criteria (job, healthcare category, department);
    an empty criterion matches everybody. The certification itself is a credential type, so the
    credential record stays the single source of truth for validity and expiry.
    """
    _name = 'healthcare.training.requirement'
    _description = 'Training Requirement'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    job_id = fields.Many2one('hr.job', string='Job Position', index=True, check_company=True)
    employee_category = fields.Selection(EMPLOYEE_CATEGORIES, string='Healthcare Category', index=True)
    department_id = fields.Many2one(
        'hr.department', index=True, check_company=True,
        help="Administrative or medical (clinical) department of the employee.")
    credential_type_id = fields.Many2one(
        'healthcare.hr.credential.type', string='Certification', required=True, index=True, ondelete='restrict',
        help="Credential type renewed when the training is completed.")
    mandatory = fields.Boolean(default=True, help="Missing mandatory training raises alerts and appears in reports.")
    renewal_period_months = fields.Integer(
        string='Renewal Period (months)', default=24,
        help="Validity of the certification after completion. 0 = does not expire.")
    due_days = fields.Integer(string='Days to Complete', default=30,
                              help="Due date of a new assignment = assignment date + this number of days.")
    auto_verify_credential = fields.Boolean(
        string='Verify Credential on Completion',
        help="When set, the credential renewed by a completed training is marked verified immediately "
             "(internal or trusted provider). Otherwise it stays 'Under Verification' until an HR officer "
             "verifies the certificate.")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self: self.env.company)
    assignment_ids = fields.One2many('healthcare.training.assignment', 'requirement_id', string='Assignments')
    assignment_count = fields.Integer(compute='_compute_assignment_count')
    note = fields.Text()

    _renewal_positive = models.Constraint('CHECK (renewal_period_months >= 0)',
                                          'The renewal period cannot be negative.')

    def _compute_assignment_count(self):
        counts = dict(self.env['healthcare.training.assignment']._read_group(
            [('requirement_id', 'in', self.ids)], ['requirement_id'], ['__count']))
        for req in self:
            req.assignment_count = counts.get(req, 0)

    @api.constrains('due_days')
    def _check_due_days(self):
        if any(req.due_days < 0 for req in self):
            raise ValidationError(self.env._('The number of days to complete cannot be negative.'))

    def _applies_to(self, employee):
        """True when this requirement is in scope for ``employee``."""
        self.ensure_one()
        if not self.active or (self.company_id and employee.company_id != self.company_id):
            return False
        if self.job_id and employee.job_id != self.job_id:
            return False
        if self.employee_category and employee.employee_category != self.employee_category:
            return False
        if self.department_id and self.department_id not in (employee.department_id | employee.medical_department_id):
            return False
        return True

    def _expiry_from(self, completion_date):
        self.ensure_one()
        if not completion_date or not self.renewal_period_months:
            return False
        return completion_date + relativedelta(months=self.renewal_period_months)

    def action_view_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Training Assignments'),
            'res_model': 'healthcare.training.assignment',
            'view_mode': 'list,form',
            'domain': [('requirement_id', '=', self.id)],
            'context': {'default_requirement_id': self.id},
        }
