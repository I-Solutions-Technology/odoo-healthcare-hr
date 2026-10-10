from datetime import timedelta

from odoo.addons.healthcare_hr_shift.tests.common import ShiftCommon


class PayrollCommon(ShiftCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.day = cls.monday - timedelta(days=35)
        cls.date_from = cls.day.replace(day=1)
        cls.date_to = (cls.date_from + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        cls.structure_type = cls.env.ref('hr.structure_type_employee')
        cls.structure = cls.env.ref('hr_payroll.structure_002')
        cls.structure.action_hc_add_healthcare_rules()
        (cls.nurse | cls.doctor).write({'structure_type_id': cls.structure_type.id})
        cls.company.write({'hc_overtime_rate': 1.5, 'hc_payroll_monthly_hours': 200})
        cls.env['healthcare.allowance.rule'].search([]).write({'active': False})
        cls.Input = cls.env['healthcare.payroll.input']

    def _approved_shift(self, employee, template, day, overtime=0.0):
        shift = self._shift(employee, template, day, publish=True)
        shift.write({'state': 'approved', 'actual_check_in': shift.datetime_start,
                     'actual_check_out': shift.datetime_end, 'actual_worked_hours': shift.planned_hours,
                     'overtime_hours': overtime, 'payroll_overtime_hours': overtime})
        return shift

    def _payslip(self, employee):
        slip = self.env['hr.payslip'].create({'name': 'T', 'employee_id': employee.id,
                                              'date_from': self.date_from, 'date_to': self.date_to})
        slip.compute_sheet()
        return slip
