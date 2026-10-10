from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    hc_overtime_min_minutes = fields.Integer(
        string='Overtime Threshold (min)', default=30,
        help="Extra time below this threshold is not proposed as overtime.")
    hc_overtime_rounding_minutes = fields.Integer(
        string='Payroll Overtime Rounding (min)', default=15,
        help="Approved overtime is rounded down to this step for payroll.")
    hc_overtime_auto_propose = fields.Boolean(
        string='Propose Overtime Automatically', default=True,
        help="Pre-fill approved overtime with the extra time on shifts that allow overtime. "
             "The approver can still change it before approval.")
    hc_missing_checkout_hours = fields.Float(
        string='Missing Checkout After (h)', default=2.0,
        help="Hours after the planned shift end (or 16 h after check-in when unplanned) "
             "after which an open attendance is flagged as missing checkout.")
