from odoo import api, fields, models


class HrRecruitmentStage(models.Model):
    _inherit = 'hr.recruitment.stage'

    hc_credential_verification = fields.Boolean(
        string='Credential Verification Stage',
        help="Stage in which HR verifies the licenses and certifications of the applicant. "
             "Applicants can only move to a hired stage once their credentials are verified.")

    @api.model
    def _hc_place_credential_stage(self):
        """Keep the hired stages after the credential verification stage (idempotent)."""
        verification = self.search([('hc_credential_verification', '=', True)], order='sequence', limit=1)
        if not verification:
            return
        hired = self.search([('hired_stage', '=', True), ('sequence', '<=', verification.sequence)])
        for stage in hired:
            stage.sequence = verification.sequence + 1
