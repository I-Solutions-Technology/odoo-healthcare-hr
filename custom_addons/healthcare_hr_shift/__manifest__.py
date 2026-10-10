{
    'name': 'Healthcare HR Shift Planning',
    'summary': 'Medical and nursing rosters: shift templates (8/12/24h, night, on-call), '
               'assignments with a validation engine, coverage rules, shift swaps, on-call '
               'and Odoo Planning integration',
    'description': """
Healthcare Shift Planning
=========================
* Shift templates with midnight-crossing times, breaks, grace, rest rules and allowed jobs.
* Shift assignments computed in the employee time zone, stored in UTC.
* Validation engine before publication: overlaps, duplicates, simultaneous branches,
  approved leave, contract validity, blocking credentials, minimum rest, weekly hours,
  incompatible pattern, unauthorised weekend or 24-hour shifts.
* Coverage rules (minimum / preferred per branch, department, unit, shift, category, job)
  with daily shortage snapshots and optional publication blocking.
* Shift swap workflow (employee -> colleague -> manager -> scheduling) with re-validation.
* On-call rosters with call-in tracking.
* Published assignments are mirrored as Odoo Planning shifts.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_credentials', 'hr_holidays', 'planning'],
    'data': [
        'security/ir.model.access.csv',
        'security/shift_rules.xml',
        'data/shift_template_data.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'wizard/shift_publish_wizard_views.xml',
        'wizard/shift_generate_wizard_views.xml',
        'views/shift_template_views.xml',
        'views/shift_assignment_views.xml',
        'views/coverage_views.xml',
        'views/shift_swap_views.xml',
        'views/shift_oncall_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_shift.xml',
    ],
    'installable': True,
}
