{
    'name': 'Healthcare HR Credentials',
    'summary': 'Professional licenses, mandatory certifications (BLS, ACLS, PALS ...), permits and '
               'malpractice insurance with verification, expiry status, alerts and shift blocking',
    'description': """
Healthcare HR Credentials
=========================
* Credential types with category, mandatory flag, applicable jobs and "blocks shift assignment".
* Credential records per employee: number, authority, dates, attachments, verification.
* Status: valid, expiring, expired, missing, under verification (recomputed daily).
* Idempotent alerts at configurable thresholds (default 90/60/30/7 days and on expiry).
* Placeholder "missing" credentials generated for mandatory requirements.
* Service used by the shift validation engine to block unqualified assignments.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_contract'],
    'data': [
        'security/ir.model.access.csv',
        'security/credential_rules.xml',
        'data/credential_type_data.xml',
        'data/ir_cron_data.xml',
        'views/credential_type_views.xml',
        'views/credential_views.xml',
        'views/hr_employee_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_credentials.xml',
    ],
    'installable': True,
}
