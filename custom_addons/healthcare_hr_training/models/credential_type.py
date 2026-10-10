from odoo import fields, models


class CredentialType(models.Model):
    _inherit = 'healthcare.hr.credential.type'

    training_requirement_ids = fields.One2many('healthcare.training.requirement', 'credential_type_id',
                                               string='Training Requirements')
