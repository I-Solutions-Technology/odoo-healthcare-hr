{
    'name': 'Healthcare HR Appraisal',
    'summary': 'Healthcare KPI templates (doctors, nurses, administrative) on the standard Appraisal, '
               'with attendance, punctuality and training compliance KPIs computed automatically',
    'description': """
Healthcare HR Appraisal
=======================
Extends the standard Odoo Appraisal application (hr_appraisal) instead of replacing it.

* KPI templates per healthcare category and/or job position, each KPI with a weight, a target and a
  measurement: manual, attendance rate, late rate or training compliance.
* KPI lines are loaded on the appraisal from the matching template (on creation or with "Load KPIs").
* Automatic attendance rate = attended / planned non-leave shifts (completed or approved shift
  assignments of the appraisal period).
* Automatic late rate = late shifts / attended shifts.
* Automatic training compliance = valid mandatory certifications / required ones (training matrix when
  the Healthcare Training module is installed, mandatory credential types otherwise).
* Score 0-100 per KPI, weighted score and weighted total on the appraisal.

Governance rule: appraisal scores are decision support only. This module NEVER terminates, renews,
extends or otherwise changes a contract, a probation or an employment status automatically from a score;
such decisions are always taken explicitly by HR in the contract and probation workflows.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_attendance', 'hr_appraisal'],
    'data': [
        'security/ir.model.access.csv',
        'security/appraisal_rules.xml',
        'data/kpi_template_data.xml',
        'views/kpi_template_views.xml',
        'views/hr_appraisal_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'data/demo_appraisal.xml',
    ],
    'installable': True,
}
