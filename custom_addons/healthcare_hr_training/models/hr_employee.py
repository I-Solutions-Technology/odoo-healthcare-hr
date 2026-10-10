from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    training_assignment_ids = fields.One2many('healthcare.training.assignment', 'employee_id',
                                              string='Training Assignments', groups='hr.group_hr_user')
    training_open_count = fields.Integer(compute='_compute_training_open_count', groups='hr.group_hr_user')

    def _compute_training_open_count(self):
        counts = dict(self.env['healthcare.training.assignment']._read_group(
            [('employee_id', 'in', self.ids), ('state', 'in', ('assigned', 'in_progress'))],
            ['employee_id'], ['__count']))
        for employee in self:
            employee.training_open_count = counts.get(employee, 0)

    def _hc_training_matrix_compliance(self, on_date=None):
        """{employee_id: compliance % of the mandatory matrix requirements, or None when none applies}.

        Used by other modules (e.g. appraisal KPIs) without a hard dependency. Read with sudo:
        only a rate is returned.
        """
        on_date = on_date or fields.Date.context_today(self)
        Assignment = self.env['healthcare.training.assignment'].sudo()
        employees = self.sudo()
        requirements = self.env['healthcare.training.requirement'].sudo().search(
            [('mandatory', '=', True), ('company_id', 'in', employees.company_id.ids)])
        credential_types = requirements.credential_type_id
        valid = {(e.id, t.id) for e, t in self.env['healthcare.hr.credential'].sudo()._read_group(
            [('employee_id', 'in', employees.ids), ('credential_type_id', 'in', credential_types.ids),
             ('verified', '=', True), '|', ('expiry_date', '=', False), ('expiry_date', '>=', on_date)],
            ['employee_id', 'credential_type_id'])}
        waived = {(e.id, r.id) for e, r in Assignment._read_group(
            [('employee_id', 'in', employees.ids), ('state', '=', 'waived')], ['employee_id', 'requirement_id'])}
        result = {}
        for employee in employees:
            applicable = requirements.filtered(lambda r: r._applies_to(employee))
            if not applicable:
                result[employee.id] = None
                continue
            ok = sum(1 for r in applicable
                     if (employee.id, r.credential_type_id.id) in valid or (employee.id, r.id) in waived)
            result[employee.id] = 100.0 * ok / len(applicable)
        return result

    def action_view_training(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Training'),
            'res_model': 'healthcare.training.assignment',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
