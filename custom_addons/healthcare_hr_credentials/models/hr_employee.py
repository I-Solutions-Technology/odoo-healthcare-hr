from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    credential_ids = fields.One2many('healthcare.hr.credential', 'employee_id', string='Credentials',
                                     groups='hr.group_hr_user')
    credential_count = fields.Integer(compute='_compute_credential_stats', groups='hr.group_hr_user')
    credential_issue_count = fields.Integer(
        compute='_compute_credential_stats', groups='hr.group_hr_user',
        help="Expired, missing or unverified credentials.")

    def _compute_credential_stats(self):
        data = self.env['healthcare.hr.credential']._read_group(
            [('employee_id', 'in', self.ids)], ['employee_id', 'status'], ['__count'])
        totals, issues = {}, {}
        for employee, status, count in data:
            totals[employee.id] = totals.get(employee.id, 0) + count
            if status in ('expired', 'missing', 'under_verification'):
                issues[employee.id] = issues.get(employee.id, 0) + count
        for employee in self:
            employee.credential_count = totals.get(employee.id, 0)
            employee.credential_issue_count = issues.get(employee.id, 0)

    def _hc_credential_blockers(self, on_date):
        """Credential types that block shift assignment and are not valid for ``on_date``.

        Returns {employee_id: [type names]}. Read with sudo: the check is needed by schedulers
        who must not see the credential details themselves.
        """
        types = self.env['healthcare.hr.credential.type'].sudo().search([
            ('mandatory', '=', True), ('blocks_shift_assignment', '=', True)])
        if not types:
            return {}
        creds = self.env['healthcare.hr.credential'].sudo().search([
            ('employee_id', 'in', self.ids), ('credential_type_id', 'in', types.ids)])
        by_key = {}
        for cred in creds:
            by_key.setdefault((cred.employee_id.id, cred.credential_type_id.id), []).append(cred)
        result = {}
        for employee in self.sudo():
            for ctype in types:
                if not ctype._applies_to(employee):
                    continue
                valid = any(c.is_valid_on(on_date) for c in by_key.get((employee.id, ctype.id), []))
                if not valid:
                    result.setdefault(employee.id, []).append(ctype.name)
        return result

    def action_view_credentials(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Credentials'),
            'res_model': 'healthcare.hr.credential',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
