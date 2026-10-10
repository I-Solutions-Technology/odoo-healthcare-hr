from odoo import fields, models


class ShiftTemplate(models.Model):
    _inherit = 'healthcare.shift.template'

    allowance_rule_ids = fields.Many2many(
        'healthcare.allowance.rule', 'healthcare_allowance_rule_shift_template_rel', 'template_id', 'rule_id',
        string='Allowance Rules', help="Allowance rules restricted to this shift template.")
