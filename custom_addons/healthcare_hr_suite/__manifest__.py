{
    'name': 'Healthcare HR Management Suite',
    'summary': 'Installs the complete Hospital & Clinic HR suite: workforce scheduling, biometric '
               'attendance, allowances, payroll integration, credentials, training, recruitment, '
               'performance, loans, exit and bank payroll',
    'description': """
Healthcare HR Management Suite
==============================
Meta module: installing it installs every Healthcare HR module. Each module can also be
installed on its own (see ARCHITECTURE.md for the dependency graph).
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': [
        'healthcare_hr_core',
        'healthcare_hr_contract',
        'healthcare_hr_credentials',
        'healthcare_hr_shift',
        'healthcare_hr_attendance',
        'healthcare_hr_biometric',
        'healthcare_hr_allowance',
        'healthcare_hr_payroll',
        'healthcare_hr_loan',
        'healthcare_hr_training',
        'healthcare_hr_appraisal',
        'healthcare_hr_recruitment',
        'healthcare_hr_clearance',
        'healthcare_hr_bank',
        'healthcare_hr_dashboard',
    ],
    'installable': True,
    'application': True,
}
