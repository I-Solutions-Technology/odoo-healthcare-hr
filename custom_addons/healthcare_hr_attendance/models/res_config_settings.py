from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hc_overtime_min_minutes = fields.Integer(related='company_id.hc_overtime_min_minutes', readonly=False)
    hc_overtime_rounding_minutes = fields.Integer(related='company_id.hc_overtime_rounding_minutes', readonly=False)
    hc_overtime_auto_propose = fields.Boolean(related='company_id.hc_overtime_auto_propose', readonly=False)
    hc_missing_checkout_hours = fields.Float(related='company_id.hc_missing_checkout_hours', readonly=False)
