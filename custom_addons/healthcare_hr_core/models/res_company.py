from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    hc_probation_alert_days = fields.Char(
        string='Probation Alert Days', default='30,14,7',
        help="Comma separated number of days before the probation end date at which a review activity is raised.")
    hc_contract_alert_days = fields.Integer(
        string='Contract Expiry Alert Days', default=60,
        help="Default number of days before contract end at which renewal activities are raised.")
    hc_credential_alert_days = fields.Char(
        string='Credential Alert Days', default='90,60,30,7',
        help="Comma separated reminder thresholds for expiring credentials.")
    hc_training_alert_days = fields.Integer(string='Training Alert Days', default=30)
    hc_alert_user_id = fields.Many2one(
        'res.users', string='Default HR Alert Responsible',
        help="Receives healthcare HR alerts when no HR responsible is set on the employee.")

    def _hc_parse_days(self, value):
        """'90,60,30,7' -> [90, 60, 30, 7] (descending, invalid parts ignored)."""
        days = set()
        for part in (value or '').split(','):
            part = part.strip()
            if part.isdigit():
                days.add(int(part))
        return sorted(days, reverse=True)
