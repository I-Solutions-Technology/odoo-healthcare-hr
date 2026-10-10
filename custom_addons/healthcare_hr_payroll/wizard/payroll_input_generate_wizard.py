from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.exceptions import UserError


class PayrollInputGenerateWizard(models.TransientModel):
    _name = 'healthcare.payroll.input.generate.wizard'
    _description = 'Generate Payroll Inputs'

    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1)
                          + relativedelta(months=1, days=-1))
    employee_ids = fields.Many2many('hr.employee', help="Leave empty for every employee.")
    compute_allowances = fields.Boolean(default=True, help="Recompute and confirm allowances of the period first.")

    def action_generate(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(self.env._('The end date is before the start date.'))
        employees = self.employee_ids or None
        if self.compute_allowances:
            results = self.env['healthcare.allowance.rule']._compute_period(self.date_from, self.date_to, employees=employees)
            results.filtered(lambda r: r.state == 'draft').action_confirm()
        inputs = self.env['healthcare.payroll.input']._generate_for_period(
            self.date_from, self.date_to, employees=employees)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Payroll Inputs'),
            'res_model': 'healthcare.payroll.input',
            'view_mode': 'list,pivot,form',
            'domain': [('id', 'in', inputs.ids)],
        }
