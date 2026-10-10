from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _hc_credential_compliance(self, on_date=None):
        """{employee_id: % of mandatory credential types valid on ``on_date``, or None if none applies}.

        Fallback measure of training compliance when the training matrix is not installed.
        """
        on_date = on_date or fields.Date.context_today(self)
        employees = self.sudo()
        types = self.env['healthcare.hr.credential.type'].sudo().search([('mandatory', '=', True)])
        creds = self.env['healthcare.hr.credential'].sudo().search([
            ('employee_id', 'in', employees.ids), ('credential_type_id', 'in', types.ids), ('verified', '=', True),
            '|', ('expiry_date', '=', False), ('expiry_date', '>=', on_date)])
        valid = {(c.employee_id.id, c.credential_type_id.id) for c in creds if c.is_valid_on(on_date)}
        result = {}
        for employee in employees:
            required = types.filtered(lambda t: t._applies_to(employee))
            if not required:
                result[employee.id] = None
                continue
            ok = sum(1 for t in required if (employee.id, t.id) in valid)
            result[employee.id] = round(100.0 * ok / len(required), 2)
        return result
