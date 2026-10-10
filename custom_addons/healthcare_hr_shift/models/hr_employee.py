from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    allow_24h_shift = fields.Boolean(string='24-hour Shifts Allowed', groups='hr.group_hr_user',
                                     help="Required to be scheduled on shifts of 24 hours.")
    weekend_work_allowed = fields.Boolean(string='Weekend Work Allowed', default=True, groups='hr.group_hr_user')
    max_weekly_hours = fields.Float(string='Max Weekly Hours', groups='hr.group_hr_user',
                                    help="Overrides the company limit when set.")
    shift_assignment_ids = fields.One2many('healthcare.shift.assignment', 'employee_id', string='Shifts')

    def action_view_shifts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Shifts'),
            'res_model': 'healthcare.shift.assignment',
            'view_mode': 'calendar,list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
