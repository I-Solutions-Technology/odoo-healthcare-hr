from odoo.tests import TransactionCase, new_test_user


class HealthcareCommon(TransactionCase):
    """Shared fixture: one company, a hospital with two branches, ICU/ER departments,
    a nurse and a doctor. Timezone UTC to keep datetime assertions simple."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_create_nolog=True))
        cls.company = cls.env.company
        Branch = cls.env['healthcare.hr.branch']
        cls.hospital = Branch.create({'name': 'Test Hospital', 'code': 'THOS', 'branch_type': 'hospital'})
        cls.branch_1 = Branch.create({'name': 'T-Branch 1', 'code': 'TB1', 'parent_id': cls.hospital.id})
        cls.branch_2 = Branch.create({'name': 'T-Branch 2', 'code': 'TB2', 'parent_id': cls.hospital.id})
        Dept = cls.env['hr.department']
        cls.dept_icu = Dept.create({'name': 'T-ICU', 'healthcare_branch_id': cls.branch_1.id})
        cls.dept_er = Dept.create({'name': 'T-ER', 'healthcare_branch_id': cls.branch_2.id})
        cls.unit_icu = cls.env['healthcare.hr.unit'].create({
            'name': 'ICU A', 'code': 'TICUA', 'department_id': cls.dept_icu.id, 'branch_id': cls.branch_1.id})
        cls.job_nurse = cls.env['hr.job'].create({'name': 'T-Nurse', 'employee_category': 'nurse'})
        cls.job_doctor = cls.env['hr.job'].create({'name': 'T-Doctor', 'employee_category': 'doctor'})
        cls.nurse = cls.env['hr.employee'].create({
            'name': 'Test Nurse', 'job_id': cls.job_nurse.id, 'department_id': cls.dept_icu.id,
            'tz': 'UTC', 'healthcare_unit_id': cls.unit_icu.id,
        })
        cls.doctor = cls.env['hr.employee'].create({
            'name': 'Test Doctor', 'job_id': cls.job_doctor.id, 'department_id': cls.dept_er.id, 'tz': 'UTC',
        })

    @classmethod
    def _user(cls, login, groups, **kw):
        return new_test_user(cls.env, login=login, groups=groups, **kw)
