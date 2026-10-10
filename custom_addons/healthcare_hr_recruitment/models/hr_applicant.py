from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.healthcare_hr_core.models.hr_employee import CLINICAL_CATEGORIES, EMPLOYEE_CATEGORIES

VERIFICATION_STATUS = [
    ('not_started', 'Not Started'),
    ('in_progress', 'In Progress'),
    ('verified', 'Verified'),
    ('failed', 'Failed'),
]
# fields that can change the verification status in the same write as a stage change
STATUS_FIELDS = {'hc_credential_line_ids', 'required_credential_type_ids', 'hc_verification_failed',
                 'job_id', 'employee_category'}


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    arabic_name = fields.Char(string='Arabic Name')
    healthcare_specialty_id = fields.Many2one('healthcare.medical.specialty', string='Specialty', tracking=True)
    years_experience = fields.Float(string='Years of Experience', tracking=True)
    professional_license = fields.Char(string='Professional License No.', tracking=True)
    classification = fields.Selection([
        ('consultant', 'Consultant'),
        ('specialist', 'Specialist'),
        ('resident', 'Resident'),
        ('general_practitioner', 'General Practitioner'),
        ('registered_nurse', 'Registered Nurse'),
        ('assistant_nurse', 'Assistant Nurse'),
        ('technician', 'Technician'),
        ('pharmacist', 'Pharmacist'),
        ('non_clinical', 'Non Clinical'),
    ], string='Professional Classification', tracking=True,
        help="Grade granted by the health authority / professional council.")
    employee_category = fields.Selection(EMPLOYEE_CATEGORIES, string='Healthcare Category',
                                         compute='_compute_employee_category', store=True, readonly=False)
    required_credential_type_ids = fields.Many2many(
        'healthcare.hr.credential.type', 'hr_applicant_required_credential_type_rel', 'applicant_id', 'type_id',
        string='Required Credentials', compute='_compute_required_credential_type_ids', store=True, readonly=False,
        help="Defaults to the mandatory credential types of the job position.")
    hc_credential_line_ids = fields.One2many('healthcare.applicant.credential', 'applicant_id',
                                             string='Applicant Credentials')
    credential_verification_status = fields.Selection(
        VERIFICATION_STATUS, string='Credential Verification', compute='_compute_credential_verification_status',
        store=True, index=True, tracking=True,
        help="Verified: every required credential has a verified, non expired line (or nothing is required and "
             "every provided line is verified). Hiring is blocked until then.")
    hc_verification_failed = fields.Boolean(string='Verification Failed', copy=False, tracking=True)
    hc_verification_note = fields.Char(string='Verification Note', copy=False)

    @api.depends('job_id')
    def _compute_employee_category(self):
        for applicant in self:
            if applicant.job_id.employee_category or not applicant.employee_category:
                applicant.employee_category = applicant.job_id.employee_category

    @api.depends('job_id', 'employee_category')
    def _compute_required_credential_type_ids(self):
        types = self.env['healthcare.hr.credential.type'].search([('mandatory', '=', True)])
        for applicant in self:
            applicant.required_credential_type_ids = types.filtered(lambda t: applicant._hc_requires_type(t))

    def _hc_requires_type(self, ctype):
        """Same scope rule as healthcare.hr.credential.type._applies_to, on the future employee."""
        self.ensure_one()
        if ctype.clinical_only and self.employee_category not in CLINICAL_CATEGORIES:
            return False
        if ctype.job_ids and self.job_id not in ctype.job_ids:
            return False
        return True

    @api.depends('hc_credential_line_ids.verified', 'hc_credential_line_ids.credential_type_id',
                 'hc_credential_line_ids.expiry_date', 'required_credential_type_ids', 'hc_verification_failed')
    def _compute_credential_verification_status(self):
        today = fields.Date.context_today(self)
        for applicant in self:
            lines = applicant.hc_credential_line_ids
            covered = lines.filtered(lambda l: l.is_valid_on(today)).credential_type_id
            required = applicant.required_credential_type_ids
            if applicant.hc_verification_failed:
                status = 'failed'
            elif required:
                status = 'verified' if not (required - covered) else ('in_progress' if lines else 'not_started')
            else:
                status = 'verified' if all(l.is_valid_on(today) for l in lines) else 'in_progress'
            applicant.credential_verification_status = status

    # ------------------------------------------------------------------
    # Verification gate
    # ------------------------------------------------------------------
    def _hc_check_credentials_verified(self):
        self._compute_credential_verification_status()  # expiry dates move with time
        blocked = self.filtered(lambda a: a.credential_verification_status != 'verified')
        if blocked:
            details = []
            for applicant in blocked:
                missing = applicant.required_credential_type_ids - applicant.hc_credential_line_ids.filtered(
                    lambda l: l.is_valid_on(fields.Date.context_today(self))).credential_type_id
                status = dict(VERIFICATION_STATUS)[applicant.credential_verification_status]
                details.append(self.env._('%(name)s: %(status)s%(missing)s', name=applicant.partner_name or applicant.display_name,
                                          status=status,
                                          missing=(' - ' + ', '.join(missing.mapped('name'))) if missing else ''))
            raise UserError(self.env._(
                'Credentials must be verified before hiring (Credential Verification stage):\n%s',
                '\n'.join(details)))

    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)
        applicants.filtered(lambda a: a.stage_id.hired_stage)._hc_check_credentials_verified()
        return applicants

    def write(self, vals):
        moving = self.browse()
        if vals.get('stage_id'):
            stage = self.env['hr.recruitment.stage'].browse(vals['stage_id'])
            if stage.hired_stage:
                moving = self.filtered(lambda a: not a.stage_id.hired_stage)
        if moving and not STATUS_FIELDS & set(vals):
            # check before writing: nothing in vals can change the verification status
            moving._hc_check_credentials_verified()
            return super().write(vals)
        res = super().write(vals)
        moving._hc_check_credentials_verified()
        return res

    def action_hc_verification_failed(self):
        for applicant in self:
            if not applicant.hc_verification_note:
                raise UserError(self.env._('Enter the verification note (reason) first.'))
        self.write({'hc_verification_failed': True})
        return True

    def action_hc_reset_verification(self):
        self.write({'hc_verification_failed': False})
        return True

    # ------------------------------------------------------------------
    # Applicant -> employee
    # ------------------------------------------------------------------
    def _get_employee_create_vals(self):
        vals = super()._get_employee_create_vals()
        specialty = self.healthcare_specialty_id
        vals.update({
            'employee_category': self.employee_category or self.job_id.employee_category or False,
            'medical_specialty_id': (specialty.parent_id or specialty).id or False,
            'sub_specialty_id': specialty.id if specialty.parent_id else False,
            'hire_date': self.availability or fields.Date.context_today(self),
            'professional_registration_number': self.professional_license or False,
        })
        if self.arabic_name:
            vals['arabic_name'] = self.arabic_name
        return vals

    def create_employee_from_applicant(self):
        self.ensure_one()
        self._hc_check_credentials_verified()
        action = super().create_employee_from_applicant()
        employee = self.employee_id or self.env['hr.employee'].browse(action.get('res_id'))
        if employee:
            self._hc_handover_to_employee(employee)
        return action

    def _hc_handover_to_employee(self, employee):
        """Create the employee credentials from the applicant lines and open the onboarding.

        Done with sudo: recruiters hand over verified documents but do not manage employee
        credentials or onboarding checklists themselves.
        """
        self.ensure_one()
        Credential = self.env['healthcare.hr.credential'].sudo()
        existing = {c.credential_type_id.id: c for c in Credential.search([('employee_id', '=', employee.id)])}
        for line in self.hc_credential_line_ids:
            vals = {
                'credential_number': line.credential_number,
                'issuing_authority': line.issuing_authority,
                'issue_date': line.issue_date,
                'expiry_date': line.expiry_date,
                'verified': line.verified,
                'verified_by': line.verified_by.id if line.verified else False,
                'verification_date': line.verification_date if line.verified else False,
                'notes': self.env._('Verified during recruitment (application %s).', self.display_name)
                if line.verified else self.env._('Provided during recruitment (application %s).', self.display_name),
            }
            cred = existing.get(line.credential_type_id.id)
            if cred:
                cred.write(vals)
            else:
                cred = Credential.create(dict(vals, employee_id=employee.id,
                                              credential_type_id=line.credential_type_id.id))
                existing[line.credential_type_id.id] = cred
            if line.attachment_ids:
                copies = line.attachment_ids.sudo().copy({'res_model': cred._name, 'res_id': cred.id})
                cred.attachment_ids = [fields.Command.link(att.id) for att in copies]
        Onboarding = self.env['healthcare.hr.onboarding'].sudo()
        if not Onboarding.search_count([('employee_id', '=', employee.id), ('state', 'in', ('draft', 'in_progress'))]):
            Onboarding.create({'employee_id': employee.id,
                               'start_date': self.availability or fields.Date.context_today(self)})
        return True
