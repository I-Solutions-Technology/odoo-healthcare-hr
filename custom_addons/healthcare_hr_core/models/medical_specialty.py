from odoo import api, fields, models


class MedicalSpecialty(models.Model):
    _name = 'healthcare.medical.specialty'
    _description = 'Medical Specialty'
    _parent_store = True
    _order = 'complete_name'
    _rec_name = 'complete_name'

    name = fields.Char(required=True, translate=True)
    complete_name = fields.Char(compute='_compute_complete_name', store=True, recursive=True)
    code = fields.Char()
    parent_id = fields.Many2one('healthcare.medical.specialty', string='Parent Specialty', index=True,
                                ondelete='restrict', help="Set for a sub-specialty.")
    parent_path = fields.Char(index=True)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique (code)', 'The specialty code must be unique.')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for spec in self:
            spec.complete_name = f'{spec.parent_id.complete_name} / {spec.name}' if spec.parent_id else spec.name
