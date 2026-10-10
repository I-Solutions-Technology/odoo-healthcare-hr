from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    loan_ids = fields.One2many('healthcare.hr.loan', 'employee_id', groups='healthcare_hr_core.group_hc_payroll_officer')
    loan_remaining_amount = fields.Monetary(compute='_compute_loan_remaining', currency_field='currency_id',
                                            groups='healthcare_hr_core.group_hc_payroll_officer')

    def _compute_loan_remaining(self):
        data = dict(self.env['healthcare.hr.loan']._read_group(
            [('employee_id', 'in', self.ids), ('state', 'in', ('approved', 'active'))],
            ['employee_id'], ['remaining_amount:sum']))
        for employee in self:
            employee.loan_remaining_amount = data.get(employee, 0.0)

    def action_view_loans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Loans'), 'res_model': 'healthcare.hr.loan',
            'view_mode': 'list,form', 'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
