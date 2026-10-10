from odoo import api, fields, models
from odoo.exceptions import UserError


class OnboardingItemTemplate(models.Model):
    _name = 'healthcare.hr.onboarding.item.template'
    _description = 'Onboarding Checklist Item'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(required=True)
    responsible_role = fields.Selection([
        ('hr', 'HR'), ('department', 'Department Manager'), ('it', 'IT'),
        ('payroll', 'Payroll'), ('scheduling', 'Scheduling'), ('training', 'Training'),
    ], default='hr', required=True)
    mandatory = fields.Boolean(default=True)
    clinical_only = fields.Boolean(help="Only added for clinical employees (doctors, nurses, technicians).")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique (code)', 'The onboarding item code must be unique.')


class Onboarding(models.Model):
    _name = 'healthcare.hr.onboarding'
    _description = 'Employee Onboarding'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True, string='Branch')
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    start_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    responsible_id = fields.Many2one('res.users', default=lambda self: self.env.user, tracking=True)
    line_ids = fields.One2many('healthcare.hr.onboarding.line', 'onboarding_id', string='Checklist')
    progress = fields.Float(compute='_compute_progress', store=True, aggregator='avg')
    state = fields.Selection([
        ('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Completed'), ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True)

    @api.depends('employee_id')
    def _compute_name(self):
        for rec in self:
            rec.name = self.env._('Onboarding - %s', rec.employee_id.name or '')

    @api.depends('line_ids.done')
    def _compute_progress(self):
        for rec in self:
            lines = rec.line_ids
            rec.progress = 100.0 * len(lines.filtered('done')) / len(lines) if lines else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: not r.line_ids):
            rec._generate_lines()
        return records

    def _generate_lines(self):
        templates = self.env['healthcare.hr.onboarding.item.template'].search([])
        for rec in self:
            items = templates.filtered(lambda t: not t.clinical_only or rec.employee_id.is_clinical)
            rec.line_ids = [fields.Command.create({'template_id': t.id, 'name': t.name, 'sequence': t.sequence,
                                                   'mandatory': t.mandatory}) for t in items]

    def action_start(self):
        self.write({'state': 'in_progress'})
        self.employee_id.filtered(lambda e: e.employment_status == 'active').employment_status = 'onboarding'

    def action_done(self):
        for rec in self:
            missing = rec.line_ids.filtered(lambda l: l.mandatory and not l.done)
            if missing:
                raise UserError(self.env._('Mandatory onboarding items are still open: %s',
                                           ', '.join(missing.mapped('name'))))
        self.write({'state': 'done'})
        self.employee_id.filtered(lambda e: e.employment_status == 'onboarding').employment_status = 'active'

    def action_cancel(self):
        self.write({'state': 'cancel'})


class OnboardingLine(models.Model):
    _name = 'healthcare.hr.onboarding.line'
    _description = 'Onboarding Checklist Line'
    _order = 'sequence, id'

    onboarding_id = fields.Many2one('healthcare.hr.onboarding', required=True, ondelete='cascade', index=True)
    template_id = fields.Many2one('healthcare.hr.onboarding.item.template', ondelete='set null')
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    mandatory = fields.Boolean()
    done = fields.Boolean()
    done_by = fields.Many2one('res.users', readonly=True)
    done_date = fields.Date(readonly=True)
    note = fields.Char()

    def write(self, vals):
        if 'done' in vals:
            vals.update({'done_by': self.env.uid if vals['done'] else False,
                         'done_date': fields.Date.context_today(self) if vals['done'] else False})
        return super().write(vals)
