{
    'name': 'Healthcare HR Core',
    'summary': 'Healthcare organisation structure (hospital, branch, unit), clinical employee '
               'data, practitioner bridge, onboarding checklist and the suite security groups',
    'description': """
Healthcare HR Core
==================
Foundation of the Healthcare HR Management Suite for Odoo 19.

* Hospital / clinic / branch hierarchy and clinical units under departments.
* Employee category (doctor, nurse, pharmacist ...), employment status, Arabic name,
  employee number, medical specialty and sub-specialty on the standard employee.
* Bridge to external clinical practitioner records (no tight coupling to any EMR).
* Onboarding checklist with configurable items.
* The suite security groups and branch-level record rules.

Standard fields are reused: national ID (identification_id), passport (passport_id),
nationality (country_id), contract dates and wage (hr.version).
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['hr', 'mail'],
    'data': [
        'security/healthcare_hr_security.xml',
        'security/ir.model.access.csv',
        'security/healthcare_hr_rules.xml',
        'data/ir_sequence_data.xml',
        'data/onboarding_item_data.xml',
        'data/medical_specialty_data.xml',
        'views/healthcare_branch_views.xml',
        'views/healthcare_unit_views.xml',
        'views/medical_specialty_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_department_views.xml',
        'views/hr_job_views.xml',
        'views/practitioner_link_views.xml',
        'views/onboarding_views.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_core.xml',
    ],
    'installable': True,
    'application': True,
}
