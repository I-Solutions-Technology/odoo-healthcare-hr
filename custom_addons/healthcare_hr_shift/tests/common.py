from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo.addons.healthcare_hr_core.tests.common import HealthcareCommon


class ShiftCommon(HealthcareCommon):
    """Nurse and doctor under contract with valid credentials, UTC timezone,
    Monday-Friday company calendar (weekend = Saturday, Sunday)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({
            'hc_night_start': 22.0, 'hc_night_end': 6.0, 'hc_max_weekly_hours': 60.0,
            'hc_max_shift_hours': 24.0, 'hc_default_rest_hours': 8.0,
        })
        cls.company.partner_id.tz = 'UTC'
        # a Monday far enough in the future, contract and credentials cover it
        today = date.today()
        cls.monday = today + timedelta(days=(7 - today.weekday()) + 7)
        for employee in cls.nurse | cls.doctor:
            employee.write({
                'contract_date_start': today - relativedelta(years=1),
                'contract_date_end': False,
                'wage': 10000,
            })
        cls.doctor.allow_24h_shift = True
        Credential = cls.env['healthcare.hr.credential']
        types = cls.env['healthcare.hr.credential.type'].search([('mandatory', '=', True)])
        for employee in cls.nurse | cls.doctor:
            for ctype in types:
                Credential.create({
                    'employee_id': employee.id, 'credential_type_id': ctype.id, 'credential_number': 'X',
                    'expiry_date': today + relativedelta(years=2), 'verified': True})
        ref = cls.env.ref
        cls.t_morning = ref('healthcare_hr_shift.shift_template_morning')
        cls.t_night = ref('healthcare_hr_shift.shift_template_night')
        cls.t_day12 = ref('healthcare_hr_shift.shift_template_day12')
        cls.t_night12 = ref('healthcare_hr_shift.shift_template_night12')
        cls.t_24 = ref('healthcare_hr_shift.shift_template_h24')
        cls.Shift = cls.env['healthcare.shift.assignment']

    def _shift(self, employee, template, day, publish=False):
        shift = self.Shift.create({'employee_id': employee.id, 'shift_template_id': template.id, 'date': day})
        if publish:
            shift.action_publish()
        return shift

    @staticmethod
    def _dt(day, hour, minute=0):
        return datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
