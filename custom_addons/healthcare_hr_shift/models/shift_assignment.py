import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from .shift_utils import get_tz, shift_interval, split_hours

_logger = logging.getLogger(__name__)

ASSIGNMENT_STATES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('confirmed', 'Confirmed'),
    ('working', 'Working'),
    ('completed', 'Completed'),
    ('conflict', 'Conflict'),
    ('approved', 'Approved'),
    ('payroll_posted', 'Payroll Posted'),
    ('cancelled', 'Cancelled'),
]
# States in which the assignment occupies the employee (used by validations and coverage)
ACTIVE_STATES = ('published', 'confirmed', 'working', 'completed', 'approved', 'payroll_posted')
LOCKED_STATES = ('approved', 'payroll_posted')


class ShiftAssignment(models.Model):
    _name = 'healthcare.shift.assignment'
    _description = 'Shift Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'datetime_start desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 compute='_compute_from_employee', store=True, readonly=False, precompute=True)
    branch_id = fields.Many2one('healthcare.hr.branch', index=True, check_company=True, tracking=True,
                                compute='_compute_from_employee', store=True, readonly=False, precompute=True)
    department_id = fields.Many2one('hr.department', index=True, check_company=True,
                                    compute='_compute_from_employee', store=True, readonly=False, precompute=True)
    unit_id = fields.Many2one('healthcare.hr.unit', index=True, check_company=True,
                              compute='_compute_from_employee', store=True, readonly=False, precompute=True)
    job_id = fields.Many2one('hr.job', compute='_compute_from_employee', store=True, readonly=False, precompute=True)
    employee_category = fields.Selection(related='employee_id.employee_category', store=True, string='Category')
    shift_template_id = fields.Many2one('healthcare.shift.template', required=True, index=True, tracking=True,
                                        check_company=True)
    shift_type = fields.Selection(related='shift_template_id.shift_type', store=True)
    date = fields.Date(required=True, index=True, tracking=True, help="Local date on which the shift starts.")
    datetime_start = fields.Datetime(compute='_compute_datetimes', store=True, readonly=False, index=True,
                                     precompute=True, tracking=True)
    datetime_end = fields.Datetime(compute='_compute_datetimes', store=True, readonly=False, index=True,
                                   precompute=True, tracking=True)
    planned_hours = fields.Float(compute='_compute_planned_hours', store=True, aggregator='sum')

    # Actuals (filled by attendance reconciliation)
    actual_check_in = fields.Datetime(readonly=True, copy=False)
    actual_check_out = fields.Datetime(readonly=True, copy=False)
    actual_worked_hours = fields.Float(readonly=True, copy=False, aggregator='sum')
    extra_hours = fields.Float(string='Worked Extra Time', readonly=True, copy=False, aggregator='sum',
                               help="Time worked beyond the planned hours (not necessarily payable).")
    overtime_hours = fields.Float(string='Approved Overtime', copy=False, tracking=True, aggregator='sum',
                                  help="Extra time approved as overtime.")
    payroll_overtime_hours = fields.Float(string='Payroll Overtime', readonly=True, copy=False, aggregator='sum',
                                          help="Approved overtime after the payroll rounding policy.")
    night_hours = fields.Float(compute='_compute_hour_split', store=True, aggregator='sum')
    weekend_hours = fields.Float(compute='_compute_hour_split', store=True, aggregator='sum')
    holiday_hours = fields.Float(compute='_compute_hour_split', store=True, aggregator='sum')

    state = fields.Selection(ASSIGNMENT_STATES, default='draft', required=True, index=True, tracking=True, copy=False)
    conflict_reason = fields.Text(copy=False, readonly=True)
    override_reason = fields.Char(copy=False, tracking=True,
                                  help="Justification when a scheduling manager publishes despite conflicts.")
    planning_slot_id = fields.Many2one('planning.slot', copy=False, readonly=True, index='btree_not_null')
    payroll_processed = fields.Boolean(copy=False, readonly=True, index=True)
    note = fields.Text()
    color = fields.Integer(related='shift_template_id.color')

    _check_dates = models.Constraint(
        'CHECK (datetime_end > datetime_start)', 'The shift must end after it starts.')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('employee_id', 'shift_template_id', 'date')
    def _compute_name(self):
        for rec in self:
            rec.name = f'{rec.employee_id.name or ""} - {rec.shift_template_id.name or ""} - {rec.date or ""}'

    @api.depends('employee_id')
    def _compute_from_employee(self):
        for rec in self:
            employee = rec.employee_id
            if not employee:
                rec.company_id = rec.company_id or self.env.company
                continue
            rec.company_id = employee.company_id
            rec.branch_id = rec.branch_id or employee.healthcare_branch_id
            rec.department_id = rec.department_id or employee.medical_department_id or employee.department_id
            rec.unit_id = rec.unit_id or employee.healthcare_unit_id
            rec.job_id = rec.job_id or employee.job_id

    def _get_tz(self):
        self.ensure_one()
        return get_tz(self.employee_id.tz or self.company_id.partner_id.tz or self.env.user.tz)

    @api.depends('date', 'shift_template_id', 'employee_id')
    def _compute_datetimes(self):
        for rec in self:
            template = rec.shift_template_id
            if not rec.date or not template:
                rec.datetime_start = rec.datetime_start or False
                rec.datetime_end = rec.datetime_end or False
                continue
            rec.datetime_start, rec.datetime_end = shift_interval(
                rec.date, template.start_time, template.duration_hours, rec._get_tz())

    @api.depends('datetime_start', 'datetime_end', 'shift_template_id.break_minutes')
    def _compute_planned_hours(self):
        for rec in self:
            if rec.datetime_start and rec.datetime_end:
                duration = (rec.datetime_end - rec.datetime_start).total_seconds() / 3600.0
                rec.planned_hours = max(duration - (rec.shift_template_id.break_minutes or 0) / 60.0, 0.0)
            else:
                rec.planned_hours = 0.0

    @api.depends('datetime_start', 'datetime_end', 'actual_check_in', 'actual_check_out', 'company_id')
    def _compute_hour_split(self):
        """Night/weekend/holiday hours: actual times once known, planned times before."""
        for rec in self:
            start = rec.actual_check_in or rec.datetime_start
            end = rec.actual_check_out or rec.datetime_end
            if not start or not end or end <= start:
                rec.night_hours = rec.weekend_hours = rec.holiday_hours = 0.0
                continue
            company = rec.company_id or self.env.company
            split = split_hours(start, end, rec._get_tz(), company.hc_night_start, company.hc_night_end,
                                company._hc_weekend_days(), company._hc_holiday_intervals(start, end))
            rec.night_hours, rec.weekend_hours, rec.holiday_hours = split['night'], split['weekend'], split['holiday']

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    def write(self, vals):
        if not self.env.context.get('hc_allow_locked_write'):
            protected = {'employee_id', 'shift_template_id', 'date', 'datetime_start', 'datetime_end', 'overtime_hours'}
            if protected & set(vals) and self.filtered(lambda r: r.state in LOCKED_STATES):
                raise UserError(self.env._('Approved or payroll-posted shifts cannot be modified. '
                                           'Reset them first (payroll-posted shifts cannot be reset).'))
        res = super().write(vals)
        if {'employee_id', 'datetime_start', 'datetime_end'} & set(vals):
            self.filtered('planning_slot_id')._sync_planning_slot()
        return res

    def unlink(self):
        if self.filtered(lambda r: r.state not in ('draft', 'cancelled', 'conflict')):
            raise UserError(self.env._('Only draft, conflicting or cancelled shifts can be deleted; cancel them first.'))
        self.planning_slot_id.sudo().unlink()
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_check(self):
        """Run the validation engine and store the result without changing the state."""
        issues = self.env['healthcare.shift.validator']._validate(self)
        for rec in self:
            rec.conflict_reason = '\n'.join(issues.get(rec.id, [])) or False
        return issues

    def action_publish(self):
        todo = self.filtered(lambda r: r.state in ('draft', 'conflict'))
        issues = todo.action_check()
        conflicting = todo.filtered(lambda r: r.id in issues)
        valid = todo - conflicting
        conflicting.write({'state': 'conflict'})
        valid.write({'state': 'published', 'conflict_reason': False})
        valid._sync_planning_slot()
        if len(self) == 1 and conflicting:
            raise UserError(self.env._('The shift cannot be published:\n%s', conflicting.conflict_reason))
        if conflicting:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'warning', 'sticky': True,
                    'title': self.env._('%(ok)s shift(s) published, %(ko)s in conflict',
                                        ok=len(valid), ko=len(conflicting)),
                    'message': self.env._('Open the "Conflict" filter to review the reasons.'),
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        return True

    def action_force_publish(self):
        """Scheduling manager override: publish despite conflicts, with a justification."""
        if not self.env.user.has_group('healthcare_hr_core.group_hc_scheduling_manager'):
            raise UserError(self.env._('Only scheduling managers can override conflicts.'))
        for rec in self.filtered(lambda r: r.state in ('draft', 'conflict')):
            if not rec.override_reason:
                raise UserError(self.env._('Enter an override reason for %s.', rec.name))
            rec.message_post(body=self.env._('Published despite conflicts: %(reason)s\n%(conflicts)s',
                                             reason=rec.override_reason, conflicts=rec.conflict_reason or ''))
            rec.write({'state': 'published'})
            rec._sync_planning_slot()

    def action_confirm(self):
        self.filtered(lambda r: r.state == 'published').write({'state': 'confirmed'})

    def action_cancel(self):
        if self.filtered(lambda r: r.state in LOCKED_STATES):
            raise UserError(self.env._('Approved or payroll-posted shifts cannot be cancelled.'))
        self.write({'state': 'cancelled'})
        self.planning_slot_id.sudo().unlink()

    def action_draft(self):
        self.filtered(lambda r: r.state in ('conflict', 'cancelled', 'published', 'confirmed')).write(
            {'state': 'draft'})

    def action_approve(self):
        for rec in self:
            if rec.state not in ('completed', 'working', 'confirmed', 'published'):
                raise UserError(self.env._('Only worked shifts can be approved (%s).', rec.name))
        self.write({'state': 'approved'})

    def action_reset_approval(self):
        if self.filtered(lambda r: r.state == 'payroll_posted' or r.payroll_processed):
            raise UserError(self.env._('Shifts already sent to payroll cannot be reset.'))
        self.filtered(lambda r: r.state == 'approved').with_context(hc_allow_locked_write=True).write(
            {'state': 'completed'})

    # ------------------------------------------------------------------
    # Planning integration
    # ------------------------------------------------------------------
    def _prepare_planning_slot_vals(self):
        self.ensure_one()
        return {
            'resource_id': self.employee_id.resource_id.id,
            'start_datetime': self.datetime_start,
            'end_datetime': self.datetime_end,
            'company_id': self.company_id.id,
            'name': self.shift_template_id.name,
            'state': 'published',
        }

    def _sync_planning_slot(self):
        """Mirror published shifts in Odoo Planning (Gantt). sudo: schedulers are not planning managers."""
        Slot = self.env['planning.slot'].sudo()
        for rec in self:
            if rec.state in ('draft', 'cancelled', 'conflict'):
                continue
            vals = rec._prepare_planning_slot_vals()
            try:
                if rec.planning_slot_id:
                    rec.planning_slot_id.sudo().write(vals)
                else:
                    rec.planning_slot_id = Slot.create(vals)
            except Exception as error:  # planning must never block a roster
                _logger.warning('Planning sync failed for shift %s: %s', rec.id, error)

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------
    @api.model
    def _hc_generate(self, employees, template, date_from, date_to, weekdays=None):
        """Create draft assignments for each employee and day (skips existing duplicates)."""
        existing = {(a.employee_id.id, a.date) for a in self.search([
            ('employee_id', 'in', employees.ids), ('shift_template_id', '=', template.id),
            ('date', '>=', date_from), ('date', '<=', date_to), ('state', '!=', 'cancelled')])}
        vals_list = []
        day = date_from
        while day <= date_to:
            if weekdays is None or day.weekday() in weekdays:
                for employee in employees:
                    if (employee.id, day) not in existing:
                        vals_list.append({'employee_id': employee.id, 'shift_template_id': template.id, 'date': day})
            day = fields.Date.add(day, days=1)
        return self.create(vals_list)

    @api.model
    def _hc_load_demo_roster(self):
        """Demo roster: past week (to be reconciled) and next week, published through the engine."""
        ref = self.env.ref
        today = fields.Date.context_today(self)
        start, end = fields.Date.subtract(today, days=7), fields.Date.add(today, days=7)
        tmpl = lambda xmlid: ref(f'healthcare_hr_shift.shift_template_{xmlid}')  # noqa: E731
        emp = lambda xmlid: ref(f'healthcare_hr_core.demo_emp_{xmlid}')  # noqa: E731
        plan = [
            (emp('nurse_mona'), tmpl('day12'), (0, 1, 2)),
            (emp('nurse_hala'), tmpl('night12'), (0, 2, 4)),
            (emp('nurse_mona'), tmpl('night12'), (4, 5)),
            (emp('nurse_omar'), tmpl('morning'), (0, 1, 2, 3, 6)),
            (emp('nurse_laila'), tmpl('morning'), (0, 1, 2, 3, 6)),
            (emp('dr_ahmed'), tmpl('h24'), (1, 4)),
            (emp('dr_sara'), tmpl('day12'), (0, 2, 3)),
            (emp('pharm_karim'), tmpl('morning'), (0, 1, 2, 3, 6)),
            (emp('lab_yasmin'), tmpl('evening'), (0, 1, 2, 3)),
            (emp('rad_tarek'), tmpl('morning'), (0, 1, 2, 3)),
        ]
        created = self.browse()
        for employee, template, weekdays in plan:
            created |= self._hc_generate(employee, template, start, end, set(weekdays))
        created.action_publish()
        self.env['healthcare.shift.coverage.rule']._refresh_snapshots(today, end)
        self.env['healthcare.shift.oncall'].create({
            'employee_id': emp('dr_sara').id,
            'start_datetime': fields.Datetime.subtract(fields.Datetime.now(), days=2, hours=4),
            'end_datetime': fields.Datetime.subtract(fields.Datetime.now(), days=1, hours=16),
            'called_in': True,
            'actual_call_datetime': fields.Datetime.subtract(fields.Datetime.now(), days=2, hours=1),
            'call_end_datetime': fields.Datetime.subtract(fields.Datetime.now(), days=1, hours=22),
            'state': 'done',
        })
        return created
