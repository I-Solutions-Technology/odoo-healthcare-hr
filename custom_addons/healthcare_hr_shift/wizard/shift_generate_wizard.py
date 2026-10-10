from odoo import fields, models
from odoo.exceptions import UserError


class ShiftGenerateWizard(models.TransientModel):
    _name = 'healthcare.shift.generate.wizard'
    _description = 'Generate Shifts'

    employee_ids = fields.Many2many('hr.employee', required=True)
    shift_template_id = fields.Many2one('healthcare.shift.template', required=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=lambda self: fields.Date.add(fields.Date.context_today(self), days=6))
    monday = fields.Boolean(default=True)
    tuesday = fields.Boolean(default=True)
    wednesday = fields.Boolean(default=True)
    thursday = fields.Boolean(default=True)
    friday = fields.Boolean(default=True)
    saturday = fields.Boolean(default=True)
    sunday = fields.Boolean(default=True)

    def action_generate(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(self.env._('The end date is before the start date.'))
        days = [self.monday, self.tuesday, self.wednesday, self.thursday, self.friday, self.saturday, self.sunday]
        weekdays = {i for i, selected in enumerate(days) if selected}
        created = self.env['healthcare.shift.assignment']._hc_generate(
            self.employee_ids, self.shift_template_id, self.date_from, self.date_to, weekdays)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Generated Shifts'),
            'res_model': 'healthcare.shift.assignment',
            'view_mode': 'list,calendar,form',
            'domain': [('id', 'in', created.ids)],
        }
