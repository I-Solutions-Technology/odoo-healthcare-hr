import base64

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.healthcare_hr_core.tests.common import HealthcareCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcareRecruitment(HealthcareCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        ref = cls.env.ref
        cls.stage_verification = ref('healthcare_hr_recruitment.stage_credential_verification')
        cls.stage_offer = ref('hr_recruitment.stage_job4')
        cls.stage_hired = cls.env['hr.recruitment.stage'].search([('hired_stage', '=', True)], limit=1)
        cls.license = ref('healthcare_hr_credentials.credential_type_medical_license')
        cls.classification = ref('healthcare_hr_credentials.credential_type_prof_classification')
        cls.bls = ref('healthcare_hr_credentials.credential_type_bls')
        cls.acls = ref('healthcare_hr_credentials.credential_type_acls')
        cls.required = cls.env['healthcare.hr.credential.type'].search([('mandatory', '=', True)]).filtered(
            lambda t: not t.job_ids)
        cls.Applicant = cls.env['hr.applicant']

    def _applicant(self, **vals):
        return self.Applicant.create(dict({
            'partner_name': 'Nadia Fathy', 'email_from': 'nadia@example.com', 'job_id': self.job_nurse.id,
            'department_id': self.dept_icu.id, 'stage_id': self.stage_offer.id}, **vals))

    def _line(self, applicant, ctype, verify=True, days=365, **vals):
        line = self.env['healthcare.applicant.credential'].create(dict({
            'applicant_id': applicant.id, 'credential_type_id': ctype.id, 'credential_number': f'{ctype.code}-1',
            'issuing_authority': 'MOH', 'expiry_date': self.today + relativedelta(days=days)}, **vals))
        if verify:
            line.action_verify()
        return line

    def _verified_applicant(self, **vals):
        applicant = self._applicant(**vals)
        for ctype in applicant.required_credential_type_ids:
            self._line(applicant, ctype)
        self.assertEqual(applicant.credential_verification_status, 'verified')
        return applicant

    def test_stage_placed_before_hiring(self):
        self.assertTrue(self.stage_offer.sequence <= self.stage_verification.sequence < self.stage_hired.sequence)

    def test_required_credentials_default_from_job(self):
        applicant = self._applicant()
        self.assertEqual(applicant.employee_category, 'nurse')
        self.assertEqual(applicant.required_credential_type_ids, self.required)
        self.assertIn(self.bls, applicant.required_credential_type_ids)
        admin = self._applicant(job_id=self.env['hr.job'].create({'name': 'T Clerk', 'employee_category': 'hr'}).id)
        self.assertFalse(admin.required_credential_type_ids, "clinical credentials are not required for HR staff")
        self.assertEqual(admin.credential_verification_status, 'verified', "nothing to verify")

    def test_verification_gate(self):
        applicant = self._applicant()
        self.assertEqual(applicant.credential_verification_status, 'not_started')
        with self.assertRaises(UserError):
            applicant.stage_id = self.stage_hired
        self._line(applicant, self.license)
        self._line(applicant, self.classification)
        bls = self._line(applicant, self.bls, verify=False)
        self.assertEqual(applicant.credential_verification_status, 'in_progress')
        applicant.stage_id = self.stage_verification  # verification stage itself is allowed
        with self.assertRaises(UserError):
            applicant.stage_id = self.stage_hired
        bls.action_verify()
        self.assertEqual(applicant.credential_verification_status, 'verified')
        applicant.stage_id = self.stage_hired
        self.assertEqual(applicant.stage_id, self.stage_hired)
        # a changed number must be verified again
        bls.credential_number = 'BLS-NEW'
        self.assertFalse(bls.verified)
        self.assertEqual(applicant.credential_verification_status, 'in_progress')

    def test_failed_verification_blocks(self):
        applicant = self._verified_applicant()
        with self.assertRaises(UserError):
            applicant.action_hc_verification_failed()
        applicant.hc_verification_note = 'License number unknown to the authority'
        applicant.action_hc_verification_failed()
        self.assertEqual(applicant.credential_verification_status, 'failed')
        with self.assertRaises(UserError):
            applicant.stage_id = self.stage_hired
        with self.assertRaises(UserError):
            applicant.create_employee_from_applicant()
        applicant.action_hc_reset_verification()
        self.assertEqual(applicant.credential_verification_status, 'verified')

    def test_expired_or_empty_line_cannot_be_verified(self):
        applicant = self._applicant()
        with self.assertRaises(UserError):
            self._line(applicant, self.bls, days=-1)
        with self.assertRaises(UserError):
            self._line(applicant, self.license, credential_number=False)

    def test_employee_creation_copies_data(self):
        specialty = self.env.ref('healthcare_hr_core.specialty_icu_nursing')
        applicant = self._verified_applicant(
            arabic_name='نادية فتحي', healthcare_specialty_id=specialty.id, professional_license='RN-777',
            years_experience=4, classification='registered_nurse')
        attachment = self.env['ir.attachment'].create({
            'name': 'acls.pdf', 'datas': base64.b64encode(b'ACLS certificate'),
            'res_model': 'hr.applicant', 'res_id': applicant.id})
        self._line(applicant, self.acls, verify=False, attachment_ids=[(6, 0, attachment.ids)])
        self.assertEqual(applicant.credential_verification_status, 'verified', "ACLS is optional")
        applicant.stage_id = self.stage_hired
        applicant.create_employee_from_applicant()
        employee = applicant.employee_id
        self.assertTrue(employee)
        self.assertEqual((employee.employee_category, employee.arabic_name, employee.professional_registration_number),
                         ('nurse', 'نادية فتحي', 'RN-777'))
        self.assertEqual((employee.medical_specialty_id, employee.sub_specialty_id), (specialty.parent_id, specialty))
        self.assertEqual(employee.job_id, self.job_nurse)
        creds = self.env['healthcare.hr.credential'].search([('employee_id', '=', employee.id)])
        self.assertEqual(creds.credential_type_id, self.required | self.acls)
        for cred in creds - creds.filtered(lambda c: c.credential_type_id == self.acls):
            self.assertTrue(cred.verified, f"{cred.credential_type_id.name} verified during recruitment")
            self.assertEqual(cred.status, 'valid')
        acls = creds.filtered(lambda c: c.credential_type_id == self.acls)
        self.assertEqual(acls.status, 'under_verification')
        self.assertEqual(acls.attachment_ids.res_model, 'healthcare.hr.credential', "document copied to the credential")
        onboarding = self.env['healthcare.hr.onboarding'].search([('employee_id', '=', employee.id)])
        self.assertEqual(len(onboarding), 1)
        self.assertTrue(onboarding.line_ids, "checklist generated")
        self.assertFalse(self.env['healthcare.hr.credential']._generate_missing_credentials(employee),
                         "every mandatory credential already exists")

    def test_create_employee_requires_verification(self):
        applicant = self._applicant()
        with self.assertRaises(UserError):
            applicant.create_employee_from_applicant()
        self.assertFalse(applicant.employee_id)

    def test_recruitment_officer_uses_standard_recruitment(self):
        officer = self._user('hc_recruiter', 'healthcare_hr_core.group_hc_recruitment_officer')
        self.assertTrue(officer.has_group('hr_recruitment.group_hr_recruitment_user'))
        applicant = self._applicant().with_user(officer)
        line = self.env['healthcare.applicant.credential'].with_user(officer).create({
            'applicant_id': applicant.id, 'credential_type_id': self.bls.id, 'credential_number': 'B-9'})
        line.action_verify()
        self.assertTrue(line.verified)
