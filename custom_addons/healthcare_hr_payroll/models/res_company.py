from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    hc_overtime_rate = fields.Float(string='Overtime Rate', default=1.25,
                                    help="Multiplier applied to the hourly wage for approved payroll overtime.")
    hc_payroll_monthly_hours = fields.Float(
        string='Monthly Hours for Hourly Rate',
        help="Hourly rate = monthly wage / this value. Empty = derived from the working schedule "
             "(weekly hours x 52 / 12).")

    def _hc_hourly_rate(self, wage, calendar=None):
        self.ensure_one()
        hours = self.hc_payroll_monthly_hours
        if not hours:
            calendar = calendar or self.resource_calendar_id
            weekly = (calendar.hours_per_day or 8.0) * len(set(calendar.attendance_ids.mapped('dayofweek')) or range(5))
            hours = weekly * 52 / 12
        return wage / hours if hours else 0.0
