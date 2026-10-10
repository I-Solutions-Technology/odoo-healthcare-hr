{
    'name': 'Healthcare HR Contracts & Probation',
    'summary': 'Healthcare contract types, probation workflow and reviews, renewal policy and '
               'contract/probation expiry alerts on Odoo 19 employee versions',
    'description': """
Healthcare HR Contracts
=======================
In Odoo 19 the employment contract is carried by the employee *version* (hr.version).
This module extends it rather than re-creating a contract model:

* Healthcare contract types (locum, visiting, consultant, trainee, intern, outsourced ...).
* Probation start/end (end = standard "End of Trial Period"), probation status workflow
  and probation review records. A review never terminates an employee automatically.
* Renewal policy (manual / automatic / non-renewable), notice and alert windows.
* Licence / insurance requirement flags used by the shift validation engine.
* Daily idempotent alerts for probation and contract expiry.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_core'],
    'data': [
        'security/ir.model.access.csv',
        'security/contract_rules.xml',
        'data/hr_contract_type_data.xml',
        'data/ir_cron_data.xml',
        'wizard/contract_renew_wizard_views.xml',
        'views/hr_version_views.xml',
        'views/probation_review_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_contract.xml',
    ],
    'installable': True,
}
