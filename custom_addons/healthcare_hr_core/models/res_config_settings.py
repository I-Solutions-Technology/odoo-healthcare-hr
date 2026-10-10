from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hc_probation_alert_days = fields.Char(related='company_id.hc_probation_alert_days', readonly=False)
    hc_contract_alert_days = fields.Integer(related='company_id.hc_contract_alert_days', readonly=False)
    hc_credential_alert_days = fields.Char(related='company_id.hc_credential_alert_days', readonly=False)
    hc_training_alert_days = fields.Integer(related='company_id.hc_training_alert_days', readonly=False)
    hc_alert_user_id = fields.Many2one(related='company_id.hc_alert_user_id', readonly=False)
