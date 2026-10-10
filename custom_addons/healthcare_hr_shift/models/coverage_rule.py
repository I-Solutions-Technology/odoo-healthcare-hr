from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.healthcare_hr_core.models.hr_employee import EMPLOYEE_CATEGORIES

from .shift_assignment import ACTIVE_STATES


class CoverageRule(models.Model):
    _name = 'healthcare.shift.coverage.rule'
    _description = 'Shift Coverage Rule'
    _order = 'branch_id, department_id, shift_template_id'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    branch_id = fields.Many2one('healthcare.hr.branch', check_company=True)
    department_id = fields.Many2one('hr.department', required=True, check_company=True)
    unit_id = fields.Many2one('healthcare.hr.unit', check_company=True, domain="[('department_id', '=', department_id)]")
    shift_template_id = fields.Many2one('healthcare.shift.template', required=True, check_company=True)
    employee_category = fields.Selection(EMPLOYEE_CATEGORIES)
    job_id = fields.Many2one('hr.job', check_company=True)
    minimum_required = fields.Integer(required=True, default=1)
    preferred_required = fields.Integer()
    weekdays = fields.Char(help="Restrict to weekdays (0=Monday ... 6=Sunday), comma separated. Empty = every day.")
    effective_from = fields.Date()
    effective_to = fields.Date()
    block_publication = fields.Boolean(
        help="When set, the roster publication wizard refuses to publish a period with a shortage on this rule.")
    active = fields.Boolean(default=True)

    @api.depends('department_id', 'unit_id', 'shift_template_id', 'employee_category', 'job_id', 'minimum_required')
    def _compute_name(self):
        categories = dict(EMPLOYEE_CATEGORIES)
        for rule in self:
            who = rule.job_id.name or categories.get(rule.employee_category) or self.env._('Staff')
            where = rule.unit_id.name or rule.department_id.name or ''
            rule.name = f'{where} / {rule.shift_template_id.name or ""} / {who} >= {rule.minimum_required}'

    @api.constrains('minimum_required', 'preferred_required', 'effective_from', 'effective_to')
    def _check_values(self):
        for rule in self:
            if rule.minimum_required < 0 or (rule.preferred_required and rule.preferred_required < rule.minimum_required):
                raise ValidationError(self.env._('The preferred staffing must be at least the minimum.'))
            if rule.effective_from and rule.effective_to and rule.effective_to < rule.effective_from:
                raise ValidationError(self.env._('The rule end date is before its start date.'))

    def _applies_on(self, day):
        self.ensure_one()
        if self.effective_from and day < self.effective_from:
            return False
        if self.effective_to and day > self.effective_to:
            return False
        if self.weekdays:
            allowed = {int(x) for x in self.weekdays.split(',') if x.strip().isdigit()}
            return day.weekday() in allowed
        return True

    def _assignment_domain(self, date_from, date_to):
        self.ensure_one()
        domain = [('shift_template_id', '=', self.shift_template_id.id), ('department_id', '=', self.department_id.id),
                  ('state', 'in', ACTIVE_STATES), ('date', '>=', date_from), ('date', '<=', date_to)]
        if self.branch_id:
            domain.append(('branch_id', '=', self.branch_id.id))
        if self.unit_id:
            domain.append(('unit_id', '=', self.unit_id.id))
        if self.employee_category:
            domain.append(('employee_category', '=', self.employee_category))
        if self.job_id:
            domain.append(('job_id', '=', self.job_id.id))
        return domain

    def _compute_coverage(self, date_from, date_to):
        """[(rule, date, assigned)] for every applicable (rule, day). One grouped query per rule."""
        Assignment = self.env['healthcare.shift.assignment'].sudo()
        result = []
        for rule in self:
            counts = dict(Assignment._read_group(rule._assignment_domain(date_from, date_to), ['date:day'], ['__count']))
            counts = {fields.Date.to_date(k): v for k, v in counts.items()}
            day = date_from
            while day <= date_to:
                if rule._applies_on(day):
                    result.append((rule, day, counts.get(day, 0)))
                day += timedelta(days=1)
        return result

    @api.model
    def _refresh_snapshots(self, date_from, date_to, rules=None):
        """Upsert coverage snapshots for the period (idempotent)."""
        rules = rules or self.search([])
        Snapshot = self.env['healthcare.shift.coverage.snapshot'].sudo()
        existing = {(s.rule_id.id, s.date): s for s in Snapshot.search([
            ('rule_id', 'in', rules.ids), ('date', '>=', date_from), ('date', '<=', date_to)])}
        to_create = []
        for rule, day, assigned in rules._compute_coverage(date_from, date_to):
            vals = {'assigned': assigned, 'minimum_required': rule.minimum_required,
                    'preferred_required': rule.preferred_required or rule.minimum_required}
            snapshot = existing.get((rule.id, day))
            if snapshot:
                if (snapshot.assigned, snapshot.minimum_required) != (assigned, rule.minimum_required):
                    snapshot.write(vals)
            else:
                to_create.append(dict(vals, rule_id=rule.id, date=day))
        Snapshot.create(to_create)
        return Snapshot.search([('rule_id', 'in', rules.ids), ('date', '>=', date_from), ('date', '<=', date_to)])

    @api.model
    def _cron_coverage(self, days=14):
        today = fields.Date.context_today(self)
        snapshots = self._refresh_snapshots(today, today + timedelta(days=days))
        Alert = self.env['healthcare.hr.alert']
        for snapshot in snapshots.filtered(lambda s: s.shortage > 0):
            manager = snapshot.department_id.manager_id.user_id or snapshot.rule_id.branch_id.manager_id.user_id
            Alert.schedule(snapshot, f'shortage_{snapshot.id}', self.env._(
                'Shift shortage: %(rule)s on %(date)s (%(assigned)s/%(min)s)', rule=snapshot.rule_id.name,
                date=snapshot.date, assigned=snapshot.assigned, min=snapshot.minimum_required),
                user=manager or None, deadline=snapshot.date)
        return True


class CoverageSnapshot(models.Model):
    """Staffing level per coverage rule and day, refreshed by cron and the publication wizard.
    Stored so coverage/shortage reports are simple pivots."""
    _name = 'healthcare.shift.coverage.snapshot'
    _description = 'Shift Coverage Snapshot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date, rule_id'

    rule_id = fields.Many2one('healthcare.shift.coverage.rule', required=True, ondelete='cascade', index=True)
    date = fields.Date(required=True, index=True)
    company_id = fields.Many2one(related='rule_id.company_id', store=True)
    branch_id = fields.Many2one(related='rule_id.branch_id', store=True)
    department_id = fields.Many2one(related='rule_id.department_id', store=True)
    unit_id = fields.Many2one(related='rule_id.unit_id', store=True)
    shift_template_id = fields.Many2one(related='rule_id.shift_template_id', store=True)
    employee_category = fields.Selection(related='rule_id.employee_category', store=True)
    minimum_required = fields.Integer(aggregator='sum')
    preferred_required = fields.Integer(aggregator='sum')
    assigned = fields.Integer(aggregator='sum')
    shortage = fields.Integer(compute='_compute_shortage', store=True, aggregator='sum')
    status = fields.Selection([('short', 'Shortage'), ('minimum', 'Minimum Met'), ('preferred', 'Preferred Met')],
                              compute='_compute_shortage', store=True)

    _rule_date_uniq = models.Constraint('unique (rule_id, date)', 'One snapshot per rule and day.')

    @api.depends('assigned', 'minimum_required', 'preferred_required')
    def _compute_shortage(self):
        for snap in self:
            snap.shortage = max(snap.minimum_required - snap.assigned, 0)
            if snap.shortage:
                snap.status = 'short'
            elif snap.assigned >= (snap.preferred_required or snap.minimum_required):
                snap.status = 'preferred'
            else:
                snap.status = 'minimum'
