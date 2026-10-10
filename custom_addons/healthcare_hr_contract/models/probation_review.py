from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProbationReview(models.Model):
    _name = 'healthcare.hr.probation.review'
    _description = 'Probation Review'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'review_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    version_id = fields.Many2one('hr.version', string='Contract', required=True, index=True, check_company=True,
                                 domain="[('employee_id', '=', employee_id)]")
    contract_id = fields.Many2one(related='version_id', string='Contract (alias)')
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    review_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    probation_end_date = fields.Date(compute='_compute_probation_end_date')
    reviewer_id = fields.Many2one('hr.employee', string='Reviewer', tracking=True)
    score = fields.Float(tracking=True, help="Overall score out of 100. Informative only.")
    attendance_score = fields.Float()
    competency_score = fields.Float()
    conduct_score = fields.Float()
    recommendation = fields.Selection([
        ('pass', 'Confirm Employment'),
        ('extend', 'Extend Probation'),
        ('terminate', 'Recommend Termination'),
    ], tracking=True)
    extension_end_date = fields.Date(string='New Probation End', tracking=True)
    comments = fields.Html()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    approved_by = fields.Many2one('res.users', readonly=True, tracking=True)

    @api.depends('employee_id', 'review_date')
    def _compute_name(self):
        for review in self:
            review.name = self.env._('Probation review - %(name)s (%(date)s)',
                                     name=review.employee_id.name or '', date=review.review_date or '')

    @api.depends('version_id')
    def _compute_probation_end_date(self):
        for review in self:
            review.probation_end_date = review.version_id.sudo().trial_date_end

    @api.constrains('score', 'attendance_score', 'competency_score', 'conduct_score')
    def _check_scores(self):
        for review in self:
            for value in (review.score, review.attendance_score, review.competency_score, review.conduct_score):
                if value < 0 or value > 100:
                    raise ValidationError(self.env._('Scores must be between 0 and 100.'))

    @api.onchange('attendance_score', 'competency_score', 'conduct_score')
    def _onchange_sub_scores(self):
        parts = [s for s in (self.attendance_score, self.competency_score, self.conduct_score) if s]
        if parts:
            self.score = sum(parts) / len(parts)

    def action_submit(self):
        for review in self:
            if not review.recommendation:
                raise UserError(self.env._('Select a recommendation before submitting.'))
            if review.recommendation == 'extend' and not review.extension_end_date:
                raise UserError(self.env._('Set the new probation end date for an extension.'))
        self.write({'state': 'submitted'})
        self.version_id.sudo().write({'probation_status': 'reviewed'})

    def action_approve(self):
        """Apply the recommendation. Termination is never automatic: it only flags the
        contract and asks HR to open an exit process."""
        for review in self:
            if review.state != 'submitted':
                raise UserError(self.env._('Only submitted reviews can be approved.'))
            version = review.version_id.sudo()
            if review.recommendation == 'pass':
                version.probation_status = 'passed'
                review.employee_id.sudo().employment_status = 'active'
            elif review.recommendation == 'extend':
                version.write({'probation_status': 'extended', 'trial_date_end': review.extension_end_date})
            else:
                version.probation_status = 'terminate_recommended'
                self.env['healthcare.hr.alert'].schedule(
                    review.employee_id, f'probation_terminate_{review.id}',
                    self.env._('Termination recommended after probation: %s', review.employee_id.name),
                    note=self.env._('Decide on the recommendation and, if confirmed, start the exit process.'))
            review.write({'state': 'approved', 'approved_by': self.env.uid})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})
