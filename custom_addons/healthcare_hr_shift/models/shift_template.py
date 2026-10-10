from odoo import api, fields, models
from odoo.exceptions import ValidationError

SHIFT_TYPES = [
    ('morning', 'Morning'),
    ('evening', 'Evening'),
    ('night', 'Night'),
    ('twelve_hour', '12 Hours'),
    ('twenty_four_hour', '24 Hours'),
    ('on_call', 'On Call'),
    ('custom', 'Custom'),
]


class ShiftTemplate(models.Model):
    _name = 'healthcare.shift.template'
    _description = 'Shift Template'
    _order = 'sequence, start_time'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True,
                                 help="Empty = shared by all companies.")
    branch_id = fields.Many2one('healthcare.hr.branch', check_company=True,
                                help="Restrict the template to a branch. Empty = all branches.")
    shift_type = fields.Selection(SHIFT_TYPES, required=True, default='morning')
    start_time = fields.Float(required=True, default=8.0, help="Local start time (24h clock).")
    end_time = fields.Float(required=True, default=16.0,
                            help="Local end time. An end time before the start time ends the next day. "
                                 "For a 24-hour shift use the same time as the start.")
    duration_hours = fields.Float(compute='_compute_duration_hours', store=True)
    break_minutes = fields.Integer(default=0)
    paid_hours = fields.Float(compute='_compute_duration_hours', store=True, help="Duration minus unpaid break.")
    grace_minutes = fields.Integer(default=10, help="Tolerance before a check-in counts as late / check-out as early.")
    night_shift = fields.Boolean(compute='_compute_flags', store=True, readonly=False)
    weekend_shift = fields.Boolean(help="Template dedicated to weekend coverage.")
    public_holiday_shift = fields.Boolean(help="Template dedicated to public holiday coverage.")
    crosses_midnight = fields.Boolean(compute='_compute_duration_hours', store=True)
    overtime_allowed = fields.Boolean(default=True, help="Extra time on this shift may be approved as overtime.")
    minimum_rest_hours = fields.Float(default=8.0, help="Minimum rest required after this shift.")
    job_ids = fields.Many2many('hr.job', string='Allowed Jobs',
                               help="Only employees in these positions may take this shift. Empty = all.")
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint('unique (code, company_id)', 'The shift code must be unique per company.')

    @api.depends('start_time', 'end_time', 'break_minutes', 'shift_type')
    def _compute_duration_hours(self):
        for template in self:
            duration = (template.end_time - template.start_time) % 24
            if template.shift_type == 'twenty_four_hour' or duration == 0:
                duration = 24.0
            template.duration_hours = duration
            template.paid_hours = max(duration - (template.break_minutes or 0) / 60.0, 0.0)
            template.crosses_midnight = template.start_time + duration > 24

    @api.depends('shift_type', 'start_time', 'end_time')
    def _compute_flags(self):
        for template in self:
            template.night_shift = template.shift_type == 'night' or (
                template.crosses_midnight and template.shift_type != 'twenty_four_hour')

    @api.constrains('start_time', 'end_time', 'break_minutes')
    def _check_times(self):
        for template in self:
            if not (0 <= template.start_time < 24 and 0 <= template.end_time <= 24):
                raise ValidationError(self.env._('Shift times must be between 00:00 and 24:00.'))
            if template.break_minutes < 0 or template.break_minutes / 60.0 >= template.duration_hours:
                raise ValidationError(self.env._('The break must be shorter than the shift.'))

    @api.depends('name', 'start_time', 'end_time')
    def _compute_display_name(self):
        for template in self:
            template.display_name = '%s (%02d:%02d-%02d:%02d)' % (
                template.name or '', int(template.start_time), round(template.start_time % 1 * 60),
                int(template.end_time) % 24, round(template.end_time % 1 * 60))
