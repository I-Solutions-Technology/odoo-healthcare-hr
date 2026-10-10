{
    'name': 'Healthcare HR Recruitment',
    'summary': 'Healthcare applicant data, credential verification gate before hiring and '
               'applicant-to-employee handover (credentials + onboarding)',
    'description': """
Healthcare HR Recruitment
=========================
Extends the standard Odoo 19 Recruitment application. In Odoo 19 the application (hr.applicant)
carries the candidate data and the employee is created from it (create_employee_from_applicant);
this module extends that flow instead of replacing it.

Flow: Applicant, Interview, Offer, Credential Verification, Employee, Contract, Onboarding, Probation.

* Applicant: specialty, years of experience, professional license number, classification,
  healthcare category, Arabic name and required credential types (defaulted from the mandatory
  credential types of the job position).
* Applicant credential lines (type, number, authority, expiry, documents, verified) and a credential
  verification status: not started, in progress, verified, failed.
* A "Credential Verification" pipeline stage placed before the hired stage(s).
* Gate: an applicant cannot reach a hired stage, nor become an employee, unless the credential
  verification status is "Verified".
* Employee creation copies the specialty, category, Arabic name and license number, creates the
  employee credentials from the applicant lines (verified lines stay verified) and opens an
  onboarding checklist. Contract and probation then follow the Healthcare Contracts workflow.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_credentials', 'hr_recruitment'],
    'data': [
        'security/recruitment_security.xml',
        'security/ir.model.access.csv',
        'security/recruitment_rules.xml',
        'data/hr_recruitment_stage_data.xml',
        'views/hr_applicant_views.xml',
        'views/hr_recruitment_stage_views.xml',
        'views/recruitment_report_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_recruitment.xml',
    ],
    'installable': True,
}
