import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

CREDENTIAL_STATUS = [
    ('valid', 'Valid'),
    ('expiring', 'Expiring'),
    ('expired', 'Expired'),
    ('missing', 'Missing'),
    ('under_verification', 'Under Verification'),
]


class Credential(models.Model):
    _name = 'healthcare.hr.credential'
    _description = 'Employee Credential'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True, string='Branch')
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    employee_category = fields.Selection(related='employee_id.employee_category', store=True)
    credential_type_id = fields.Many2one('healthcare.hr.credential.type', required=True, index=True, tracking=True)
    credential_category = fields.Selection(related='credential_type_id.credential_category', store=True)
    confidential = fields.Boolean(related='credential_type_id.confidential', store=True)
    credential_number = fields.Char(tracking=True)
    issuing_authority = fields.Char(tracking=True)
    issue_date = fields.Date(tracking=True)
    expiry_date = fields.Date(tracking=True, index=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    status = fields.Selection(CREDENTIAL_STATUS, compute='_compute_status', store=True, index=True, tracking=True)
    days_to_expiry = fields.Integer(compute='_compute_days_to_expiry')
    verified = fields.Boolean(tracking=True, copy=False)
    verified_by = fields.Many2one('res.users', readonly=True, copy=False, tracking=True)
    verification_date = fields.Date(readonly=True, copy=False)
    notes = fields.Text()
    active = fields.Boolean(default=True)

    @api.depends('employee_id', 'credential_type_id')
    def _compute_name(self):
        for cred in self:
            cred.name = f'{cred.credential_type_id.name or ""} - {cred.employee_id.name or ""}'

    @api.depends('credential_number', 'attachment_ids', 'verified', 'expiry_date',
                 'credential_type_id.default_alert_days', 'credential_type_id.has_expiry')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for cred in self:
            cred.status = cred._get_status(today)

    def _get_status(self, on_date):
        self.ensure_one()
        if not self.credential_number and not self.attachment_ids and not self.verified:
            return 'missing'
        if self.expiry_date and self.expiry_date < on_date:
            return 'expired'
        if not self.verified:
            return 'under_verification'
        if self.expiry_date and self.expiry_date <= on_date + relativedelta(days=self._first_alert_days()):
            return 'expiring'
        return 'valid'

    def _alert_thresholds(self):
        self.ensure_one()
        if self.credential_type_id.default_alert_days:
            company_days = self.company_id._hc_parse_days(self.company_id.hc_credential_alert_days)
            return sorted({self.credential_type_id.default_alert_days}
                          | {d for d in company_days if d < self.credential_type_id.default_alert_days}, reverse=True)
        return self.company_id._hc_parse_days(self.company_id.hc_credential_alert_days) or [30]

    def _first_alert_days(self):
        return max(self._alert_thresholds())

    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for cred in self:
            cred.days_to_expiry = (cred.expiry_date - today).days if cred.expiry_date else 0

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for cred in self:
            if cred.issue_date and cred.expiry_date and cred.expiry_date < cred.issue_date:
                raise ValidationError(self.env._('The expiry date cannot be before the issue date.'))

    def is_valid_on(self, on_date):
        """Valid for operational use (shift assignment) on ``on_date``."""
        self.ensure_one()
        return bool(self.verified and (self.credential_number or self.attachment_ids)
                    and (not self.expiry_date or self.expiry_date >= on_date))

    # ------------------------------------------------------------------
    # Verification workflow
    # ------------------------------------------------------------------
    def action_verify(self):
        for cred in self:
            if not cred.credential_number and not cred.attachment_ids:
                raise UserError(self.env._('Add the credential number or a scanned document before verifying.'))
        self.write({'verified': True, 'verified_by': self.env.uid,
                    'verification_date': fields.Date.context_today(self)})

    def action_reset_verification(self):
        self.write({'verified': False, 'verified_by': False, 'verification_date': False})

    def write(self, vals):
        # A new number or expiry date must be verified again.
        if 'verified' not in vals and ({'credential_number', 'expiry_date'} & set(vals)):
            new_number = vals.get('credential_number')
            new_expiry = fields.Date.to_date(vals['expiry_date']) if 'expiry_date' in vals else None
            changed = self.filtered(lambda c: c.verified and (
                ('credential_number' in vals and new_number != c.credential_number)
                or ('expiry_date' in vals and new_expiry != c.expiry_date)))
            if changed:
                super(Credential, changed).write({'verified': False, 'verified_by': False,
                                                  'verification_date': False})
        return super().write(vals)

    # ------------------------------------------------------------------
    # Crons (idempotent)
    # ------------------------------------------------------------------
    @api.model
    def _cron_update_status(self):
        """Dates move, stored statuses do not: refresh every non-final credential."""
        creds = self.sudo().search([('status', 'in', ('valid', 'expiring', 'under_verification')),
                                    ('expiry_date', '!=', False)])
        creds._compute_status()
        return True

    @api.model
    def _cron_credential_alerts(self):
        today = fields.Date.context_today(self)
        Alert = self.env['healthcare.hr.alert']
        self._cron_update_status()
        creds = self.sudo().search([('expiry_date', '!=', False), ('status', 'in', ('expiring', 'expired')),
                                    ('employee_id.active', '=', True)])
        for cred in creds:
            days_left = (cred.expiry_date - today).days
            if days_left < 0:
                key, summary = f'credential_{cred.id}_expired', self.env._(
                    '%(type)s EXPIRED: %(name)s', type=cred.credential_type_id.name, name=cred.employee_id.name)
            else:
                hit = [d for d in cred._alert_thresholds() if days_left <= d]
                if not hit:
                    continue
                key, summary = f'credential_{cred.id}_{min(hit)}', self.env._(
                    '%(type)s expires in %(days)s days: %(name)s',
                    type=cred.credential_type_id.name, days=days_left, name=cred.employee_id.name)
            Alert.schedule(cred, key, summary, deadline=cred.expiry_date)
        missing = self.sudo().search([('status', '=', 'missing'), ('credential_type_id.mandatory', '=', True),
                                      ('employee_id.active', '=', True)])
        for cred in missing:
            Alert.schedule(cred, f'credential_{cred.id}_missing', self.env._(
                'Missing mandatory %(type)s: %(name)s', type=cred.credential_type_id.name, name=cred.employee_id.name))
        return True

    @api.model
    def _generate_missing_credentials(self, employees=None):
        """Create 'missing' placeholders for mandatory credential types without any record."""
        employees = employees or self.env['hr.employee'].search([])
        types = self.env['healthcare.hr.credential.type'].search([('mandatory', '=', True)])
        existing = {(e.id, t.id) for e, t in self.with_context(active_test=False)._read_group(
            [('employee_id', 'in', employees.ids)], ['employee_id', 'credential_type_id'])}
        vals = [{'employee_id': emp.id, 'credential_type_id': ctype.id}
                for emp in employees for ctype in types
                if (emp.id, ctype.id) not in existing and ctype._applies_to(emp)]
        return self.create(vals)
