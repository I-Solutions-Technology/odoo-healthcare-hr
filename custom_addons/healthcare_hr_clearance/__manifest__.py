{
    'name': 'Healthcare HR Exit, Clearance & Final Settlement',
    'summary': 'Employee exit workflow with department clearance (HR, Finance, IT, Medical Equipment, '
               'Security ...) and a configurable final settlement engine',
    'description': """
Exit, Clearance & Final Settlement
==================================
Exit Initiated -> Clearance Started -> Department Approvals -> Final Settlement -> HR Approval
-> Employee Archived.

* Clearance departments are configurable; the employee's department item goes to the
  department manager. Items can carry obligations (unreturned equipment, advances ...).
* Final settlement components are configurable records (final salary, unused leave,
  pending overtime / allowances / bonuses, deductions, outstanding loans, clearance
  obligations, end of service, other) computed by method or by formula. No labour-law
  rule is hard-coded: end of service is a formula to configure per country.
* HR approval archives the employee (standard departure fields), ends the contract,
  cancels future shifts and settles loans and pending payroll inputs.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_loan'],
    'data': [
        'security/ir.model.access.csv',
        'security/clearance_rules.xml',
        'data/clearance_data.xml',
        'report/final_settlement_report.xml',
        'views/exit_views.xml',
        'views/settlement_views.xml',
        'views/config_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
