from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hc_night_start = fields.Float(related='company_id.hc_night_start', readonly=False)
    hc_night_end = fields.Float(related='company_id.hc_night_end', readonly=False)
    hc_max_weekly_hours = fields.Float(related='company_id.hc_max_weekly_hours', readonly=False)
    hc_max_shift_hours = fields.Float(related='company_id.hc_max_shift_hours', readonly=False)
    hc_default_rest_hours = fields.Float(related='company_id.hc_default_rest_hours', readonly=False)
    hc_shift_match_window = fields.Float(related='company_id.hc_shift_match_window', readonly=False)
