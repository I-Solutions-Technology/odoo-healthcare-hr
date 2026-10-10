from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    hc_night_start = fields.Float(string='Night Window Start', default=22.0,
                                  help="Local time from which worked hours count as night hours.")
    hc_night_end = fields.Float(string='Night Window End', default=6.0)
    hc_max_weekly_hours = fields.Float(string='Maximum Weekly Hours', default=60.0,
                                       help="Scheduling limit per employee and ISO week (0 = no limit).")
    hc_max_shift_hours = fields.Float(string='Maximum Continuous Shift', default=24.0)
    hc_default_rest_hours = fields.Float(string='Default Minimum Rest (h)', default=8.0)
    hc_shift_match_window = fields.Float(
        string='Attendance Matching Window (h)', default=3.0,
        help="A check-in up to this many hours before a shift start is matched to that shift.")

    def _hc_weekend_days(self):
        """Weekend = weekdays without working hours in the company working schedule."""
        self.ensure_one()
        calendar = self.resource_calendar_id
        if not calendar or not calendar.attendance_ids:
            return (5, 6)
        working = {int(att.dayofweek) for att in calendar.attendance_ids}
        return tuple(day for day in range(7) if day not in working)

    def _hc_holiday_intervals(self, start, end):
        """Company-wide public holidays (calendar leaves without resource) as UTC intervals."""
        self.ensure_one()
        leaves = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False), ('company_id', 'in', (self.id, False)),
            ('date_from', '<', end), ('date_to', '>', start),
            '|', ('calendar_id', '=', False), ('calendar_id', '=', self.resource_calendar_id.id),
        ])
        return [(leave.date_from, leave.date_to) for leave in leaves]
