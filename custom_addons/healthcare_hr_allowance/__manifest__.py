{
    'name': 'Healthcare HR Allowances',
    'summary': 'Allowance rule engine for healthcare: night, weekend, holiday, on-call, call-in, '
               'risk, ICU/ER/OR, housing, transport ... fixed, per shift, per hour, % of basic, '
               '% of gross or formula, computed from approved work data',
    'description': """
Healthcare Allowances
=====================
* Allowance types (night shift, weekend, public holiday, risk, transportation, housing,
  responsibility, on call, call in, remote area, infection risk, ICU, ER, operating room,
  performance, other) with a taxable flag and a payroll input code.
* Rules filtered by effective dates, company, branch, department, unit, employee category,
  job, contract type, shift type or shift templates.
* Calculation: fixed, per shift, per hour (night / weekend / holiday / worked / overtime /
  on-call hours), percentage of basic, percentage of gross, or a safe formula; min / max per period.
* Results per employee, rule and period are recomputed idempotently from *approved*
  shifts and on-call duties only, then confirmed for payroll.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'security/allowance_rules.xml',
        'data/allowance_type_data.xml',
        'wizard/allowance_compute_wizard_views.xml',
        'views/allowance_type_views.xml',
        'views/allowance_rule_views.xml',
        'views/allowance_result_views.xml',
        'views/shift_template_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_allowance.xml',
    ],
    'installable': True,
}
