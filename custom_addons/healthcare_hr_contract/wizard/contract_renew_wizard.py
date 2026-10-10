from odoo import api, fields, models


class ContractRenewWizard(models.TransientModel):
    _name = 'healthcare.hr.contract.renew.wizard'
    _description = 'Renew Contract'

    employee_id = fields.Many2one('hr.employee', required=True)
    version_id = fields.Many2one('hr.version', required=True)
    current_end_date = fields.Date(related='version_id.contract_date_end')
    months = fields.Integer(default=12, required=True)
    new_wage = fields.Monetary(help="Leave empty to keep the current wage.")
    currency_id = fields.Many2one(related='version_id.currency_id')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        employee = self.env['hr.employee'].browse(self.env.context.get('active_id'))
        if employee and self.env.context.get('active_model') == 'hr.employee':
            res.update({'employee_id': employee.id, 'version_id': employee.current_version_id.id,
                        'months': employee.current_version_id.renewal_period_months or 12})
        return res

    def action_renew(self):
        self.ensure_one()
        self.version_id._renew(months=self.months, new_wage=self.new_wage or None)
        return {'type': 'ir.actions.act_window_close'}
