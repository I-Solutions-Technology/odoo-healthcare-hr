from odoo.tests import tagged

from .common import PayrollCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcarePayroll(PayrollCommon):

    def test_overtime_input(self):
        shift = self._approved_shift(self.nurse, self.t_morning, self.day, overtime=2.0)
        inputs = self.Input._generate_for_period(self.date_from, self.date_to)
        overtime = inputs.filtered(lambda i: i.source_type == 'overtime' and i.employee_id == self.nurse)
        self.assertEqual(overtime.amount, 2.0 * 10000 / 200 * 1.5)
        self.assertEqual((overtime.source_model, overtime.source_res_id), (shift._name, shift.id),
                         "source linkage")
        self.assertEqual(overtime.processing_key, f'overtime:{shift.id}')

    def test_no_duplicate_generation(self):
        self._approved_shift(self.nurse, self.t_morning, self.day, overtime=1.0)
        first = self.Input._generate_for_period(self.date_from, self.date_to)
        second = self.Input._generate_for_period(self.date_from, self.date_to)
        self.assertEqual(first, second)
        self.assertEqual(self.Input.search_count([('employee_id', '=', self.nurse.id)]), 1)

    def test_allowance_input(self):
        rule = self.env['healthcare.allowance.rule'].create({
            'name': 'Night T', 'type_id': self.env.ref('healthcare_hr_allowance.allowance_type_night').id,
            'calculation_method': 'per_hour', 'hour_basis': 'night_hours', 'amount': 10})
        self._approved_shift(self.nurse, self.t_night12, self.day)
        result = self.env['healthcare.allowance.rule']._compute_period(self.date_from, self.date_to).filtered(
            lambda r: r.rule_id == rule)
        self.assertFalse(self.Input._generate_for_period(self.date_from, self.date_to).filtered(
            lambda i: i.source_model == result._name), "draft allowances are not sent to payroll")
        result.action_confirm()
        allowance_input = self.Input._generate_for_period(self.date_from, self.date_to).filtered(
            lambda i: i.source_model == result._name)
        self.assertEqual(allowance_input.amount, 80.0)
        self.assertEqual(allowance_input.input_type_id.code, 'HC_NIGHT')

    def test_payslip_integration_and_lifecycle(self):
        shift = self._approved_shift(self.nurse, self.t_morning, self.day, overtime=2.0)
        bonus = self.Input.create({'name': 'Bonus', 'employee_id': self.nurse.id, 'source_type': 'bonus',
                                   'date_from': self.date_from, 'date_to': self.date_to, 'amount': 500})
        self.assertEqual(bonus.state, 'draft', "manual inputs need approval")
        bonus.action_confirm()
        deduction = self.Input.create({'name': 'Damage', 'employee_id': self.nurse.id, 'source_type': 'deduction',
                                       'date_from': self.date_from, 'date_to': self.date_to, 'amount': 200,
                                       'state': 'confirmed'})
        overtime = self.Input._generate_for_period(self.date_from, self.date_to)
        slip = self._payslip(self.nurse)
        codes = {line.code: line.amount for line in slip.input_line_ids}
        self.assertEqual(codes.get('HC_OVERTIME'), 150.0)
        self.assertEqual(codes.get('HC_BONUS'), 500.0)
        self.assertEqual(codes.get('HC_DED'), 200.0)
        lines = {line.code: line.total for line in slip.line_ids}
        self.assertEqual(lines.get('HC_OVERTIME'), 150.0)
        self.assertEqual(lines.get('HC_DED'), -200.0)
        self.assertEqual((overtime | bonus | deduction).mapped('payslip_id'), slip)
        # a second payslip in the same period cannot take them again
        slip2 = self._payslip(self.nurse)
        self.assertFalse(slip2.input_line_ids.filtered(lambda l: l.code.startswith('HC_')))
        slip.action_payslip_done()
        self.assertEqual(set((overtime | bonus).mapped('state')), {'done'})
        self.assertTrue(shift.payroll_processed)
        self.assertEqual(shift.state, 'payroll_posted')
        slip.action_payslip_cancel()
        self.assertEqual(set((overtime | bonus).mapped('state')), {'confirmed'})
        self.assertFalse(shift.payroll_processed)
        self.assertEqual(shift.state, 'approved')

    def test_structure_rules_idempotent(self):
        count = len(self.structure.rule_ids)
        self.structure.action_hc_add_healthcare_rules()
        self.assertEqual(len(self.structure.rule_ids), count)

    def test_department_manager_has_no_payroll_access(self):
        manager = self._user('hc_dept_mgr_pay', 'healthcare_hr_core.group_hc_department_manager')
        self.assertFalse(self.env['healthcare.payroll.input'].with_user(manager).has_access('read'))
