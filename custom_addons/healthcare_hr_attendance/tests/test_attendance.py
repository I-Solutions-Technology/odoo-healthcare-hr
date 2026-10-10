from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.healthcare_hr_shift.tests.common import ShiftCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcareAttendance(ShiftCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({'hc_overtime_min_minutes': 30, 'hc_overtime_rounding_minutes': 15,
                           'hc_overtime_auto_propose': True, 'hc_missing_checkout_hours': 2})
        # the shift must be in the past for reconciliation: use last week's Monday
        cls.day = cls.monday - timedelta(days=21)
        cls.Attendance = cls.env['hr.attendance']

    def _attend(self, shift, late=0, extra=0, checkout=True):
        vals = {'employee_id': shift.employee_id.id, 'check_in': shift.datetime_start + timedelta(minutes=late)}
        if checkout:
            vals['check_out'] = shift.datetime_end + timedelta(minutes=extra)
        return self.Attendance.create(vals)

    def test_on_time(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        att = self._attend(shift)
        self.assertEqual(att.planned_shift_id, shift)
        self.assertEqual((att.attendance_status, att.late_minutes, att.early_leave_minutes), ('present', 0, 0))
        self.assertEqual(shift.state, 'completed')
        self.assertEqual(shift.actual_worked_hours, 7.5, "8h on site minus 30 min unpaid break")

    def test_late_within_and_beyond_grace(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        self.assertEqual(self._attend(shift, late=5).late_minutes, 0, "inside 10 min grace")
        shift2 = self._shift(self.nurse, self.t_morning, self.day + timedelta(days=1), publish=True)
        att = self._attend(shift2, late=25)
        self.assertEqual((att.late_minutes, att.attendance_status), (25, 'late'))

    def test_early_checkout(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        att = self._attend(shift, extra=-40)
        self.assertEqual((att.early_leave_minutes, att.attendance_status), (40, 'early_leave'))

    def test_overtime_separation(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        self._attend(shift, extra=50)
        self.assertAlmostEqual(shift.extra_hours, 50 / 60, places=2)
        rec = self.env['healthcare.attendance.reconciliation'].create({'date_from': self.day, 'date_to': self.day})
        rec.action_compute()
        line = rec.line_ids.filtered(lambda l: l.assignment_id == shift)
        self.assertAlmostEqual(line.approved_overtime_hours, 50 / 60, places=2, msg="proposed = extra time")
        line.approved_overtime_hours = 0.5  # approver approves only 30 min
        rec.action_approve()
        self.assertEqual(shift.state, 'approved')
        self.assertAlmostEqual(shift.extra_hours, 50 / 60, places=2, msg="worked extra time kept")
        self.assertEqual(shift.overtime_hours, 0.5)
        self.assertEqual(shift.payroll_overtime_hours, 0.5)

    def test_overtime_below_threshold_not_proposed(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        self._attend(shift, extra=20)
        rec = self.env['healthcare.attendance.reconciliation'].create({'date_from': self.day, 'date_to': self.day})
        rec.action_compute()
        self.assertEqual(rec.line_ids.approved_overtime_hours, 0.0)

    def test_payroll_overtime_rounding(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        self.assertEqual(shift._hc_payroll_overtime(0.95), 0.75)

    def test_missing_checkout(self):
        shift = self._shift(self.nurse, self.t_morning, fields.Date.today() - timedelta(days=2), publish=True)
        att = self._attend(shift, checkout=False)
        att._compute_shift_metrics()
        self.assertEqual(att.attendance_status, 'missing_checkout')
        self.Attendance._cron_missing_checkout()
        self.Attendance._cron_missing_checkout()
        activities = self.env['mail.activity'].search([('res_model', '=', 'hr.employee'), ('res_id', '=', self.nurse.id),
                                                       ('summary', 'ilike', 'missing checkout')])
        self.assertEqual(len(activities), 1, "alerted once")

    def test_attendance_without_shift(self):
        att = self.Attendance.create({'employee_id': self.nurse.id, 'check_in': self._dt(self.day, 9),
                                      'check_out': self._dt(self.day, 12)})
        self.assertFalse(att.planned_shift_id)
        self.assertEqual(att.attendance_status, 'unplanned')

    def test_shift_across_midnight(self):
        shift = self._shift(self.nurse, self.t_night12, self.day, publish=True)
        att = self._attend(shift, late=15)
        self.assertEqual(att.planned_shift_id, shift)
        self.assertEqual(att.late_minutes, 15)
        self.assertEqual(att.night_hours, 8.0)
        self.assertEqual(shift.night_hours, 8.0)

    def test_absence_and_idempotent_reconciliation(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        rec = self.env['healthcare.attendance.reconciliation'].create({'date_from': self.day, 'date_to': self.day})
        rec.action_compute()
        rec.action_compute()
        lines = rec.line_ids.filtered(lambda l: l.assignment_id == shift)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.status, 'absent')
        rec.action_approve()
        self.assertEqual(shift.overtime_hours, 0.0)
