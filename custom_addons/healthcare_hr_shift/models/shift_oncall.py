from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ShiftOncall(models.Model):
    _name = 'healthcare.shift.oncall'
    _description = 'On-Call Duty'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    department_id = fields.Many2one('hr.department', check_company=True, compute='_compute_org', store=True,
                                    readonly=False, precompute=True)
    branch_id = fields.Many2one('healthcare.hr.branch', check_company=True, compute='_compute_org', store=True,
                                readonly=False, precompute=True)
    employee_category = fields.Selection(related='employee_id.employee_category', store=True)
    start_datetime = fields.Datetime(required=True, tracking=True)
    end_datetime = fields.Datetime(required=True, tracking=True)
    standby_hours = fields.Float(compute='_compute_hours', store=True, aggregator='sum')
    called_in = fields.Boolean(tracking=True)
    actual_call_datetime = fields.Datetime(string='Called In At', tracking=True)
    call_end_datetime = fields.Datetime(string='Call Ended At', tracking=True)
    worked_hours = fields.Float(compute='_compute_hours', store=True, aggregator='sum')
    currency_id = fields.Many2one(related='company_id.currency_id')
    allowance_amount = fields.Monetary(readonly=True, copy=False, aggregator='sum',
                                       help="Computed by the allowance engine.")
    state = fields.Selection([
        ('draft', 'Draft'), ('scheduled', 'Scheduled'), ('done', 'Done'), ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    payroll_processed = fields.Boolean(readonly=True, copy=False)

    @api.depends('employee_id', 'start_datetime')
    def _compute_name(self):
        for rec in self:
            rec.name = self.env._('On-call %(name)s %(date)s', name=rec.employee_id.name or '',
                                  date=rec.start_datetime and rec.start_datetime.date() or '')

    @api.depends('employee_id')
    def _compute_org(self):
        for rec in self:
            rec.department_id = rec.department_id or rec.employee_id.department_id
            rec.branch_id = rec.branch_id or rec.employee_id.healthcare_branch_id

    @api.depends('start_datetime', 'end_datetime', 'called_in', 'actual_call_datetime', 'call_end_datetime')
    def _compute_hours(self):
        for rec in self:
            standby = ((rec.end_datetime - rec.start_datetime).total_seconds() / 3600.0
                       if rec.start_datetime and rec.end_datetime else 0.0)
            worked = 0.0
            if rec.called_in and rec.actual_call_datetime and rec.call_end_datetime:
                worked = max((rec.call_end_datetime - rec.actual_call_datetime).total_seconds() / 3600.0, 0.0)
            rec.standby_hours = max(standby - worked, 0.0)
            rec.worked_hours = worked

    @api.constrains('start_datetime', 'end_datetime', 'actual_call_datetime', 'call_end_datetime')
    def _check_dates(self):
        for rec in self:
            if rec.end_datetime <= rec.start_datetime:
                raise ValidationError(self.env._('The on-call period must end after it starts.'))
            if rec.actual_call_datetime and rec.call_end_datetime and rec.call_end_datetime <= rec.actual_call_datetime:
                raise ValidationError(self.env._('The call must end after it starts.'))

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_done(self):
        for rec in self:
            if rec.called_in and not (rec.actual_call_datetime and rec.call_end_datetime):
                raise UserError(self.env._('Enter the call-in times of %s.', rec.name))
        self.write({'state': 'done'})

    def action_approve(self):
        self.filtered(lambda r: r.state == 'done').write({'state': 'approved'})

    def action_cancel(self):
        if self.filtered('payroll_processed'):
            raise UserError(self.env._('On-call duties sent to payroll cannot be cancelled.'))
        self.write({'state': 'cancelled'})
