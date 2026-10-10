from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ApplicantCredential(models.Model):
    _name = 'healthcare.applicant.credential'
    _description = 'Applicant Credential'
    _order = 'applicant_id, id'

    applicant_id = fields.Many2one('hr.applicant', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='applicant_id.company_id', store=True, index=True)
    credential_type_id = fields.Many2one('healthcare.hr.credential.type', required=True, index=True)
    credential_number = fields.Char()
    issuing_authority = fields.Char()
    issue_date = fields.Date()
    expiry_date = fields.Date()
    attachment_ids = fields.Many2many('ir.attachment', 'healthcare_applicant_credential_attachment_rel',
                                      'line_id', 'attachment_id', string='Documents')
    verified = fields.Boolean(readonly=True, copy=False)
    verified_by = fields.Many2one('res.users', readonly=True, copy=False)
    verification_date = fields.Date(readonly=True, copy=False)
    required = fields.Boolean(compute='_compute_required')
    note = fields.Char()

    @api.depends('credential_type_id', 'applicant_id.required_credential_type_ids')
    def _compute_required(self):
        for line in self:
            line.required = line.credential_type_id in line.applicant_id.required_credential_type_ids

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for line in self:
            if line.issue_date and line.expiry_date and line.expiry_date < line.issue_date:
                raise ValidationError(self.env._('The expiry date cannot be before the issue date.'))

    def is_valid_on(self, on_date):
        self.ensure_one()
        return bool(self.verified and (not self.expiry_date or self.expiry_date >= on_date))

    def action_verify(self):
        today = fields.Date.context_today(self)
        for line in self:
            if not line.credential_number and not line.attachment_ids:
                raise UserError(self.env._('Add the %s number or a scanned document before verifying.',
                                           line.credential_type_id.name))
            if line.expiry_date and line.expiry_date < today:
                raise UserError(self.env._('The %s of the applicant is expired.', line.credential_type_id.name))
        self.write({'verified': True, 'verified_by': self.env.uid, 'verification_date': today})
        return True

    def action_reset_verification(self):
        self.write({'verified': False, 'verified_by': False, 'verification_date': False})
        return True

    def write(self, vals):
        # a new number or expiry date must be verified again
        if 'verified' not in vals and {'credential_number', 'expiry_date', 'credential_type_id'} & set(vals):
            vals = dict(vals, verified=False, verified_by=False, verification_date=False)
        return super().write(vals)
