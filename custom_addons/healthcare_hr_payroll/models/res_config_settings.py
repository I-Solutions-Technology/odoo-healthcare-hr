from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hc_overtime_rate = fields.Float(related='company_id.hc_overtime_rate', readonly=False)
    hc_payroll_monthly_hours = fields.Float(related='company_id.hc_payroll_monthly_hours', readonly=False)
