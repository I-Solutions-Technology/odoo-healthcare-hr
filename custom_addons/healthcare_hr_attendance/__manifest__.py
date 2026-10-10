{
    'name': 'Healthcare HR Attendance & Reconciliation',
    'summary': 'Match attendance to planned shifts, compute late / early leave / extra time / '
               'night / weekend / holiday hours and reconcile them into approved work data for payroll',
    'description': """
Healthcare Attendance
=====================
Extends the standard attendance (hr.attendance) instead of replacing it:

* Each attendance is matched to its planned shift (cross-midnight aware).
* Late minutes, early leave, extra time, night / weekend / holiday hours, status
  (present, late, early leave, partial, on leave, missing checkout, unplanned).
* Reconciliation batches turn shift + raw attendance + approved leave + public holidays +
  overtime policy into approved work data. Worked extra time, approved overtime and
  payroll overtime are kept separate: extra time is never paid automatically.
* Daily idempotent cron: reconcile yesterday, alert on missing checkouts and unresolved issues.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_shift', 'hr_attendance'],
    'data': [
        'security/attendance_security.xml',
        'security/ir.model.access.csv',
        'security/attendance_rules.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/hr_attendance_views.xml',
        'views/shift_assignment_views.xml',
        'views/reconciliation_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_attendance.xml',
    ],
    'installable': True,
}
