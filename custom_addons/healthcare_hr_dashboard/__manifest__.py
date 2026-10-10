{
    'name': 'Healthcare HR Dashboard',
    'summary': 'Headcount, attendance, workforce, compliance and payroll KPIs for hospitals and '
               'clinics, filtered by branch, with drill-down to the underlying records',
    'description': """
Healthcare HR Dashboard
=======================
One screen per user, computed on open with aggregated queries (search_count / _read_group,
never loading employee records into Python):

* Headcount: total, doctors, nurses, technicians, administrative, new hires, exits.
* Attendance today: present, absent, late, on leave, missing checkout, overtime this month.
* Workforce: scheduled today, shortages, open (draft) shifts, conflicts, night shifts.
* Compliance: contracts expiring, probation ending, licenses expiring, expired credentials,
  missing / expired training (when the training module is installed).
* Payroll (payroll officers only): payroll, overtime and allowance cost this month.

Every tile opens the filtered list.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_clearance'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'healthcare_hr_dashboard/static/src/scss/dashboard.scss',
        ],
    },
    'installable': True,
}
