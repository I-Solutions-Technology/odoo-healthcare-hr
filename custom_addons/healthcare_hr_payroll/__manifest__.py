{
    'name': 'Healthcare HR Payroll Integration',
    'summary': 'Feeds Odoo Payroll with approved healthcare work data: allowances, approved '
               'overtime, on-call, bonuses, deductions and loan installments, through '
               'idempotent payroll inputs',
    'description': """
Healthcare Payroll Integration
==============================
Odoo Payroll is not rewritten. This module produces *payroll inputs* (staging records with a
unique processing key, a period, the source model and record) and injects them as standard
payslip "Other Inputs":

Contract + Work Entries + Attendance + Shift + Leave + Approved Overtime + Allowances + Loans
-> Payroll inputs -> Payslip -> Accounting (hr_payroll_account) -> Bank batch.

* Repeated generation never duplicates an input (unique key per source).
* Inputs are linked to the payslip that consumed them; validating the payslip marks
  shifts, allowances and on-call duties as processed; cancelling releases them.
* Salary rules reading the healthcare inputs can be added to any structure (country
  localisations keep their own structures and taxes).
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_allowance', 'hr_payroll'],
    'data': [
        'security/payroll_security.xml',
        'security/ir.model.access.csv',
        'security/payroll_rules.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/allowance_type_mapping_data.xml',
        'data/ir_cron_data.xml',
        'wizard/payroll_input_generate_wizard_views.xml',
        'views/payroll_input_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_payroll.xml',
    ],
    'installable': True,
}
