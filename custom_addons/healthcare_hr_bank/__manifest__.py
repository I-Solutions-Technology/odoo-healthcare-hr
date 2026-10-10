{
    'name': 'Healthcare HR Payroll Bank Export',
    'summary': 'Salary transfer batches from validated payslips with configurable bank layouts '
               '(CSV, fixed-width TXT, XLSX) and an API-ready sending interface',
    'description': """
Payroll Bank Export
===================
* Bank batches built from validated payslips (period, pay run, branch).
* One line per employee: bank, IBAN / account number, net salary, reference. Missing or
  untrusted bank accounts are flagged instead of exported silently.
* Configurable layouts: columns, order, header, delimiter, fixed widths, padding,
  decimals, date format, encoding; CSV, TXT and XLSX outputs.
* API-ready: `_send_to_bank()` dispatches to `_send_<provider>()`, to implement per bank.
* Bank data is restricted to payroll officers.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'security/bank_rules.xml',
        'data/bank_layout_data.xml',
        'views/bank_layout_views.xml',
        'views/bank_batch_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
