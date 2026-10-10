from odoo import fields, models

ALLOWANCE_CATEGORIES = [
    ('night_shift', 'Night Shift'),
    ('weekend', 'Weekend'),
    ('public_holiday', 'Public Holiday'),
    ('risk', 'Risk'),
    ('transportation', 'Transportation'),
    ('housing', 'Housing'),
    ('responsibility', 'Responsibility'),
    ('on_call', 'On Call'),
    ('call_in', 'Call In'),
    ('remote_area', 'Remote Area'),
    ('infection_risk', 'Infection Risk'),
    ('icu', 'ICU'),
    ('er', 'ER'),
    ('operating_room', 'Operating Room'),
    ('performance', 'Performance'),
    ('other', 'Other'),
]


class AllowanceType(models.Model):
    _name = 'healthcare.allowance.type'
    _description = 'Allowance Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Also used as the payroll input code (prefixed HC_ when mapped).")
    sequence = fields.Integer(default=10)
    category = fields.Selection(ALLOWANCE_CATEGORIES, required=True, default='other')
    taxable = fields.Boolean(default=True, help="Informative flag for localisations deciding the tax treatment.")
    active = fields.Boolean(default=True)
    rule_ids = fields.One2many('healthcare.allowance.rule', 'type_id', string='Rules')

    _code_uniq = models.Constraint('unique (code)', 'The allowance type code must be unique.')
