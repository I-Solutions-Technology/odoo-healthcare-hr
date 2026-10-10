from odoo import api, fields, models


class HealthcareAlert(models.AbstractModel):
    """Idempotent activity scheduling shared by every healthcare cron.

    An alert is identified by (record, key). The key is written at the start of the
    activity summary; the same key is never scheduled twice on a record while an activity
    for it is still open, so daily crons never spam users.
    """
    _name = 'healthcare.hr.alert'
    _description = 'Healthcare HR Alert Service'

    @api.model
    def _responsible_for(self, employee):
        employee = employee.sudo()
        return (employee.hr_responsible_id or employee.company_id.hc_alert_user_id
                or employee.parent_id.user_id
                or self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user)

    @api.model
    def schedule(self, records, key, summary, note=None, user=None, deadline=None, employee_field='employee_id'):
        """Schedule a To-Do on each of ``records`` unless an open one with ``key`` exists.

        :param records: any recordset inheriting mail.activity.mixin
        :param key: stable technical key, e.g. 'probation_14'
        :return: created mail.activity records
        """
        Activity = self.env['mail.activity'].sudo()
        if not records:
            return Activity
        prefix = f'[{key}] '
        existing = Activity.search([
            ('res_model', '=', records._name), ('res_id', 'in', records.ids),
            ('summary', '=like', prefix.replace('[', '\\[').replace('_', '\\_') + '%'),
        ])
        already = set(existing.mapped('res_id'))
        todo = self.env.ref('mail.mail_activity_data_todo')
        created = Activity
        for record in records:
            if record.id in already:
                continue
            if user:
                responsible = user
            elif records._name == 'hr.employee':
                responsible = self._responsible_for(record)
            elif employee_field in record._fields:
                responsible = self._responsible_for(record[employee_field])
            else:
                responsible = self.env.user
            created |= record.sudo().activity_schedule(
                activity_type_id=todo.id,
                summary=prefix + summary,
                note=note or '',
                user_id=responsible.id,
                date_deadline=deadline or fields.Date.context_today(self),
            )
        return created
