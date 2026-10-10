from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.healthcare_hr_core.tests.common import HealthcareCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcareContract(HealthcareCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = fields.Date.today()
        cls.nurse.write({
            'contract_date_start': today - relativedelta(days=80),
            'contract_date_end': today + relativedelta(days=20),
            'trial_date_end': today + relativedelta(days=10),
            'wage': 10000,
        })
        cls.version = cls.nurse.version_id

    def test_start_probation_and_alerts(self):
        self.version.action_start_probation()
        self.assertEqual(self.version.probation_status, 'started')
        self.assertEqual(self.nurse.employment_status, 'probation')
        self.env['hr.version']._cron_healthcare_contract_alerts()
        self.assertEqual(self.version.probation_status, 'review_due', "10 days left <= 30 day threshold")
        activities = self.env['mail.activity'].search([('res_model', '=', 'hr.employee'), ('res_id', '=', self.nurse.id)])
        self.assertEqual(len(activities), 2, "one probation alert and one contract expiry alert")
        self.env['hr.version']._cron_healthcare_contract_alerts()
        activities_again = self.env['mail.activity'].search([('res_model', '=', 'hr.employee'), ('res_id', '=', self.nurse.id)])
        self.assertEqual(activities, activities_again, "cron is idempotent: no duplicate alerts")

    def test_review_never_terminates(self):
        self.version.action_start_probation()
        review = self.env['healthcare.hr.probation.review'].create({
            'employee_id': self.nurse.id, 'version_id': self.version.id, 'score': 10, 'recommendation': 'terminate'})
        review.action_submit()
        review.action_approve()
        self.assertEqual(self.version.probation_status, 'terminate_recommended')
        self.assertTrue(self.nurse.active, "employee is not archived automatically")
        self.assertNotEqual(self.nurse.employment_status, 'exited')

    def test_review_pass_and_extend(self):
        self.version.action_start_probation()
        review = self.env['healthcare.hr.probation.review'].create({
            'employee_id': self.nurse.id, 'version_id': self.version.id, 'recommendation': 'extend'})
        with self.assertRaises(UserError):
            review.action_submit()
        new_end = fields.Date.today() + relativedelta(months=2)
        review.extension_end_date = new_end
        review.action_submit()
        review.action_approve()
        self.assertEqual(self.version.trial_date_end, new_end)
        self.assertEqual(self.version.probation_status, 'extended')
        review2 = self.env['healthcare.hr.probation.review'].create({
            'employee_id': self.nurse.id, 'version_id': self.version.id, 'recommendation': 'pass'})
        review2.action_submit()
        review2.action_approve()
        self.assertEqual(self.version.probation_status, 'passed')
        self.assertEqual(self.nurse.employment_status, 'active')

    def test_renew_contract(self):
        old_end = self.version.contract_date_end
        new_version = self.version._renew(months=12)
        self.assertEqual(new_version.contract_date_start, old_end + relativedelta(days=1))
        self.assertEqual(new_version.contract_date_end, old_end + relativedelta(months=12))
        self.version.renewal_type = 'non_renewable'
        with self.assertRaises(UserError):
            self.version._renew()

    def test_under_contract_check(self):
        today = fields.Date.today()
        self.assertTrue(self.nurse._hc_is_under_contract(today))
        self.assertFalse(self.nurse._hc_is_under_contract(today + relativedelta(days=40)))
        self.assertFalse(self.doctor._hc_is_under_contract(date(2000, 1, 1)))
