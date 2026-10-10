from odoo import api, fields, models

EMPLOYEE_CATEGORIES = [
    ('doctor', 'Doctor'),
    ('nurse', 'Nurse'),
    ('pharmacist', 'Pharmacist'),
    ('lab_technician', 'Laboratory Technician'),
    ('radiology_doctor', 'Radiology Doctor'),
    ('radiology_technician', 'Radiology Technician'),
    ('medical_technician', 'Medical Technician'),
    ('administrative', 'Administrative'),
    ('reception', 'Reception'),
    ('call_center', 'Call Center'),
    ('finance', 'Finance'),
    ('hr', 'Human Resources'),
    ('management', 'Management'),
    ('other', 'Other'),
]

CLINICAL_CATEGORIES = (
    'doctor', 'nurse', 'pharmacist', 'lab_technician', 'radiology_doctor',
    'radiology_technician', 'medical_technician',
)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # --- General (national ID, passport and nationality are the standard
    #     identification_id, passport_id and country_id fields) ---
    employee_number = fields.Char(
        string='Employee Number', copy=False, index=True, groups='hr.group_hr_user', tracking=True,
        help="Personnel number. Generated from the 'Healthcare Employee Number' sequence when empty.")
    arabic_name = fields.Char(string='Arabic Name', tracking=True)
    hire_date = fields.Date(string='Hire Date', groups='hr.group_hr_user', tracking=True,
                            help="Original hiring date, kept across contract versions.")
    employee_category = fields.Selection(EMPLOYEE_CATEGORIES, string='Healthcare Category', index=True,
                                         tracking=True)
    is_clinical = fields.Boolean(compute='_compute_is_clinical', store=True,
                                 help="Doctors, nurses, pharmacists and technicians.")
    employment_status = fields.Selection([
        ('onboarding', 'Onboarding'),
        ('probation', 'On Probation'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('notice', 'Notice Period'),
        ('exited', 'Exited'),
    ], string='Employment Status', default='active', index=True, tracking=True, groups='hr.group_hr_user')

    # --- Organisational ---
    healthcare_branch_id = fields.Many2one('healthcare.hr.branch', string='Branch', index=True,
                                           check_company=True, tracking=True)
    healthcare_unit_id = fields.Many2one('healthcare.hr.unit', string='Unit', index=True,
                                         check_company=True, tracking=True,
                                         domain="[('department_id', '=?', department_id)]")
    medical_department_id = fields.Many2one(
        'hr.department', string='Medical Department', check_company=True,
        help="Clinical department when it differs from the administrative department "
             "(e.g. a nurse administratively in Nursing, clinically in ICU).")

    # --- Clinical (licence numbers and expiry live on credential records) ---
    medical_specialty_id = fields.Many2one('healthcare.medical.specialty', string='Specialty',
                                           domain="[('parent_id', '=', False)]", tracking=True)
    sub_specialty_id = fields.Many2one('healthcare.medical.specialty', string='Sub-specialty',
                                       domain="[('parent_id', '=', medical_specialty_id)]", tracking=True)
    practitioner_reference = fields.Char(
        string='Practitioner Reference', groups='hr.group_hr_user',
        help="Code of the practitioner in the clinical system (EMR / scheduling).")
    professional_registration_number = fields.Char(
        string='Professional Registration No.', groups='hr.group_hr_user', tracking=True,
        help="Registration with the health authority / professional council. "
             "License numbers, dates and verification are tracked on credential records.")
    practitioner_link_ids = fields.One2many('healthcare.employee.practitioner.link', 'employee_id',
                                            string='Practitioner Links', groups='hr.group_hr_user')
    onboarding_ids = fields.One2many('healthcare.hr.onboarding', 'employee_id', string='Onboarding',
                                     groups='hr.group_hr_user')

    _employee_number_company_uniq = models.Constraint(
        'unique (employee_number, company_id)',
        'The employee number must be unique per company.',
    )

    @api.depends('employee_category')
    def _compute_is_clinical(self):
        for employee in self:
            employee.is_clinical = employee.employee_category in CLINICAL_CATEGORIES

    @api.onchange('job_id')
    def _onchange_job_id_healthcare_category(self):
        if self.job_id.employee_category and not self.employee_category:
            self.employee_category = self.job_id.employee_category

    @api.onchange('department_id')
    def _onchange_department_id_healthcare_branch(self):
        if self.department_id.healthcare_branch_id:
            self.healthcare_branch_id = self.department_id.healthcare_branch_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('employee_number'):
                vals['employee_number'] = self.env['ir.sequence'].sudo().next_by_code('healthcare.hr.employee') or False
            if not vals.get('employee_category') and vals.get('job_id'):
                vals['employee_category'] = self.env['hr.job'].browse(vals['job_id']).employee_category
            if not vals.get('healthcare_branch_id') and vals.get('department_id'):
                branch = self.env['hr.department'].browse(vals['department_id']).healthcare_branch_id
                vals['healthcare_branch_id'] = branch.id or False
        return super().create(vals_list)
