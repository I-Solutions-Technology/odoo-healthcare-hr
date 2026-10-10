from datetime import timedelta

from odoo.tests import tagged

from odoo.addons.healthcare_hr_shift.tests.common import ShiftCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestAllowances(ShiftCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.day = cls.monday - timedelta(days=28)   # a past Monday
        cls.date_from, cls.date_to = cls.day, cls.day + timedelta(days=6)
        cls.Rule = cls.env['healthcare.allowance.rule']
        cls.Type = cls.env['healthcare.allowance.type']
        # isolate from demo rules
        cls.Rule.search([]).write({'active': False})
        cls.t_night_type = cls.env.ref('healthcare_hr_allowance.allowance_type_night')

    def _worked(self, employee, template, day):
        shift = self._shift(employee, template, day, publish=True)
        shift.write({'state': 'approved', 'actual_check_in': shift.datetime_start,
                     'actual_check_out': shift.datetime_end, 'actual_worked_hours': shift.planned_hours})
        return shift

    def _rule(self, **vals):
        vals.setdefault('name', 'Test rule')
        vals.setdefault('type_id', self.t_night_type.id)
        return self.Rule.create(vals)

    def _result(self, rule, employee=None):
        return self.env['healthcare.allowance.result'].search([
            ('rule_id', '=', rule.id), ('employee_id', '=', (employee or self.nurse).id),
            ('date_from', '=', self.date_from)])

    def test_per_hour_night(self):
        rule = self._rule(calculation_method='per_hour', hour_basis='night_hours', amount=10)
        self._worked(self.nurse, self.t_night12, self.day)                       # 8 night hours
        self._worked(self.nurse, self.t_night12, self.day + timedelta(days=2))   # 8 night hours
        self.Rule._compute_period(self.date_from, self.date_to)
        self.assertEqual(self._result(rule).amount, 160.0)

    def test_per_shift_weekend(self):
        rule = self._rule(calculation_method='per_shift', shift_basis='weekend', amount=150,
                          type_id=self.env.ref('healthcare_hr_allowance.allowance_type_weekend').id)
        self._worked(self.nurse, self.t_morning, self.day)                        # Monday
        self._worked(self.nurse, self.t_morning, self.day + timedelta(days=5))    # Saturday
        self.Rule._compute_period(self.date_from, self.date_to)
        result = self._result(rule)
        self.assertEqual((result.quantity, result.amount), (1.0, 150.0))

    def test_per_shift_department_and_maximum(self):
        rule = self._rule(calculation_method='per_shift', shift_basis='all', amount=100, maximum=150,
                          department_id=self.dept_icu.id)
        for offset in (0, 1, 2):
            self._worked(self.nurse, self.t_morning, self.day + timedelta(days=offset))
        self.Rule._compute_period(self.date_from, self.date_to)
        self.assertEqual(self._result(rule).amount, 150.0, "3 x 100 capped at 150")

    def test_percentage_basic_and_gross(self):
        basic = self._rule(calculation_method='percentage_basic', percentage=10, sequence=1)
        gross = self._rule(calculation_method='percentage_gross', percentage=5, sequence=2)
        self.Rule._compute_period(self.date_from, self.date_to, employees=self.nurse)
        self.assertEqual(self._result(basic).amount, 1000.0)
        self.assertEqual(self._result(gross).amount, 550.0, "5% of (10000 + 1000)")

    def test_category_filter_and_minimum(self):
        rule = self._rule(calculation_method='fixed', amount=50, minimum=80, employee_category='doctor')
        self.Rule._compute_period(self.date_from, self.date_to, employees=self.nurse | self.doctor)
        self.assertFalse(self._result(rule, self.nurse))
        self.assertEqual(self._result(rule, self.doctor).amount, 80.0)

    def test_formula(self):
        rule = self._rule(calculation_method='formula',
                          formula="result = shifts.get('night', 0) * 40 + wage * 0.001")
        self._worked(self.nurse, self.t_night12, self.day)
        self.Rule._compute_period(self.date_from, self.date_to)
        self.assertEqual(self._result(rule).amount, 50.0)

    def test_idempotent_and_only_approved(self):
        rule = self._rule(calculation_method='per_hour', hour_basis='night_hours', amount=10)
        self._worked(self.nurse, self.t_night12, self.day)
        not_approved = self._shift(self.nurse, self.t_night12, self.day + timedelta(days=2), publish=True)
        self.Rule._compute_period(self.date_from, self.date_to)
        first = self._result(rule)
        self.Rule._compute_period(self.date_from, self.date_to)
        self.assertEqual(self._result(rule), first, "same record, no duplicate")
        self.assertEqual(first.amount, 80.0, "published-only shift ignored")
        first.action_confirm()
        first.state = 'processed'
        not_approved.write({'state': 'approved'})
        self.Rule._compute_period(self.date_from, self.date_to)
        self.assertEqual(first.amount, 80.0, "results already in payroll are never changed")

    def test_oncall_allowance(self):
        rule = self._rule(calculation_method='per_hour', hour_basis='oncall_worked_hours', amount=80,
                          type_id=self.env.ref('healthcare_hr_allowance.allowance_type_callin').id)
        start = self._dt(self.day, 20)
        oncall = self.env['healthcare.shift.oncall'].create({
            'employee_id': self.doctor.id, 'start_datetime': start, 'end_datetime': start + timedelta(hours=12),
            'called_in': True, 'actual_call_datetime': start + timedelta(hours=1),
            'call_end_datetime': start + timedelta(hours=3), 'state': 'approved'})
        self.Rule._compute_period(self.date_from, self.date_to)
        self.assertEqual(self._result(rule, self.doctor).amount, 160.0)
        self.assertEqual(oncall.allowance_amount, 160.0)
