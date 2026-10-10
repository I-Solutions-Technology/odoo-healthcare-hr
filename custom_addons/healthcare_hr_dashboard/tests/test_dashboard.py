from odoo.tests import tagged

from odoo.addons.healthcare_hr_shift.tests.common import ShiftCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestDashboard(ShiftCommon):

    def test_kpis_and_drilldown(self):
        self._shift(self.nurse, self.t_morning, self.monday, publish=True)
        dash = self.env['healthcare.hr.dashboard'].create({'date': self.monday, 'branch_id': self.branch_1.id})
        self.assertEqual(dash.nurses, 1)
        self.assertEqual(dash.doctors, 0, "the doctor belongs to branch 2")
        self.assertEqual(dash.scheduled, 1)
        action = dash.with_context(kpi='scheduled').action_open_kpi()
        self.assertEqual(self.env[action['res_model']].search(action['domain']).employee_id, self.nurse)

    def test_payroll_tiles_hidden_for_non_payroll(self):
        user = self._user('dash_user', 'healthcare_hr_core.group_hc_user')
        dash = self.env['healthcare.hr.dashboard'].with_user(user).create({})
        self.assertFalse(dash.payroll_visible)
        self.assertEqual(dash.payroll_total, 0.0)
        self.assertEqual(dash.contracts_expiring, 0, "restricted contract dates degrade to 0, no crash")
