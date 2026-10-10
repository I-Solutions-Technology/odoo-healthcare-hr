from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import HealthcareCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcareCore(HealthcareCommon):

    def test_employee_defaults_from_job_and_department(self):
        self.assertEqual(self.nurse.employee_category, 'nurse')
        self.assertTrue(self.nurse.is_clinical)
        self.assertEqual(self.nurse.healthcare_branch_id, self.branch_1, "branch comes from the department")
        self.assertTrue(self.nurse.employee_number, "employee number comes from the sequence")

    def test_employee_number_unique_per_company(self):
        with self.assertRaises(Exception), self.cr.savepoint(), mute_logger('odoo.sql_db'):
            self.env['hr.employee'].create({'name': 'Dup', 'employee_number': self.nurse.employee_number})

    def test_branch_hierarchy(self):
        self.assertEqual(self.branch_1.complete_name, 'Test Hospital / T-Branch 1')
        with self.assertRaises(UserError), self.cr.savepoint():
            self.hospital.parent_id = self.branch_1
            self.hospital.flush_recordset()
        self.assertEqual(self.hospital.employee_count, 2, "hospital counts employees of its branches")

    def test_practitioner_link_resolution(self):
        self.env['healthcare.employee.practitioner.link'].create({
            'employee_id': self.doctor.id, 'external_system': 'EMR', 'external_code': 'DR-77'})
        found = self.env['healthcare.employee.practitioner.link']._get_employee_for_practitioner('EMR', 'DR-77')
        self.assertEqual(found, self.doctor)

    def test_onboarding_checklist(self):
        onboarding = self.env['healthcare.hr.onboarding'].create({'employee_id': self.nurse.id})
        self.assertTrue(onboarding.line_ids, "checklist generated from templates")
        onboarding.action_start()
        with self.assertRaises(Exception):
            onboarding.action_done()
        onboarding.line_ids.write({'done': True})
        self.assertEqual(onboarding.progress, 100.0)
        onboarding.action_done()
        self.assertEqual(onboarding.state, 'done')

    def test_branch_rule_for_officer(self):
        officer = self._user('hc_officer_b1', 'healthcare_hr_core.group_hc_officer')
        officer.healthcare_branch_ids = self.branch_1
        employees = self.env['hr.employee'].with_user(officer).search([('id', 'in', (self.nurse | self.doctor).ids)])
        self.assertEqual(employees, self.nurse, "officer of branch 1 does not see branch 2 employees")
        officer.healthcare_branch_ids = self.hospital
        employees = self.env['hr.employee'].with_user(officer).search([('id', 'in', (self.nurse | self.doctor).ids)])
        self.assertEqual(employees, self.nurse | self.doctor, "a facility grants its sub-branches")

    def test_multi_company_isolation(self):
        other = self.env['res.company'].create({'name': 'Other Clinic Co'})
        branch = self.env['healthcare.hr.branch'].create({'name': 'Other', 'code': 'OTH', 'company_id': other.id})
        user = self._user('hc_user_mc', 'healthcare_hr_core.group_hc_user')
        self.assertFalse(self.env['healthcare.hr.branch'].with_user(user).search([('id', '=', branch.id)]))
        with self.assertRaises(AccessError):
            branch.with_user(user).read(['name'])
