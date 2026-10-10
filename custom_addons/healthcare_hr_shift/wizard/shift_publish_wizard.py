from odoo import fields, models
from odoo.exceptions import UserError


class ShiftPublishWizard(models.TransientModel):
    _name = 'healthcare.shift.publish.wizard'
    _description = 'Publish Roster'

    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=lambda self: fields.Date.add(fields.Date.context_today(self), days=6))
    branch_id = fields.Many2one('healthcare.hr.branch')
    department_id = fields.Many2one('hr.department')
    draft_count = fields.Integer(compute='_compute_summary')
    shortage_summary = fields.Text(compute='_compute_summary')
    blocking = fields.Boolean(compute='_compute_summary')

    def _domain(self):
        domain = [('date', '>=', self.date_from), ('date', '<=', self.date_to), ('state', 'in', ('draft', 'conflict'))]
        if self.branch_id:
            domain.append(('branch_id', 'child_of', self.branch_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        return domain

    def _rules(self):
        domain = []
        if self.branch_id:
            domain.append(('branch_id', 'child_of', self.branch_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        return self.env['healthcare.shift.coverage.rule'].search(domain)

    def _compute_summary(self):
        for wiz in self:
            wiz.draft_count = self.env['healthcare.shift.assignment'].search_count(wiz._domain())
            lines, blocking = [], False
            if wiz.date_from and wiz.date_to:
                # coverage as if the drafts in scope were published
                drafts = self.env['healthcare.shift.assignment'].search(wiz._domain())
                for rule, day, assigned in wiz._rules()._compute_coverage(wiz.date_from, wiz.date_to):
                    planned = assigned + len(drafts.filtered_domain(
                        [('date', '=', day)] + [d for d in rule._assignment_domain(day, day) if d[0] != 'state']))
                    if planned < rule.minimum_required:
                        blocking = blocking or rule.block_publication
                        lines.append(self.env._('%(date)s  %(rule)s: %(n)s/%(min)s%(block)s', date=day, rule=rule.name,
                                                n=planned, min=rule.minimum_required,
                                                block=self.env._(' (blocking)') if rule.block_publication else ''))
            wiz.shortage_summary = '\n'.join(lines) or False
            wiz.blocking = blocking

    def action_publish(self):
        self.ensure_one()
        if self.blocking:
            raise UserError(self.env._('Publication blocked by coverage rules:\n%s', self.shortage_summary))
        assignments = self.env['healthcare.shift.assignment'].search(self._domain())
        if not assignments:
            raise UserError(self.env._('There is no draft shift to publish in this scope.'))
        result = assignments.action_publish()
        self.env['healthcare.shift.coverage.rule']._refresh_snapshots(self.date_from, self.date_to, self._rules())
        return result if isinstance(result, dict) else {'type': 'ir.actions.act_window_close'}
