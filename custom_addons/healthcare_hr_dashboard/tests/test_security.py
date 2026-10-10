from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.healthcare_hr_shift.tests.common import ShiftCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestSuiteSecurity(ShiftCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nurse_user = cls._user('sec_nurse', 'base.group_user')
        cls.nurse.user_id = cls.nurse_user
        cls.manager_user = cls._user('sec_icu_manager', 'healthcare_hr_core.group_hc_department_manager')
        cls.manager_employee = cls.env['hr.employee'].create({'name': 'ICU Head', 'user_id': cls.manager_user.id,
                                                              'department_id': cls.dept_icu.id})
        cls.dept_icu.manager_id = cls.manager_employee
        cls.nurse_shift = cls._shift(cls, cls.nurse, cls.t_morning, cls.monday, publish=True)
        cls.doctor_shift = cls._shift(cls, cls.doctor, cls.t_morning, cls.monday, publish=True)

    def test_employee_sees_only_own_records(self):
        Shift = self.env['healthcare.shift.assignment'].with_user(self.nurse_user)
        self.assertEqual(Shift.search([('id', 'in', (self.nurse_shift | self.doctor_shift).ids)]), self.nurse_shift)
        Credential = self.env['healthcare.hr.credential'].with_user(self.nurse_user)
        self.assertEqual(set(Credential.search([]).employee_id.ids), {self.nurse.id})
        with self.assertRaises(AccessError):
            self.doctor_shift.with_user(self.nurse_user).read(['name'])
        with self.assertRaises(AccessError):
            self.nurse_shift.with_user(self.nurse_user).write({'note': 'self-edit'})

    def test_department_manager_scope(self):
        Shift = self.env['healthcare.shift.assignment'].with_user(self.manager_user)
        visible = Shift.search([('id', 'in', (self.nurse_shift | self.doctor_shift).ids)])
        self.assertIn(self.nurse_shift, visible, "ICU manager sees ICU shifts")
        self.assertTrue(self.env['healthcare.shift.swap'].with_user(self.manager_user).has_access('read'))

    def test_payroll_restriction(self):
        for user in (self.nurse_user, self.manager_user):
            for model in ('healthcare.payroll.input', 'healthcare.allowance.result'):
                self.assertFalse(self.env[model].with_user(user).has_access('read'), f'{user.login} on {model}')
        with self.assertRaises(AccessError):
            self.nurse.with_user(self.manager_user).read(['wage'])

    def test_multi_company_isolation(self):
        other = self.env['res.company'].create({'name': 'Isolated Clinic'})
        officer = self._user('sec_officer_mc', 'healthcare_hr_core.group_hc_officer,healthcare_hr_core.group_hc_scheduling_officer')
        other_emp = self.env['hr.employee'].create({'name': 'Other Co Nurse', 'company_id': other.id})
        shift = self.env['healthcare.shift.assignment'].with_company(other).create({
            'employee_id': other_emp.id, 'shift_template_id': self.t_morning.id, 'date': self.monday,
            'company_id': other.id})
        self.assertFalse(self.env['healthcare.shift.assignment'].with_user(officer).search([('id', '=', shift.id)]))
        self.assertFalse(self.env['hr.employee'].with_user(officer).search([('id', '=', other_emp.id)]))
