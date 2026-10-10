{
    'name': 'Healthcare HR Loans & Salary Advances',
    'summary': 'Employee loans and salary advances with approval workflow, installment schedule '
               'and automatic deduction through healthcare payroll inputs',
    'description': """
Loans & Salary Advances
=======================
Draft -> Submitted -> Approved -> Paid -> Active -> Completed.

* Installment schedule generated from the approved amount, count and first deduction date.
* Due installments become payroll inputs (unique key per installment); validating the
  payslip marks them paid, cancelling the payslip releases them.
* Postpone an installment, early settlement, remaining balance for final settlement.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'security/loan_rules.xml',
        'data/ir_sequence_data.xml',
        'views/loan_views.xml',
        'views/hr_employee_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_loan.xml',
    ],
    'installable': True,
}
