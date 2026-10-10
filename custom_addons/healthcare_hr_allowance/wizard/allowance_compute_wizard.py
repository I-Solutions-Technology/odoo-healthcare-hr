from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.exceptions import UserError


class AllowanceComputeWizard(models.TransientModel):
    _name = 'healthcare.allowance.compute.wizard'
    _description = 'Compute Allowances'

    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1)
                          + relativedelta(months=1, days=-1))
    employee_ids = fields.Many2many('hr.employee', help="Leave empty for every employee of the company.")
    confirm = fields.Boolean(string='Confirm results', help="Confirm the computed results for payroll right away.")

    def action_compute(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(self.env._('The end date is before the start date.'))
        results = self.env['healthcare.allowance.rule']._compute_period(
            self.date_from, self.date_to, employees=self.employee_ids or None)
        if self.confirm:
            results.action_confirm()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Allowance Results'),
            'res_model': 'healthcare.allowance.result',
            'view_mode': 'list,pivot,form',
            'domain': [('date_from', '=', self.date_from), ('date_to', '=', self.date_to)],
        }
