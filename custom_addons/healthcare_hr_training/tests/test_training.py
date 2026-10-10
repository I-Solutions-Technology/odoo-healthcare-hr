from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.healthcare_hr_core.tests.common import HealthcareCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcareTraining(HealthcareCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env['healthcare.training.assignment'])
        cls.company.hc_training_alert_days = 30
        Requirement = cls.env['healthcare.training.requirement']
        # isolate the tests from the demo matrix
        Requirement.search([]).write({'active': False})
        cls.bls = cls.env.ref('healthcare_hr_credentials.credential_type_bls')
        cls.acls = cls.env.ref('healthcare_hr_credentials.credential_type_acls')
        cls.req_bls = Requirement.create({
            'name': 'T Nurse BLS', 'employee_category': 'nurse', 'credential_type_id': cls.bls.id,
            'renewal_period_months': 24, 'due_days': 30})
        cls.req_acls = Requirement.create({
            'name': 'T ICU ACLS', 'employee_category': 'nurse', 'department_id': cls.dept_icu.id,
            'credential_type_id': cls.acls.id, 'renewal_period_months': 24, 'auto_verify_credential': True})
        cls.Assignment = cls.env['healthcare.training.assignment']
        cls.Credential = cls.env['healthcare.hr.credential']

    def _generate(self):
        return self.Assignment._generate_assignments(self.nurse | self.doctor)

    def _assignment(self, requirement, employee=None):
        return self.Assignment.search([('employee_id', '=', (employee or self.nurse).id),
                                       ('requirement_id', '=', requirement.id)], order='id desc', limit=1)

    def _complete(self, requirement, completion=None, number='CERT-1'):
        assignment = self._assignment(requirement)
        assignment.write({'certificate_number': number, 'provider': 'AHA',
                          'completion_date': completion or self.today})
        assignment.action_complete()
        return assignment

    def test_applies_to(self):
        self.assertTrue(self.req_bls._applies_to(self.nurse))
        self.assertFalse(self.req_bls._applies_to(self.doctor))
        self.assertTrue(self.req_acls._applies_to(self.nurse), "nurse of the ICU department")
        self.nurse.department_id = self.dept_er
        self.assertFalse(self.req_acls._applies_to(self.nurse))
        self.nurse.medical_department_id = self.dept_icu
        self.assertTrue(self.req_acls._applies_to(self.nurse), "medical department also matches")

    def test_generation_idempotent(self):
        created = self._generate()
        self.assertEqual(created.employee_id, self.nurse)
        self.assertEqual(created.requirement_id, self.req_bls | self.req_acls)
        self.assertTrue(all(a.state == 'assigned' and a.due_date == self.today + relativedelta(days=30)
                            for a in created.filtered(lambda a: a.requirement_id == self.req_bls)))
        self.assertFalse(self._generate(), "second run creates nothing")

    def test_generation_skips_compliant_employee(self):
        self.Credential.create({'employee_id': self.nurse.id, 'credential_type_id': self.bls.id,
                                'credential_number': 'B-1', 'verified': True,
                                'expiry_date': self.today + relativedelta(days=400)})
        self.Credential.create({'employee_id': self.nurse.id, 'credential_type_id': self.acls.id,
                                'credential_number': 'A-1', 'verified': True,
                                'expiry_date': self.today + relativedelta(days=10)})
        created = self._generate()
        self.assertEqual(created.requirement_id, self.req_acls,
                         "valid BLS skipped, ACLS expiring inside the alert window is assigned")
        self.assertEqual(created.due_date, self.today + relativedelta(days=10), "due before the credential expires")

    def test_completion_creates_credential(self):
        self._generate()
        completion = self.today - relativedelta(days=10)
        assignment = self._complete(self.req_bls, completion, number='BLS-77')
        self.assertEqual(assignment.state, 'completed')
        self.assertEqual(assignment.expiry_date, completion + relativedelta(months=24))
        cred = assignment.credential_id
        self.assertTrue(cred)
        self.assertEqual((cred.employee_id, cred.credential_type_id), (self.nurse, self.bls))
        self.assertEqual((cred.credential_number, cred.issue_date, cred.expiry_date, cred.issuing_authority),
                         ('BLS-77', completion, assignment.expiry_date, 'AHA'))
        self.assertEqual(cred.status, 'under_verification', "not auto-verified: left for HR verification")
        acls = self._complete(self.req_acls)
        self.assertTrue(acls.credential_id.verified)
        self.assertEqual(acls.credential_id.status, 'valid', "auto-verified requirement")

    def test_completion_renews_existing_credential(self):
        old = self.Credential.create({'employee_id': self.nurse.id, 'credential_type_id': self.bls.id,
                                      'credential_number': 'OLD', 'verified': True,
                                      'expiry_date': self.today + relativedelta(days=5)})
        self._generate()
        assignment = self._complete(self.req_bls, number='NEW')
        self.assertEqual(assignment.credential_id, old, "the existing credential is renewed, not duplicated")
        self.assertEqual(old.credential_number, 'NEW')
        self.assertEqual(old.expiry_date, self.today + relativedelta(months=24))
        self.assertFalse(old.verified, "a renewed certificate must be verified again")
        self.assertEqual(self.Credential.search_count([('employee_id', '=', self.nurse.id),
                                                       ('credential_type_id', '=', self.bls.id)]), 1)

    def test_completion_requires_certificate(self):
        self._generate()
        with self.assertRaises(UserError):
            self._assignment(self.req_bls).action_complete()

    def test_expiry_marking_and_compliance_flag(self):
        self._generate()
        recent = self._complete(self.req_acls)
        self.assertTrue(recent.compliant)
        self.assertEqual(recent.compliance_rate, 100.0)
        old = self._complete(self.req_bls, self.today - relativedelta(months=24, days=1))
        self.assertEqual(old.expiry_date, self.today - relativedelta(days=1))
        self.assertFalse(old.compliant, "completed but already expired")
        expired = self.Assignment._cron_mark_expired()
        self.assertIn(old, expired)
        self.assertEqual(old.state, 'expired')
        self.assertEqual(recent.state, 'completed')
        self.assertFalse(old.compliant)
        # the expired certification is due again
        self.assertEqual(self._generate().requirement_id, self.req_bls)

    def test_compliance_report(self):
        self._generate()
        self._complete(self.req_acls)
        self.env.flush_all()
        Report = self.env['healthcare.training.compliance.report']
        rows = Report.search([('employee_id', '=', self.nurse.id)])
        status = {row.requirement_id: row.status for row in rows}
        self.assertEqual(status, {self.req_acls: 'compliant', self.req_bls: 'in_training'})
        [(department, rate)] = Report._read_group([('employee_id', '=', self.nurse.id)], ['department_id'],
                                                  ['compliance_rate:avg'])
        self.assertEqual((department, rate), (self.dept_icu, 50.0))
        self.assertFalse(Report.search([('employee_id', '=', self.doctor.id)]), "no requirement for doctors")
        self.assertEqual(self.nurse._hc_training_matrix_compliance()[self.nurse.id], 50.0)

    def test_waiver_counts_as_compliant(self):
        self._generate()
        assignment = self._assignment(self.req_bls)
        with self.assertRaises(UserError):
            assignment.action_waive()
        assignment.waiver_reason = 'Certified abroad, equivalence pending'
        assignment.action_waive()
        self.assertTrue(assignment.compliant)
        self.assertFalse(self._generate(), "waived requirement is not re-assigned")

    def test_alerts_idempotent(self):
        self._generate()
        expiring = self._complete(self.req_acls, self.today - relativedelta(months=24) + relativedelta(days=10))
        self.assertEqual(expiring.expiry_date, self.today + relativedelta(days=10))
        self.Assignment._cron_training_alerts()
        self.Assignment._cron_training_alerts()
        missing = self._assignment(self.req_bls)
        for record, key in ((missing, 'missing'), (expiring, 'expiring')):
            activities = self.env['mail.activity'].search([('res_model', '=', record._name),
                                                           ('res_id', '=', record.id)])
            self.assertEqual(len(activities), 1, f"one {key} alert")
            self.assertIn(f'training_{record.id}_{key}', activities.summary)

    def test_unique_open_assignment(self):
        self._generate()
        with self.assertRaises(Exception), self.cr.savepoint(), mute_logger('odoo.sql_db'):
            self.Assignment.create({'employee_id': self.nurse.id, 'requirement_id': self.req_bls.id})
            self.env.flush_all()

    def test_self_service_rule(self):
        req_doctor = self.env['healthcare.training.requirement'].create({
            'name': 'T Doctor BLS', 'employee_category': 'doctor', 'credential_type_id': self.bls.id})
        self._generate()
        doctor_assignment = self._assignment(req_doctor, self.doctor)
        self.assertTrue(doctor_assignment)
        user = self._user('hc_nurse_self', 'base.group_user')
        self.nurse.user_id = user
        mine = self.Assignment.with_user(user).search([])
        self.assertEqual(mine.employee_id, self.nurse)
        self.assertEqual(len(mine), 2)
        with self.assertRaises(AccessError):
            doctor_assignment.with_user(user).read(['name'])
        with self.assertRaises(AccessError):
            mine[0].with_user(user).write({'score': 100})

    def test_training_officer_completes_training(self):
        """Training officers renew credentials through the training, without credential rights."""
        officer = self._user('hc_trainer', 'healthcare_hr_core.group_hc_training_officer')
        self._generate()
        assignment = self._assignment(self.req_bls).with_user(officer)
        assignment.write({'certificate_number': 'BLS-OFF', 'provider': 'Internal'})
        assignment.action_complete()
        self.assertEqual(assignment.state, 'completed')
        self.assertEqual(assignment.credential_id.sudo().credential_number, 'BLS-OFF')
        self.assertEqual(assignment.credential_status, 'under_verification')
