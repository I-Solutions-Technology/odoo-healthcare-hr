from odoo import api, fields, models

from .hr_attendance import ATTENDANCE_STATUS


class ShiftAssignment(models.Model):
    _inherit = 'healthcare.shift.assignment'

    attendance_ids = fields.One2many('hr.attendance', 'planned_shift_id', string='Attendances')
    attendance_status = fields.Selection(ATTENDANCE_STATUS, readonly=True, copy=False, index=True)
    late_minutes = fields.Integer(readonly=True, copy=False, aggregator='sum')
    early_leave_minutes = fields.Integer(readonly=True, copy=False, aggregator='sum')

    def _hc_update_actuals(self):
        """Aggregate linked attendances into the shift actuals (idempotent)."""
        for shift in self.sudo():
            if shift.state in ('approved', 'payroll_posted', 'cancelled'):
                continue
            atts = shift.attendance_ids.sorted('check_in')
            vals = {'actual_check_in': False, 'actual_check_out': False, 'actual_worked_hours': 0.0,
                    'extra_hours': 0.0, 'late_minutes': 0, 'early_leave_minutes': 0}
            if atts:
                closed = atts.filtered('check_out')
                # Raw time on site minus the shift's unpaid break. The standard worked_hours is not
                # used: it deducts the working-schedule lunch break, meaningless for 24/7 shifts.
                break_hours = (shift.shift_template_id.break_minutes or 0) / 60.0
                on_site = sum((a.check_out - a.check_in).total_seconds() / 3600.0 for a in closed)
                worked = max(on_site - break_hours, 0.0)
                vals.update({
                    'actual_check_in': atts[0].check_in,
                    'actual_check_out': closed and max(closed.mapped('check_out')) or False,
                    'actual_worked_hours': round(worked, 2),
                    # extra time = time worked outside the planned interval
                    'extra_hours': round(sum(atts.mapped('extra_time_hours')), 2),
                    'late_minutes': atts[0].late_minutes,
                    'early_leave_minutes': atts[-1].early_leave_minutes,
                })
                if shift.state in ('published', 'confirmed', 'working', 'completed'):
                    vals['state'] = 'completed' if atts[-1].check_out else 'working'
                statuses = set(atts.mapped('attendance_status'))
                vals['attendance_status'] = next(
                    (s for s in ('missing_checkout', 'on_leave', 'partial', 'late', 'early_leave') if s in statuses),
                    'present')
            shift.write(vals)

    def _hc_reconcile_status(self, leaves_by_employee):
        """Status of a finished shift without attendance: absent or on leave."""
        self.ensure_one()
        if self.attendance_ids:
            return self.attendance_status
        for date_from, date_to in leaves_by_employee.get(self.employee_id.id, []):
            if date_from < self.datetime_end and date_to > self.datetime_start:
                return 'on_leave'
        return 'absent'

    def _hc_proposed_overtime(self):
        """Approved overtime proposal: extra time above the company threshold on shifts allowing overtime."""
        self.ensure_one()
        company = self.company_id
        if not company.hc_overtime_auto_propose or not self.shift_template_id.overtime_allowed:
            return 0.0
        if self.extra_hours * 60 < (company.hc_overtime_min_minutes or 0):
            return 0.0
        return self.extra_hours

    def _hc_payroll_overtime(self, approved_hours):
        step = (self.company_id.hc_overtime_rounding_minutes or 0) / 60.0
        if not step:
            return round(approved_hours, 2)
        return round(int(approved_hours / step + 1e-9) * step, 2)
