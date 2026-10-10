{
    'name': 'Healthcare HR Training',
    'summary': 'Training requirement matrix (job / category / department -> certification), training '
               'assignments that renew credentials, compliance, expiry alerts and reports',
    'description': """
Healthcare HR Training
======================
* Training Requirement Matrix: which certification (credential type) is required for which job,
  healthcare category and/or department (e.g. Nurse -> BLS, ICU nurse -> ACLS,
  Radiology technician -> Radiation Safety, Lab technician -> Infection Control).
* Training assignments generated idempotently from the matrix. Employees who already hold a valid
  credential of the required type (not expiring within the company training alert window) are skipped.
* The credential record is the certification: completing a training creates or renews the employee's
  credential (number, issue date, expiry date = completion + renewal period), left under verification
  or verified automatically depending on the requirement.
* Daily cron: generate assignments, mark expired trainings, idempotent alerts for trainings expiring
  within the company "Training Alert Days" and for missing mandatory training.
* Reports: Missing Training, Expiring Certifications, Training Compliance (rate by department).
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_credentials'],
    'data': [
        'security/ir.model.access.csv',
        'security/training_rules.xml',
        'data/ir_cron_data.xml',
        'views/training_requirement_views.xml',
        'views/training_assignment_views.xml',
        'views/compliance_report_views.xml',
        'views/hr_employee_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_training.xml',
    ],
    'installable': True,
}
