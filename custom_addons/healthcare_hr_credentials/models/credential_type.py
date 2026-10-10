from odoo import fields, models


class CredentialType(models.Model):
    _name = 'healthcare.hr.credential.type'
    _description = 'Credential Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    credential_category = fields.Selection([
        ('license', 'Professional License'),
        ('registration', 'Registration / Classification'),
        ('certification', 'Clinical Certification'),
        ('permit', 'Work / Residency Permit'),
        ('identity', 'Identity Document'),
        ('insurance', 'Insurance'),
        ('other', 'Other'),
    ], required=True, default='certification')
    mandatory = fields.Boolean(help="Required for the employees in scope (see Jobs / Clinical only).")
    clinical_only = fields.Boolean(help="In scope: clinical employees only (doctors, nurses, technicians).")
    job_ids = fields.Many2many('hr.job', string='Required for Jobs',
                               help="Restrict the requirement to these positions. Empty = every employee in scope.")
    blocks_shift_assignment = fields.Boolean(
        help="An employee without a valid credential of this type cannot be published on a shift.")
    has_expiry = fields.Boolean(default=True)
    default_alert_days = fields.Integer(
        help="First reminder before expiry. Empty = company thresholds (Settings).")
    confidential = fields.Boolean(help="Visible to Healthcare HR officers only (not to department managers).")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique (code)', 'The credential type code must be unique.')

    def _applies_to(self, employee):
        """True when this (mandatory) type is required for ``employee``."""
        self.ensure_one()
        if self.clinical_only and not employee.is_clinical:
            return False
        if self.job_ids and employee.job_id not in self.job_ids:
            return False
        return True
