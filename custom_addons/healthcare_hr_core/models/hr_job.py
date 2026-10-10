from odoo import fields, models

from .hr_employee import EMPLOYEE_CATEGORIES


class HrJob(models.Model):
    _inherit = 'hr.job'

    employee_category = fields.Selection(
        EMPLOYEE_CATEGORIES, string='Healthcare Category',
        help="Default healthcare category for employees holding this position. "
             "Drives credential requirements, coverage rules and allowances.")
    medical_license_required = fields.Boolean(
        help="Employees in this position must hold a valid professional/medical license.")
