from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.healthcare_hr_payroll.tests.common import PayrollCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestClearance(PayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.last_day = cls.monday + timedelta(days=2)
        cls.last_day = cls.last_day.replace(day=15) if cls.last_day.day > 15 else cls.last_day
        cls.nurse.hire_date = cls.last_day - timedelta(days=730)

    def _exit(self):
        return self.env['healthcare.hr.exit'].create({
            'employee_id': self.nurse.id, 'exit_reason': 'resignation', 'last_working_date': self.last_day})

    def _clear_all(self, exit_rec):
        exit_rec.clearance_item_ids.action_clear()

    def test_full_exit_flow(self):
        future_shift = self._shift(self.nurse, self.t_morning, self.last_day + timedelta(days=3), publish=True)
        loan = self.env['healthcare.hr.loan'].create({
            'employee_id': self.nurse.id, 'requested_amount': 3000, 'installment_count': 3,
            'first_deduction_date': self.last_day + timedelta(days=60)})
        loan.action_submit()
        loan.action_approve()
        loan.action_mark_paid()
        exit_rec = self._exit()
        exit_rec.action_start_clearance()
        self.assertEqual(exit_rec.state, 'clearance')
        self.assertEqual(self.nurse.employment_status, 'notice')
        self.assertEqual(len(exit_rec.clearance_item_ids), 7)
        it_item = exit_rec.clearance_item_ids.filtered(lambda i: i.clearance_department_id.code == 'MEDEQ')
        it_item.amount_due = 400
        exit_rec.clearance_item_ids[:-1].action_clear()
        self.assertEqual(exit_rec.state, 'clearance', "still one mandatory item pending")
        exit_rec.clearance_item_ids[-1:].action_clear()
        self.assertEqual(exit_rec.state, 'settlement')
        settlement = exit_rec.settlement_id
        settlement.action_compute()
        lines = {line.component_id.code: line.amount for line in settlement.line_ids}
        daily = 10000 / 30
        self.assertAlmostEqual(lines['FINAL_SALARY'], round(daily * self.last_day.day, 2), places=2)
        self.assertEqual(lines['LOANS'], -3000.0)
        self.assertEqual(lines['OBLIGATIONS'], -400.0)
        self.assertNotIn('EOS', lines, "end of service formula defaults to 0 until configured")
        with self.assertRaises(UserError):
            exit_rec.action_hr_approve()
        settlement.action_confirm()
        self.assertEqual(exit_rec.state, 'hr_approval')
        settlement.action_mark_paid()
        self.assertEqual(loan.state, 'completed')
        exit_rec.action_hr_approve()
        self.assertEqual(exit_rec.state, 'done')
        self.assertFalse(self.nurse.active)
        self.assertEqual(self.nurse.employment_status, 'exited')
        self.assertEqual(self.nurse.version_id.sudo().contract_date_end, self.last_day)
        self.assertEqual(future_shift.state, 'cancelled')

    def test_configurable_end_of_service(self):
        eos = self.env.ref('healthcare_hr_clearance.settlement_component_eos')
        eos.formula = "result = daily_wage * 15 * service_years if exit_reason != 'termination' else 0"
        exit_rec = self._exit()
        exit_rec.action_start_clearance()
        self._clear_all(exit_rec)
        exit_rec.settlement_id.action_compute()
        line = exit_rec.settlement_id.line_ids.filtered(lambda l: l.component_id == eos)
        service_years = round(((self.last_day - self.nurse.hire_date).days + 1) / 365.25, 4)
        self.assertAlmostEqual(line.amount, round(10000 / 30 * 15 * service_years, 2), places=2)

    def test_pending_inputs_in_settlement(self):
        self.Input.create({'name': 'Bonus', 'employee_id': self.nurse.id, 'source_type': 'bonus',
                           'date_from': self.date_from, 'date_to': self.date_to, 'amount': 700, 'state': 'confirmed'})
        exit_rec = self._exit()
        exit_rec.action_start_clearance()
        self._clear_all(exit_rec)
        settlement = exit_rec.settlement_id
        settlement.action_compute()
        self.assertEqual(settlement.line_ids.filtered(lambda l: l.component_id.code == 'BONUSES').amount, 700.0)
        settlement.action_confirm()
        settlement.action_mark_paid()
        self.assertEqual(self.Input.search([('employee_id', '=', self.nurse.id), ('source_type', '=', 'bonus')]).state, 'done')

    def test_block_requires_note_and_responsible(self):
        exit_rec = self._exit()
        exit_rec.action_start_clearance()
        item = exit_rec.clearance_item_ids[0]
        with self.assertRaises(UserError):
            item.action_block()
        stranger = self._user('stranger_clear', 'healthcare_hr_core.group_hc_user')
        item.responsible_user_id = self.env.user
        with self.assertRaises(Exception):
            item.with_user(stranger).action_clear()
