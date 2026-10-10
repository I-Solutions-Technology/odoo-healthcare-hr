from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.healthcare_hr_core.tests.common import HealthcareCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcareCredentials(HealthcareCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        cls.Credential = cls.env['healthcare.hr.credential']
        cls.bls = cls.env.ref('healthcare_hr_credentials.credential_type_bls')
        cls.license = cls.env.ref('healthcare_hr_credentials.credential_type_medical_license')

    def _cred(self, ctype, days, verified=True, number='N-1'):
        return self.Credential.create({
            'employee_id': self.nurse.id, 'credential_type_id': ctype.id, 'credential_number': number,
            'expiry_date': self.today + relativedelta(days=days), 'verified': verified})

    def test_status_valid(self):
        self.assertEqual(self._cred(self.bls, 400).status, 'valid')

    def test_status_expiring(self):
        self.assertEqual(self._cred(self.bls, 20).status, 'expiring')

    def test_status_expired(self):
        self.assertEqual(self._cred(self.bls, -1).status, 'expired')

    def test_status_missing_and_under_verification(self):
        placeholder = self.Credential.create({'employee_id': self.nurse.id, 'credential_type_id': self.bls.id})
        self.assertEqual(placeholder.status, 'missing')
        placeholder.credential_number = 'BLS-9'
        self.assertEqual(placeholder.status, 'under_verification')
        placeholder.action_verify()
        self.assertEqual(placeholder.status, 'valid')

    def test_new_number_requires_reverification(self):
        cred = self._cred(self.bls, 400)
        cred.credential_number = 'CHANGED'
        self.assertFalse(cred.verified)

    def test_blocked_shift_check(self):
        blockers = self.nurse._hc_credential_blockers(self.today)
        self.assertIn(self.nurse.id, blockers, "no credentials at all -> blocked")
        self._cred(self.bls, 400)
        self._cred(self.license, 400)
        self._cred(self.env.ref('healthcare_hr_credentials.credential_type_infection_control'), 400)
        self._cred(self.env.ref('healthcare_hr_credentials.credential_type_prof_classification'), 400)
        self.assertFalse(self.nurse._hc_credential_blockers(self.today).get(self.nurse.id))
        self.assertIn(self.nurse.id, self.nurse._hc_credential_blockers(self.today + relativedelta(days=500)),
                      "credentials expired on a future shift date block it")

    def test_alerts_idempotent(self):
        cred = self._cred(self.bls, 5)
        self.Credential._cron_credential_alerts()
        self.Credential._cron_credential_alerts()
        activities = self.env['mail.activity'].search([('res_model', '=', cred._name), ('res_id', '=', cred.id)])
        self.assertEqual(len(activities), 1)

    def test_generate_missing(self):
        created = self.Credential._generate_missing_credentials(self.nurse)
        self.assertTrue(created)
        self.assertTrue(all(c.status == 'missing' for c in created))
        self.assertFalse(self.Credential._generate_missing_credentials(self.nurse), "idempotent")
