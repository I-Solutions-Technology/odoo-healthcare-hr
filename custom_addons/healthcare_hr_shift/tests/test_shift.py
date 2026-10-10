from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ShiftCommon
from ..models.shift_utils import get_tz, split_hours


@tagged('post_install', '-at_install', 'healthcare')
class TestShiftEngine(ShiftCommon):

    def test_valid_assignment_published_and_planning(self):
        shift = self._shift(self.nurse, self.t_morning, self.monday, publish=True)
        self.assertEqual(shift.state, 'published')
        self.assertFalse(shift.conflict_reason)
        self.assertTrue(shift.planning_slot_id, "published shift mirrored in Planning")
        self.assertEqual(shift.planning_slot_id.start_datetime, shift.datetime_start)
        self.assertEqual(shift.planned_hours, 7.5, "8h minus 30 min break")

    def test_cross_midnight_shift(self):
        shift = self._shift(self.nurse, self.t_night12, self.monday)
        self.assertEqual(shift.datetime_start, self._dt(self.monday, 20))
        self.assertEqual(shift.datetime_end, self._dt(self.monday + timedelta(days=1), 8))
        self.assertEqual(shift.night_hours, 8.0, "22:00-06:00 inside 20:00-08:00")

    def test_timezone_conversion(self):
        self.nurse.tz = 'Africa/Cairo'
        shift = self._shift(self.nurse, self.t_morning, self.monday)
        offset = get_tz('Africa/Cairo').utcoffset(self._dt(self.monday, 8)).total_seconds() / 3600
        self.assertEqual(shift.datetime_start, self._dt(self.monday, 8) - timedelta(hours=offset))

    def test_twelve_hour_shift(self):
        shift = self._shift(self.nurse, self.t_day12, self.monday, publish=True)
        self.assertEqual((shift.datetime_end - shift.datetime_start), timedelta(hours=12))
        self.assertEqual(shift.planned_hours, 11.0)
        self.assertEqual(shift.state, 'published')

    def test_twenty_four_hour_shift(self):
        shift = self._shift(self.doctor, self.t_24, self.monday, publish=True)
        self.assertEqual(shift.datetime_end - shift.datetime_start, timedelta(hours=24))
        self.assertEqual(shift.state, 'published')
        unauthorised = self._shift(self.nurse, self.t_24, self.monday + timedelta(days=2))
        with self.assertRaisesRegex(UserError, '24-hour'):
            unauthorised.action_publish()

    def test_overlapping_shifts(self):
        self._shift(self.nurse, self.t_day12, self.monday, publish=True)
        second = self._shift(self.nurse, self.t_morning, self.monday)
        with self.assertRaisesRegex(UserError, 'Overlaps'):
            second.action_publish()
        self.assertEqual(second.state, 'conflict')

    def test_duplicate_assignment(self):
        self._shift(self.nurse, self.t_morning, self.monday, publish=True)
        dup = self._shift(self.nurse, self.t_morning, self.monday)
        with self.assertRaisesRegex(UserError, 'Duplicate'):
            dup.action_publish()

    def test_two_branches_simultaneously(self):
        self._shift(self.nurse, self.t_morning, self.monday, publish=True)
        other = self.Shift.create({'employee_id': self.nurse.id, 'shift_template_id': self.t_day12.id,
                                   'date': self.monday, 'branch_id': self.branch_2.id})
        with self.assertRaisesRegex(UserError, 'branch'):
            other.action_publish()

    def test_minimum_rest_violation(self):
        self._shift(self.nurse, self.t_night12, self.monday, publish=True)  # ends Tue 08:00, rest 11h
        morning = self._shift(self.nurse, self.t_morning, self.monday + timedelta(days=1))  # wait: Tue 08:00 = 0h rest
        with self.assertRaisesRegex(UserError, 'rest'):
            morning.action_publish()

    def _approved_leave(self, day):
        leave_type = self.env['hr.leave.type'].create({
            'name': 'Test Leave', 'requires_allocation': False, 'leave_validation_type': 'hr'})
        leave = self.env['hr.leave'].sudo().create({
            'employee_id': self.nurse.id, 'holiday_status_id': leave_type.id,
            'request_date_from': day, 'request_date_to': day})
        leave.sudo().action_approve()
        self.assertEqual(leave.state, 'validate')
        return leave

    def test_leave_conflict(self):
        self._approved_leave(self.monday)
        shift = self._shift(self.nurse, self.t_morning, self.monday)
        with self.assertRaisesRegex(UserError, 'leave'):
            shift.action_publish()

    def test_leave_approved_after_publication_flags_shift(self):
        shift = self._shift(self.nurse, self.t_morning, self.monday + timedelta(days=1), publish=True)
        self._approved_leave(self.monday + timedelta(days=1))
        self.assertEqual(shift.state, 'conflict')
        self.assertIn('leave', shift.conflict_reason)

    def test_expired_credential_blocks(self):
        bls = self.env.ref('healthcare_hr_credentials.credential_type_bls')
        cred = self.env['healthcare.hr.credential'].search([('employee_id', '=', self.nurse.id),
                                                            ('credential_type_id', '=', bls.id)])
        cred.with_context(hc_keep_verification=True).write({'expiry_date': self.monday - timedelta(days=1),
                                                            'verified': True})
        shift = self._shift(self.nurse, self.t_morning, self.monday)
        with self.assertRaisesRegex(UserError, 'BLS'):
            shift.action_publish()

    def test_contract_expired_blocks(self):
        self.nurse.contract_date_end = self.monday - timedelta(days=1)
        shift = self._shift(self.nurse, self.t_morning, self.monday)
        with self.assertRaisesRegex(UserError, 'contract'):
            shift.action_publish()

    def test_weekly_hours_limit(self):
        self.company.hc_max_weekly_hours = 20
        self._shift(self.nurse, self.t_day12, self.monday, publish=True)
        second = self._shift(self.nurse, self.t_day12, self.monday + timedelta(days=2))
        with self.assertRaisesRegex(UserError, 'limit'):
            second.action_publish()

    def test_weekend_authorisation(self):
        self.nurse.weekend_work_allowed = False
        saturday = self.monday + timedelta(days=5)
        shift = self._shift(self.nurse, self.t_morning, saturday)
        with self.assertRaisesRegex(UserError, 'weekend'):
            shift.action_publish()

    def test_incompatible_pattern(self):
        self.t_morning.job_ids = self.job_doctor
        shift = self._shift(self.nurse, self.t_morning, self.monday)
        with self.assertRaisesRegex(UserError, 'qualified'):
            shift.action_publish()

    def test_batch_publish_partial(self):
        good = self._shift(self.nurse, self.t_morning, self.monday)
        bad = self._shift(self.nurse, self.t_morning, self.monday)
        result = (good | bad).action_publish()
        self.assertEqual({good.state, bad.state}, {'published', 'conflict'}, "one wins, the duplicate is flagged")
        self.assertEqual(result['params']['type'], 'warning')

    def test_force_publish_requires_manager_and_reason(self):
        shift = self._shift(self.nurse, self.t_24, self.monday)
        with self.assertRaises(UserError):
            shift.action_publish()
        with self.assertRaises(UserError):
            shift.action_force_publish()
        shift.override_reason = 'Mass casualty event'
        shift.action_force_publish()
        self.assertEqual(shift.state, 'published')

    def test_coverage_shortage(self):
        rule = self.env['healthcare.shift.coverage.rule'].create({
            'department_id': self.dept_icu.id, 'shift_template_id': self.t_night12.id,
            'employee_category': 'nurse', 'minimum_required': 2})
        self._shift(self.nurse, self.t_night12, self.monday, publish=True)
        snaps = self.env['healthcare.shift.coverage.rule']._refresh_snapshots(self.monday, self.monday, rule)
        self.assertEqual((snaps.assigned, snaps.shortage, snaps.status), (1, 1, 'short'))
        again = self.env['healthcare.shift.coverage.rule']._refresh_snapshots(self.monday, self.monday, rule)
        self.assertEqual(snaps, again, "snapshots are upserted, not duplicated")

    def test_publish_wizard_blocking_rule(self):
        self.env['healthcare.shift.coverage.rule'].create({
            'department_id': self.dept_icu.id, 'shift_template_id': self.t_night12.id,
            'employee_category': 'nurse', 'minimum_required': 3, 'block_publication': True})
        self._shift(self.nurse, self.t_night12, self.monday)
        wizard = self.env['healthcare.shift.publish.wizard'].create({
            'date_from': self.monday, 'date_to': self.monday, 'department_id': self.dept_icu.id})
        self.assertTrue(wizard.blocking)
        with self.assertRaisesRegex(UserError, 'blocked'):
            wizard.action_publish()

    def test_shift_swap(self):
        nurse2 = self.env['hr.employee'].create({
            'name': 'Nurse Two', 'job_id': self.job_nurse.id, 'department_id': self.dept_icu.id, 'tz': 'UTC',
            'contract_date_start': self.monday - relativedelta(years=1), 'wage': 9000})
        for cred in self.env['healthcare.hr.credential'].search([('employee_id', '=', self.nurse.id)]):
            cred.copy({'employee_id': nurse2.id, 'verified': True})
        give = self._shift(self.nurse, self.t_morning, self.monday, publish=True)
        take = self._shift(nurse2, self.t_morning, self.monday + timedelta(days=1), publish=True)
        swap = self.env['healthcare.shift.swap'].create({
            'requester_assignment_id': give.id, 'target_employee_id': nurse2.id,
            'target_assignment_id': take.id, 'reason': 'Family event'})
        swap.action_request()
        swap.action_accept()
        swap.action_manager_approve()
        swap.action_apply()
        self.assertEqual(swap.state, 'applied')
        self.assertEqual(give.employee_id, nurse2)
        self.assertEqual(take.employee_id, self.nurse)
        self.assertEqual(give.planning_slot_id.resource_id, nurse2.resource_id)

    def test_swap_rejects_unqualified_colleague(self):
        give = self._shift(self.nurse, self.t_morning, self.monday, publish=True)
        swap = self.env['healthcare.shift.swap'].create({
            'requester_assignment_id': give.id, 'target_employee_id': self.doctor.id, 'reason': 'x'})
        with self.assertRaisesRegex(UserError, 'category'):
            swap.action_request()

    def test_split_hours_weekend_holiday(self):
        saturday = self.monday + timedelta(days=5)
        start, end = self._dt(saturday, 20), self._dt(saturday + timedelta(days=1), 8)
        split = split_hours(start, end, get_tz('UTC'), 22, 6, (5, 6),
                            [(self._dt(saturday + timedelta(days=1), 0), self._dt(saturday + timedelta(days=2), 0))])
        self.assertEqual(split, {'night': 8.0, 'weekend': 12.0, 'holiday': 8.0})

    def test_oncall_hours(self):
        start = self._dt(self.monday, 20)
        oncall = self.env['healthcare.shift.oncall'].create({
            'employee_id': self.doctor.id, 'start_datetime': start, 'end_datetime': start + timedelta(hours=12),
            'called_in': True, 'actual_call_datetime': start + timedelta(hours=2),
            'call_end_datetime': start + timedelta(hours=5)})
        self.assertEqual((oncall.worked_hours, oncall.standby_hours), (3.0, 9.0))

    def test_generate_is_idempotent(self):
        created = self.Shift._hc_generate(self.nurse, self.t_morning, self.monday, self.monday + timedelta(days=4))
        self.assertEqual(len(created), 5)
        self.assertFalse(self.Shift._hc_generate(self.nurse, self.t_morning, self.monday, self.monday + timedelta(days=4)))

    def test_locked_after_approval(self):
        shift = self._shift(self.nurse, self.t_morning, self.monday, publish=True)
        shift.write({'state': 'completed'})
        shift.action_approve()
        with self.assertRaises(UserError):
            shift.write({'overtime_hours': 5})
        with self.assertRaises(UserError):
            shift.action_cancel()
