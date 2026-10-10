import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

PROBATION_STATUS = [
    ('none', 'No Probation'),
    ('draft', 'Draft'),
    ('started', 'Probation Started'),
    ('review_due', 'Review Due'),
    ('reviewed', 'Reviewed'),
    ('passed', 'Passed'),
    ('extended', 'Extended'),
    ('terminate_recommended', 'Termination Recommended'),
]


class HrVersion(models.Model):
    _inherit = 'hr.version'

    probation_start_date = fields.Date(groups='hr.group_hr_user', tracking=True)
    probation_end_date = fields.Date(
        related='trial_date_end', readonly=False, groups='hr.group_hr_manager', string='Probation End Date',
        help="Same as the standard 'End of Trial Period'.")
    probation_status = fields.Selection(PROBATION_STATUS, default='none', required=True,
                                        groups='hr.group_hr_user', tracking=True, index=True)
    probation_review_ids = fields.One2many('healthcare.hr.probation.review', 'version_id',
                                           groups='hr.group_hr_user')
    renewal_type = fields.Selection([
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
        ('non_renewable', 'Non Renewable'),
    ], default='manual', groups='hr.group_hr_user', tracking=True)
    renewal_period_months = fields.Integer(default=12, groups='hr.group_hr_user',
                                           help="Duration added by an automatic or manual renewal.")
    renewal_notice_days = fields.Integer(default=30, groups='hr.group_hr_user',
                                         help="Notice to give the employee before a non renewal.")
    contract_expiry_alert_days = fields.Integer(
        groups='hr.group_hr_user',
        help="Days before the contract end date at which a renewal activity is raised. "
             "Empty = company default.")
    medical_license_required = fields.Boolean(groups='hr.group_hr_user', tracking=True)
    professional_license_required = fields.Boolean(groups='hr.group_hr_user', tracking=True)
    insurance_required = fields.Boolean(groups='hr.group_hr_user', tracking=True,
                                        help="Malpractice insurance required for this contract.")

    @api.constrains('probation_start_date', 'trial_date_end')
    def _check_probation_dates(self):
        for version in self.sudo():
            if version.probation_start_date and version.trial_date_end \
                    and version.trial_date_end < version.probation_start_date:
                raise ValidationError(self.env._('The probation end date cannot be before its start date.'))

    @api.onchange('job_id')
    def _onchange_job_id_license(self):
        if self.job_id.medical_license_required:
            self.medical_license_required = True

    # ------------------------------------------------------------------
    # Probation workflow
    # ------------------------------------------------------------------
    def action_start_probation(self):
        for version in self:
            if not version.trial_date_end:
                raise UserError(self.env._('Set the probation end date on %s first.', version.employee_id.name))
            version.write({
                'probation_status': 'started',
                'probation_start_date': version.probation_start_date or version.contract_date_start
                or fields.Date.context_today(self),
            })
            version.employee_id.employment_status = 'probation'

    def action_create_probation_review(self):
        self.ensure_one()
        review = self.env['healthcare.hr.probation.review'].create({
            'version_id': self.id,
            'employee_id': self.employee_id.id,
            'reviewer_id': self.employee_id.parent_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'healthcare.hr.probation.review',
            'res_id': review.id,
            'view_mode': 'form',
        }

    # ------------------------------------------------------------------
    # Renewal
    # ------------------------------------------------------------------
    def _renew(self, months=None, new_wage=None):
        """Renew by creating a new employee version starting the day after the current end."""
        self.ensure_one()
        if self.renewal_type == 'non_renewable':
            raise UserError(self.env._('The contract of %s is not renewable.', self.employee_id.name))
        if not self.contract_date_end:
            raise UserError(self.env._('The contract of %s has no end date.', self.employee_id.name))
        months = months or self.renewal_period_months or 12
        start = self.contract_date_end + relativedelta(days=1)
        vals = {
            'date_version': start,
            'contract_date_start': start,
            'contract_date_end': start + relativedelta(months=months, days=-1),
            'probation_status': 'none',
            'probation_start_date': False,
            'trial_date_end': False,
        }
        if new_wage:
            vals['wage'] = new_wage
        new_version = self.employee_id.create_version(vals)
        self.message_post(body=self.env._('Contract renewed until %s.', vals['contract_date_end']))
        return new_version

    # ------------------------------------------------------------------
    # Alerts (daily, idempotent)
    # ------------------------------------------------------------------
    @api.model
    def _cron_healthcare_contract_alerts(self):
        today = fields.Date.context_today(self)
        Alert = self.env['healthcare.hr.alert']
        Version = self.sudo()
        employees = self.env['hr.employee'].sudo().search([('employment_status', '!=', 'exited')])
        versions = employees.mapped('current_version_id')

        # Probation
        for version in versions.filtered(lambda v: v.probation_status in ('started', 'extended', 'review_due')
                                          and v.trial_date_end):
            days_left = (version.trial_date_end - today).days
            thresholds = version.company_id._hc_parse_days(version.company_id.hc_probation_alert_days)
            hit = [d for d in thresholds if days_left <= d]
            if not hit:
                continue
            threshold = min(hit)
            if version.probation_status in ('started', 'extended') and thresholds and days_left <= max(thresholds):
                version.probation_status = 'review_due'
            Alert.schedule(
                version.employee_id, f'probation_{version.id}_{threshold}',
                self.env._('Probation ends in %(days)s days: %(name)s',
                           days=max(days_left, 0), name=version.employee_id.name),
                note=self.env._('Probation end date: %s. Create and complete the probation review.',
                                version.trial_date_end),
                deadline=version.trial_date_end)

        # Contract expiry / automatic renewal
        for version in versions.filtered(lambda v: v.contract_date_end):
            alert_days = version.contract_expiry_alert_days or version.company_id.hc_contract_alert_days or 60
            days_left = (version.contract_date_end - today).days
            if version.renewal_type == 'automatic' and days_left < 0:
                try:
                    with self.env.cr.savepoint():
                        version._renew()
                except (UserError, ValidationError) as error:
                    _logger.warning('Automatic renewal failed for %s: %s', version.employee_id.name, error)
                continue
            if days_left <= alert_days:
                Alert.schedule(
                    version.employee_id, f'contract_{version.id}',
                    self.env._('Contract expires in %(days)s days: %(name)s',
                               days=max(days_left, 0), name=version.employee_id.name),
                    note=self.env._('Renewal policy: %s', dict(
                        Version._fields['renewal_type']._description_selection(self.env)).get(version.renewal_type)),
                    deadline=version.contract_date_end)
        return True
