from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.healthcare_hr_shift.models.shift_assignment import ACTIVE_STATES
from odoo.addons.healthcare_hr_shift.models.shift_utils import get_tz, split_hours

ATTENDANCE_STATUS = [
    ('present', 'Present'),
    ('late', 'Late'),
    ('early_leave', 'Early Leave'),
    ('absent', 'Absent'),
    ('partial', 'Partial'),
    ('on_leave', 'On Leave'),
    ('missing_checkout', 'Missing Checkout'),
    ('unplanned', 'Unplanned'),
]


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    planned_shift_id = fields.Many2one(
        'healthcare.shift.assignment', string='Planned Shift', index='btree_not_null',
        compute='_compute_planned_shift_id', store=True, readonly=False,
        help="Shift this attendance is matched to. Computed from the check-in, can be corrected manually.")
    scheduled_start = fields.Datetime(related='planned_shift_id.datetime_start')
    scheduled_end = fields.Datetime(related='planned_shift_id.datetime_end')
    planned_hours = fields.Float(related='planned_shift_id.planned_hours')
    branch_id = fields.Many2one('healthcare.hr.branch', related='employee_id.healthcare_branch_id', store=True)
    late_minutes = fields.Integer(compute='_compute_shift_metrics', store=True, aggregator='sum')
    early_leave_minutes = fields.Integer(compute='_compute_shift_metrics', store=True, aggregator='sum')
    extra_time_hours = fields.Float(
        string='Extra Time vs Shift', compute='_compute_shift_metrics', store=True, aggregator='sum',
        help="Time worked outside the planned shift. The standard 'Worked Extra Hours' is computed against the "
             "working schedule; this one against the healthcare shift.")
    night_hours = fields.Float(compute='_compute_premium_hours', store=True, aggregator='sum')
    weekend_hours = fields.Float(compute='_compute_premium_hours', store=True, aggregator='sum')
    holiday_hours = fields.Float(compute='_compute_premium_hours', store=True, aggregator='sum')
    attendance_status = fields.Selection(ATTENDANCE_STATUS, compute='_compute_shift_metrics', store=True, index=True)
    reconciliation_state = fields.Selection([
        ('pending', 'Pending'), ('reconciled', 'Reconciled'), ('approved', 'Approved'), ('excluded', 'Excluded'),
    ], default='pending', index=True, copy=False)

    @api.depends('employee_id', 'check_in')
    def _compute_planned_shift_id(self):
        todo = self.filtered(lambda a: a.employee_id and a.check_in and a.reconciliation_state != 'approved')
        if not todo:
            return
        window = max(todo.mapped(lambda a: a.employee_id.company_id.hc_shift_match_window or 3.0))
        min_in, max_in = min(todo.mapped('check_in')), max(todo.mapped('check_in'))
        shifts = self.env['healthcare.shift.assignment'].sudo().search([
            ('employee_id', 'in', todo.employee_id.ids), ('state', 'in', ACTIVE_STATES + ('conflict',)),
            ('datetime_start', '<=', max_in + timedelta(hours=window)), ('datetime_end', '>', min_in),
        ])
        by_employee = {}
        for shift in shifts:
            by_employee.setdefault(shift.employee_id.id, []).append(shift)
        for att in todo:
            window_td = timedelta(hours=att.employee_id.company_id.hc_shift_match_window or 3.0)
            candidates = [s for s in by_employee.get(att.employee_id.id, [])
                          if s.datetime_start - window_td <= att.check_in < s.datetime_end]
            # closest planned start wins (back-to-back shifts)
            candidates.sort(key=lambda s: abs((s.datetime_start - att.check_in).total_seconds()))
            att.planned_shift_id = candidates[0] if candidates else False

    @api.depends('check_in', 'check_out', 'planned_shift_id.datetime_start', 'planned_shift_id.datetime_end',
                 'planned_shift_id.shift_template_id.grace_minutes')
    def _compute_shift_metrics(self):
        now = fields.Datetime.now()
        leaves = self._hc_leaves_by_employee()
        for att in self:
            shift = att.planned_shift_id
            company = att.employee_id.company_id
            late = early = 0
            extra = 0.0
            if shift and att.check_in:
                grace = shift.shift_template_id.grace_minutes or 0
                late_raw = (att.check_in - shift.datetime_start).total_seconds() / 60.0
                late = int(late_raw) if late_raw > grace else 0
                if att.check_out:
                    early_raw = (shift.datetime_end - att.check_out).total_seconds() / 60.0
                    early = int(early_raw) if early_raw > grace else 0
                    before = max((shift.datetime_start - att.check_in).total_seconds(), 0)
                    after = max((att.check_out - shift.datetime_end).total_seconds(), 0)
                    extra = round((before + after) / 3600.0, 2)
            att.late_minutes, att.early_leave_minutes, att.extra_time_hours = late, early, extra
            # status
            limit_hours = company.hc_missing_checkout_hours or 2.0
            if not att.check_out:
                deadline = (shift.datetime_end + timedelta(hours=limit_hours)) if shift \
                    else (att.check_in + timedelta(hours=16))
                status = 'missing_checkout' if now > deadline else ('late' if late else 'present')
            elif any(l_from < att.check_out and l_to > att.check_in for l_from, l_to in leaves.get(att.employee_id.id, [])):
                status = 'on_leave'
            elif not shift:
                status = 'unplanned'
            elif late and early:
                status = 'partial'
            elif late:
                status = 'late'
            elif early:
                status = 'early_leave'
            else:
                status = 'present'
            att.attendance_status = status

    def _hc_leaves_by_employee(self):
        records = self.filtered('check_in')
        if not records:
            return {}
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', records.employee_id.ids), ('state', '=', 'validate'),
            ('date_from', '<', max(records.mapped(lambda a: a.check_out or a.check_in))),
            ('date_to', '>', min(records.mapped('check_in'))),
        ])
        result = {}
        for leave in leaves:
            result.setdefault(leave.employee_id.id, []).append((leave.date_from, leave.date_to))
        return result

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_premium_hours(self):
        for att in self:
            if not att.check_in or not att.check_out:
                att.night_hours = att.weekend_hours = att.holiday_hours = 0.0
                continue
            company = att.employee_id.company_id
            split = split_hours(att.check_in, att.check_out, get_tz(att.employee_id.tz or company.partner_id.tz),
                                company.hc_night_start, company.hc_night_end, company._hc_weekend_days(),
                                company._hc_holiday_intervals(att.check_in, att.check_out))
            att.night_hours, att.weekend_hours, att.holiday_hours = split['night'], split['weekend'], split['holiday']

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.planned_shift_id._hc_update_actuals()
        return records

    def write(self, vals):
        old_shifts = self.planned_shift_id
        res = super().write(vals)
        if {'check_in', 'check_out', 'planned_shift_id', 'employee_id'} & set(vals):
            (old_shifts | self.planned_shift_id)._hc_update_actuals()
        return res

    @api.model
    def _cron_missing_checkout(self):
        """Refresh open attendances' status and alert (once) on missing checkouts."""
        open_atts = self.sudo().search([('check_out', '=', False),
                                        ('check_in', '>', fields.Datetime.now() - timedelta(days=7))])
        open_atts._compute_shift_metrics()
        Alert = self.env['healthcare.hr.alert']
        for att in open_atts.filtered(lambda a: a.attendance_status == 'missing_checkout'):
            # hr.attendance has no activities: the alert is raised on the employee
            Alert.schedule(att.employee_id, f'missing_checkout_{att.id}',
                           self.env._('Missing checkout on %s', att.check_in.date()),
                           note=self.env._('Complete the check-out time or correct the attendance.'))
        return True
