from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.healthcare_hr_shift.tests.common import ShiftCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestHealthcareAppraisal(ShiftCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Appraisal = cls.env['hr.appraisal']
        cls.Template = cls.env['healthcare.appraisal.kpi.template']
        cls.tpl_nurse = cls.env.ref('healthcare_hr_appraisal.kpi_template_nurse')
        cls.tpl_doctor = cls.env.ref('healthcare_hr_appraisal.kpi_template_doctor')
        cls.day = cls.monday - timedelta(days=21)  # a past Monday
        cls.manager = cls.env['hr.employee'].create({'name': 'T Appraiser'})

    def _appraisal(self, employee, **vals):
        return self.Appraisal.create(dict({'employee_id': employee.id, 'manager_ids': [(6, 0, self.manager.ids)],
                                           'date_close': fields.Date.today()}, **vals))

    def _line(self, appraisal, source):
        return appraisal.hc_kpi_line_ids.filtered(lambda l: l.source == source)

    def test_template_loading_by_category(self):
        nurse_appraisal = self._appraisal(self.nurse)
        self.assertEqual(nurse_appraisal.hc_kpi_template_id, self.tpl_nurse)
        self.assertEqual(nurse_appraisal.hc_kpi_line_ids.mapped('name'), self.tpl_nurse.line_ids.mapped('name'))
        self.assertEqual(sum(nurse_appraisal.hc_kpi_line_ids.mapped('weight')), 100.0)
        doctor_appraisal = self._appraisal(self.doctor)
        self.assertEqual(doctor_appraisal.hc_kpi_template_id, self.tpl_doctor)
        self.assertEqual(len(doctor_appraisal.hc_kpi_line_ids), 6)
        self.assertEqual(nurse_appraisal.hc_period_end, fields.Date.today(), "period ends on the appraisal date")

    def test_job_template_wins_and_reload(self):
        job_template = self.Template.create({
            'name': 'T ICU nurses', 'job_ids': [(6, 0, self.job_nurse.ids)],
            'line_ids': [(0, 0, {'name': 'Ventilator care', 'weight': 100, 'target': 90})]})
        appraisal = self._appraisal(self.nurse)
        self.assertEqual(appraisal.hc_kpi_template_id, job_template)
        appraisal.hc_kpi_template_id = self.tpl_nurse
        appraisal.action_hc_load_kpis()
        self.assertEqual(len(appraisal.hc_kpi_line_ids), 5, "reload replaces the lines")

    def test_template_weights_must_sum_to_100(self):
        with self.assertRaises(Exception):
            self.Template.create({'name': 'Bad', 'line_ids': [(0, 0, {'name': 'A', 'weight': 60}),
                                                              (0, 0, {'name': 'B', 'weight': 30})]})

    def test_weighted_score(self):
        template = self.Template.create({
            'name': 'T weighted', 'job_ids': [(6, 0, self.job_doctor.ids)],
            'line_ids': [(0, 0, {'name': 'Quality', 'weight': 60, 'target': 100}),
                         (0, 0, {'name': 'Incidents', 'weight': 40, 'target': 2, 'higher_is_better': False}),
                         ]})
        appraisal = self._appraisal(self.doctor)
        self.assertEqual(appraisal.hc_kpi_template_id, template)
        self.assertEqual(appraisal.hc_kpi_score, 0.0, "nothing evaluated yet")
        quality, incidents = appraisal.hc_kpi_line_ids.sorted('sequence')
        quality.actual = 80
        self.assertEqual((quality.score, quality.weighted_score, quality.evaluated), (80.0, 48.0, True))
        self.assertEqual(appraisal.hc_kpi_score, 80.0, "only evaluated KPIs count")
        incidents.actual = 4  # twice the tolerated rate
        self.assertEqual((incidents.score, incidents.weighted_score), (50.0, 20.0))
        self.assertEqual(appraisal.hc_kpi_score, 68.0)

    def test_attendance_kpi_from_shifts(self):
        on_time = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        late = self._shift(self.nurse, self.t_morning, self.day + timedelta(days=1), publish=True)
        absent = self._shift(self.nurse, self.t_morning, self.day + timedelta(days=2), publish=True)
        Attendance = self.env['hr.attendance']
        Attendance.create({'employee_id': self.nurse.id, 'check_in': on_time.datetime_start,
                           'check_out': on_time.datetime_end})
        Attendance.create({'employee_id': self.nurse.id, 'check_in': late.datetime_start + timedelta(minutes=25),
                           'check_out': late.datetime_end})
        reconciliation = self.env['healthcare.attendance.reconciliation'].create(
            {'date_from': self.day, 'date_to': self.day + timedelta(days=2)})
        reconciliation.action_compute()
        reconciliation.action_approve()
        self.assertEqual((on_time.attendance_status, late.attendance_status, absent.attendance_status),
                         ('present', 'late', 'absent'))
        appraisal = self._appraisal(self.nurse)
        attendance = self._line(appraisal, 'attendance_rate')
        self.assertAlmostEqual(attendance.actual, 66.67, places=2)
        self.assertTrue(attendance.evaluated)
        self.assertAlmostEqual(attendance.score, 70.18, places=2, msg="66.67 against a 95 target")
        late_rate = self._line(appraisal, 'late_rate')
        self.assertEqual(late_rate.actual, 50.0, "1 late shift out of 2 attended")
        self.assertEqual(late_rate.score, 10.0, "5% tolerated, 50% measured")
        training = self._line(appraisal, 'training_compliance')
        self.assertEqual(training.actual, 100.0, "all mandatory credentials are valid")
        # shifts outside the KPI period are ignored
        appraisal.hc_period_start = self.day + timedelta(days=3)
        appraisal.action_hc_refresh_kpis()
        self.assertFalse(self._line(appraisal, 'attendance_rate').evaluated, "no shift in the period")

    def test_training_compliance_from_credentials(self):
        appraisal = self._appraisal(self.nurse)
        self.assertEqual(self._line(appraisal, 'training_compliance').actual, 100.0)
        bls = self.env.ref('healthcare_hr_credentials.credential_type_bls')
        self.env['healthcare.hr.credential'].search([('employee_id', '=', self.nurse.id),
                                                     ('credential_type_id', '=', bls.id)]).unlink()
        rate = self.nurse._hc_credential_compliance()[self.nurse.id]
        self.assertLess(rate, 100.0)

    def test_no_side_effect_on_contracts(self):
        version = self.nurse.version_id
        tracked = ['contract_date_start', 'contract_date_end', 'trial_date_end', 'probation_status', 'renewal_type']
        before = version.read(tracked)[0]
        versions_before = self.env['hr.version'].search_count([('employee_id', '=', self.nurse.id)])
        status_before = self.nurse.employment_status
        appraisal = self._appraisal(self.nurse)
        appraisal.hc_kpi_line_ids.filtered(lambda l: l.source == 'manual').write({'actual': 0})
        appraisal.action_hc_refresh_kpis()
        self.assertLess(appraisal.hc_kpi_score, 50.0)
        appraisal.action_confirm()
        appraisal.assessment_note = self.env['hr.appraisal.note'].search(
            [('company_id', 'in', (self.company.id, False))], limit=1)
        appraisal.action_done()
        self.assertEqual(appraisal.state, '3_done')
        self.assertEqual(version.read(tracked)[0], before, "a poor score never changes the contract")
        self.assertEqual(self.env['hr.version'].search_count([('employee_id', '=', self.nurse.id)]), versions_before)
        self.assertEqual(self.nurse.employment_status, status_before)
        self.assertTrue(self.nurse.active)
        with self.assertRaises(UserError):
            appraisal.action_hc_load_kpis()

    def test_employee_cannot_rate_himself(self):
        user = self._user('hc_appraisal_nurse', 'base.group_user')
        self.nurse.user_id = user
        appraisal = self._appraisal(self.nurse)
        line = appraisal.hc_kpi_line_ids.filtered(lambda l: l.source == 'manual')[:1]
        self.assertTrue(line.with_user(user).read(['name']), "the employee reads his KPIs")
        with self.assertRaises(UserError):
            line.with_user(user).write({'actual': 100})
