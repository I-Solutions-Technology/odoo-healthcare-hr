from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .hr_attendance import ATTENDANCE_STATUS


class AttendanceReconciliation(models.Model):
    """Shift + raw attendance + approved leave + public holidays + overtime policy
    -> reviewed lines -> approved work data (assignment state 'approved')."""
    _name = 'healthcare.attendance.reconciliation'
    _description = 'Attendance Reconciliation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'
    _check_company_auto = True

    name = fields.Char(default=lambda self: self.env._('New'), readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('healthcare.hr.branch', check_company=True)
    department_id = fields.Many2one('hr.department', check_company=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    line_ids = fields.One2many('healthcare.attendance.reconciliation.line', 'reconciliation_id', string='Lines')
    state = fields.Selection([('draft', 'Draft'), ('computed', 'To Review'), ('approved', 'Approved')],
                             default='draft', required=True, tracking=True)
    issue_count = fields.Integer(compute='_compute_counts')
    line_count = fields.Integer(compute='_compute_counts')
    approved_by = fields.Many2one('res.users', readonly=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New')) == self.env._('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('healthcare.attendance.reconciliation') or '/'
        return super().create(vals_list)

    @api.depends('line_ids.status')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.issue_count = len(rec.line_ids.filtered(lambda l: l.status not in ('present', 'on_leave')))

    def _assignment_domain(self):
        self.ensure_one()
        tz_margin = timedelta(hours=14)
        end = datetime.combine(self.date_to, time.max) + tz_margin
        domain = [('company_id', '=', self.company_id.id), ('date', '>=', self.date_from), ('date', '<=', self.date_to),
                  ('state', 'in', ('published', 'confirmed', 'working', 'completed')),
                  ('datetime_end', '<=', min(end, fields.Datetime.now()))]
        if self.branch_id:
            domain.append(('branch_id', 'child_of', self.branch_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        return domain

    def action_compute(self):
        """(Re)build the lines. Idempotent: lines of approved shifts are never touched."""
        Line = self.env['healthcare.attendance.reconciliation.line']
        for rec in self:
            if rec.state == 'approved':
                raise UserError(self.env._('%s is already approved.', rec.name))
            Assignment = self.env['healthcare.shift.assignment']
            domain = rec._assignment_domain()
            assignments = Assignment.search(domain)
            # conflicting (unpublished) shifts only matter when someone actually worked them
            conflict_domain = [d if not (isinstance(d, tuple) and d[0] == 'state') else ('state', '=', 'conflict')
                               for d in domain]
            assignments |= Assignment.search(conflict_domain + [('attendance_ids', '!=', False)])
            # other open batches must not reconcile the same shifts twice
            taken = Line.search([('assignment_id', 'in', assignments.ids), ('reconciliation_id', '!=', rec.id),
                                 ('reconciliation_id.state', '!=', 'draft')]).assignment_id
            assignments -= taken
            self._hc_link_orphan_attendances(assignments)
            assignments._hc_update_actuals()
            leaves = {}
            if assignments:
                for leave in self.env['hr.leave'].sudo().search([
                        ('employee_id', 'in', assignments.employee_id.ids), ('state', '=', 'validate'),
                        ('date_from', '<', max(assignments.mapped('datetime_end'))),
                        ('date_to', '>', min(assignments.mapped('datetime_start')))]):
                    leaves.setdefault(leave.employee_id.id, []).append((leave.date_from, leave.date_to))
            existing = {line.assignment_id.id: line for line in rec.line_ids}
            to_create = []
            for shift in assignments:
                status = shift._hc_reconcile_status(leaves)
                shift.attendance_status = status
                vals = {
                    'status': status,
                    'planned_hours': shift.planned_hours,
                    'worked_hours': shift.actual_worked_hours,
                    'late_minutes': shift.late_minutes,
                    'early_leave_minutes': shift.early_leave_minutes,
                    'extra_hours': shift.extra_hours,
                    'night_hours': shift.night_hours,
                    'weekend_hours': shift.weekend_hours,
                    'holiday_hours': shift.holiday_hours,
                }
                line = existing.pop(shift.id, None)
                if line:
                    if not line.approved_overtime_edited:
                        vals['approved_overtime_hours'] = shift._hc_proposed_overtime()
                    line.with_context(hc_system_write=True).write(vals)
                else:
                    vals.update(assignment_id=shift.id, reconciliation_id=rec.id,
                                approved_overtime_hours=shift._hc_proposed_overtime())
                    to_create.append(vals)
            Line.create(to_create)
            Line.browse([line.id for line in existing.values()]).unlink()
            rec.state = 'computed'
        return True

    def _hc_link_orphan_attendances(self, assignments):
        """Attendances created before their shift was published are matched now."""
        if not assignments:
            return
        orphans = self.env['hr.attendance'].sudo().search([
            ('employee_id', 'in', assignments.employee_id.ids), ('planned_shift_id', '=', False),
            ('check_in', '>=', min(assignments.mapped('datetime_start')) - timedelta(hours=12)),
            ('check_in', '<=', max(assignments.mapped('datetime_end'))),
        ])
        if orphans:
            orphans._compute_planned_shift_id()

    def action_approve(self):
        for rec in self:
            if rec.state != 'computed':
                raise UserError(self.env._('Compute the reconciliation before approving it.'))
            for line in rec.line_ids:
                shift = line.assignment_id
                approved = line.approved_overtime_hours if line.status not in ('absent', 'on_leave') else 0.0
                shift.write({
                    'overtime_hours': approved,
                    'payroll_overtime_hours': shift._hc_payroll_overtime(approved),
                    'attendance_status': line.status,
                    'state': 'approved',
                })
                shift.attendance_ids.write({'reconciliation_state': 'approved'})
            rec.write({'state': 'approved', 'approved_by': self.env.uid})
        return True

    def action_reset(self):
        for rec in self:
            shifts = rec.line_ids.assignment_id
            if shifts.filtered('payroll_processed'):
                raise UserError(self.env._('Some shifts are already in payroll; the batch cannot be reset.'))
            shifts.filtered(lambda s: s.state == 'approved').with_context(hc_allow_locked_write=True).write(
                {'state': 'completed', 'payroll_overtime_hours': 0.0})
            shifts.attendance_ids.write({'reconciliation_state': 'reconciled'})
            rec.state = 'draft'

    @api.model
    def _cron_reconcile_yesterday(self):
        """Create/refresh a reconciliation per company for yesterday (never approves)."""
        yesterday = fields.Date.context_today(self) - timedelta(days=1)
        for company in self.env['res.company'].search([]):
            rec = self.search([('company_id', '=', company.id), ('date_from', '=', yesterday),
                               ('date_to', '=', yesterday), ('branch_id', '=', False),
                               ('department_id', '=', False)], limit=1)
            if rec and rec.state == 'approved':
                continue
            rec = rec or self.create({'company_id': company.id, 'date_from': yesterday, 'date_to': yesterday})
            rec.action_compute()
            if rec.issue_count:
                self.env['healthcare.hr.alert'].schedule(
                    rec, 'reconciliation_issues',
                    self.env._('%(count)s attendance issue(s) to review for %(date)s', count=rec.issue_count, date=yesterday),
                    user=company.hc_alert_user_id or None)
        return True


class AttendanceReconciliationLine(models.Model):
    _name = 'healthcare.attendance.reconciliation.line'
    _description = 'Attendance Reconciliation Line'
    _order = 'date, employee_id'

    reconciliation_id = fields.Many2one('healthcare.attendance.reconciliation', required=True, ondelete='cascade', index=True)
    assignment_id = fields.Many2one('healthcare.shift.assignment', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='assignment_id.employee_id', store=True)
    department_id = fields.Many2one(related='assignment_id.department_id', store=True)
    branch_id = fields.Many2one(related='assignment_id.branch_id', store=True)
    date = fields.Date(related='assignment_id.date', store=True)
    shift_template_id = fields.Many2one(related='assignment_id.shift_template_id')
    status = fields.Selection(ATTENDANCE_STATUS, required=True)
    planned_hours = fields.Float(aggregator='sum')
    worked_hours = fields.Float(aggregator='sum')
    late_minutes = fields.Integer(aggregator='sum')
    early_leave_minutes = fields.Integer(aggregator='sum')
    extra_hours = fields.Float(string='Worked Extra Time', aggregator='sum')
    approved_overtime_hours = fields.Float(string='Approved Overtime', aggregator='sum')
    approved_overtime_edited = fields.Boolean(readonly=True)
    night_hours = fields.Float(aggregator='sum')
    weekend_hours = fields.Float(aggregator='sum')
    holiday_hours = fields.Float(aggregator='sum')
    note = fields.Char()

    _assignment_uniq = models.Constraint('unique (reconciliation_id, assignment_id)',
                                         'A shift appears once per reconciliation.')

    def write(self, vals):
        if 'approved_overtime_hours' in vals and not self.env.context.get('hc_system_write'):
            if self.reconciliation_id.filtered(lambda r: r.state == 'approved'):
                raise UserError(self.env._('The reconciliation is approved.'))
            vals['approved_overtime_edited'] = True
        res = super().write(vals)
        if 'approved_overtime_hours' in vals:
            for line in self:
                if line.approved_overtime_hours < 0 or line.approved_overtime_hours > line.extra_hours + 0.01:
                    raise UserError(self.env._(
                        'Approved overtime for %(name)s must be between 0 and the worked extra time (%(extra).2f h).',
                        name=line.employee_id.name, extra=line.extra_hours))
        return res


class AttendanceReconciliationDemo(models.Model):
    _inherit = 'healthcare.attendance.reconciliation'

    @api.model
    def _hc_load_demo_attendance(self):
        """Attendances for the past week's published shifts: on time, late, early, overtime, a missing
        checkout and one absence, then a computed (not approved) reconciliation."""
        today = fields.Date.context_today(self)
        shifts = self.env['healthcare.shift.assignment'].search([
            ('state', 'in', ('published', 'confirmed')), ('datetime_end', '<', fields.Datetime.now()),
            ('date', '>=', today - timedelta(days=7))], order='datetime_start')
        Attendance = self.env['hr.attendance']
        patterns = [(0, 0), (12, 0), (0, -25), (-5, 75), (0, 0), (35, 30)]
        for index, shift in enumerate(shifts):
            if index == 3:
                continue  # absence
            late, extra = patterns[index % len(patterns)]
            vals = {'employee_id': shift.employee_id.id,
                    'check_in': shift.datetime_start + timedelta(minutes=late)}
            if index != 5:  # one missing checkout
                vals['check_out'] = shift.datetime_end + timedelta(minutes=extra)
            Attendance.create(vals)
        rec = self.create({'date_from': today - timedelta(days=7), 'date_to': today - timedelta(days=1)})
        rec.action_compute()
        return rec
