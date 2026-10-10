from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EmployeePractitionerLink(models.Model):
    """Loose bridge between an HR employee and a clinical practitioner record.

    The clinical side can be any Odoo model (practitioner_model + practitioner_id) or an
    external system (external_system + external_code). HR never depends on the clinical app.
    """
    _name = 'healthcare.employee.practitioner.link'
    _description = 'Employee / Practitioner Link'
    _inherit = ['mail.thread']
    _order = 'valid_from desc'
    _check_company_auto = True

    employee_id = fields.Many2one('hr.employee', required=True, index=True, ondelete='cascade',
                                  check_company=True, tracking=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    external_system = fields.Char(help="Clinical system name, e.g. EMR, LIS, RIS, PACS, pharmacy.", tracking=True)
    external_code = fields.Char(string='Practitioner Code', index=True, tracking=True)
    practitioner_model = fields.Char(string='Practitioner Model',
                                     help="Technical name of the Odoo model holding practitioners, if any.")
    practitioner_id = fields.Many2oneReference(string='Practitioner Record', model_field='practitioner_model')
    valid_from = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    valid_to = fields.Date(tracking=True)
    active = fields.Boolean(default=True)

    @api.constrains('valid_from', 'valid_to')
    def _check_dates(self):
        for link in self:
            if link.valid_to and link.valid_to < link.valid_from:
                raise ValidationError(self.env._('The link end date cannot be before its start date.'))

    @api.constrains('external_code', 'practitioner_id')
    def _check_target(self):
        for link in self:
            if not link.external_code and not link.practitioner_id:
                raise ValidationError(self.env._('Set a practitioner code or a practitioner record.'))

    @api.model
    def _get_employee_for_practitioner(self, external_system, external_code, on_date=None):
        """Service method for clinical integrations: resolve the employee behind a practitioner code."""
        on_date = on_date or fields.Date.context_today(self)
        link = self.search([
            ('external_system', '=', external_system), ('external_code', '=', external_code),
            ('valid_from', '<=', on_date), '|', ('valid_to', '=', False), ('valid_to', '>=', on_date),
        ], limit=1)
        return link.employee_id
