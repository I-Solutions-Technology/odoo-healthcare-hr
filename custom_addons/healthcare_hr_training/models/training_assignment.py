import datetime
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ASSIGNMENT_STATES = [
    ('assigned', 'Assigned'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('expired', 'Expired'),
    ('waived', 'Waived'),
]
OPEN_STATES = ('assigned', 'in_progress')


class TrainingAssignment(models.Model):
    _name = 'healthcare.training.assignment'
    _description = 'Training Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date asc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    requirement_id = fields.Many2one('healthcare.training.requirement', required=True, index=True,
                                     check_company=True, ondelete='restrict', tracking=True)
    credential_type_id = fields.Many2one(related='requirement_id.credential_type_id', store=True, index=True,
                                         string='Certification')
    mandatory = fields.Boolean(related='requirement_id.mandatory', store=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True, string='Branch', index=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True, index=True)
    employee_category = fields.Selection(related='employee_id.employee_category', store=True)
    state = fields.Selection(ASSIGNMENT_STATES, default='assigned', required=True, index=True, tracking=True,
                             copy=False)
    assigned_date = fields.Date(default=fields.Date.context_today, required=True)
    due_date = fields.Date(tracking=True, index=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue')
    completion_date = fields.Date(tracking=True, copy=False)
    expiry_date = fields.Date(compute='_compute_expiry_date', store=True, index=True, copy=False,
                              help="Completion date + renewal period of the requirement.")
    provider = fields.Char(string='Training Provider', tracking=True)
    certificate_number = fields.Char(tracking=True, copy=False)
    score = fields.Float(aggregator='avg', copy=False)
    attachment_ids = fields.Many2many('ir.attachment', 'healthcare_training_assignment_attachment_rel',
                                      'assignment_id', 'attachment_id', string='Certificate', copy=False)
    credential_id = fields.Many2one('healthcare.hr.credential', string='Credential', readonly=True, copy=False,
                                    index='btree_not_null',
                                    help="Credential created or renewed when the training was completed.")
    credential_status = fields.Selection(related='credential_id.status', string='Credential Status')
    waiver_reason = fields.Char(tracking=True, copy=False)
    compliant = fields.Boolean(compute='_compute_compliant', store=True, index=True,
                               help="Completed and not expired, or waived.")
    compliance_rate = fields.Float(
        string='Compliance %', compute='_compute_compliant', store=True, aggregator='avg',
        help="100 when compliant, 0 otherwise: the average over a group is the compliance rate.")
    note = fields.Text()

    _unique_open_assignment = models.UniqueIndex(
        "(employee_id, requirement_id) WHERE state IN ('assigned', 'in_progress')",
        "This employee already has an open assignment for this training requirement.",
    )

    @api.depends('employee_id', 'requirement_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f'{rec.requirement_id.name or ""} - {rec.employee_id.name or ""}'

    @api.depends('completion_date', 'requirement_id.renewal_period_months')
    def _compute_expiry_date(self):
        for rec in self:
            rec.expiry_date = rec.requirement_id._expiry_from(rec.completion_date) if rec.requirement_id else False

    @api.depends('state', 'expiry_date')
    def _compute_compliant(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.compliant = rec.state == 'waived' or (
                rec.state == 'completed' and (not rec.expiry_date or rec.expiry_date >= today))
            rec.compliance_rate = 100.0 if rec.compliant else 0.0

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(rec.state in OPEN_STATES and rec.due_date and rec.due_date < today)

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if not vals.get('due_date') and vals.get('requirement_id'):
                req = self.env['healthcare.training.requirement'].browse(vals['requirement_id'])
                assigned = fields.Date.to_date(vals.get('assigned_date')) or today
                vals['due_date'] = assigned + relativedelta(days=req.due_days)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_start(self):
        self.filtered(lambda r: r.state == 'assigned').write({'state': 'in_progress'})

    def action_complete(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state not in OPEN_STATES:
                raise UserError(self.env._('Only assigned or in-progress trainings can be completed (%s).', rec.name))
            if not rec.certificate_number and not rec.attachment_ids:
                raise UserError(self.env._('Enter the certificate number or attach the certificate of %s.', rec.name))
            completion = rec.completion_date or today
            if completion > today:
                raise UserError(self.env._('The completion date of %s cannot be in the future.', rec.name))
            rec.write({'completion_date': completion, 'state': 'completed'})
            rec._hc_renew_credential()
        return True

    def action_waive(self):
        for rec in self:
            if rec.state not in OPEN_STATES:
                raise UserError(self.env._('Only open trainings can be waived.'))
            if not rec.waiver_reason:
                raise UserError(self.env._('Enter a waiver reason for %s.', rec.name))
        self.write({'state': 'waived'})

    def action_reset(self):
        """Cancel a waiver: the training is due again."""
        self.filtered(lambda r: r.state == 'waived').write({'state': 'assigned', 'waiver_reason': False})

    def _hc_renew_credential(self):
        """Create or renew the employee credential of the requirement's type.

        The credential is written with sudo: completing a training is a controlled business
        operation of training officers, who do not manage credential records themselves.
        A renewed number or expiry date always needs a new verification, unless the requirement
        trusts the training (auto verification).
        """
        Credential = self.env['healthcare.hr.credential'].sudo()
        for rec in self:
            cred = rec.credential_id.sudo() or Credential.with_context(active_test=False).search([
                ('employee_id', '=', rec.employee_id.id), ('credential_type_id', '=', rec.credential_type_id.id),
            ], order='active desc, id desc', limit=1)
            vals = {
                'credential_number': rec.certificate_number or cred.credential_number or False,
                'issuing_authority': rec.provider or cred.issuing_authority or False,
                'issue_date': rec.completion_date,
                'expiry_date': rec.expiry_date,
                'active': True,
            }
            if rec.attachment_ids:
                vals['attachment_ids'] = [fields.Command.link(att.id) for att in rec.attachment_ids]
            if cred:
                cred.write(vals)
            else:
                cred = Credential.create(dict(vals, employee_id=rec.employee_id.id,
                                              credential_type_id=rec.credential_type_id.id))
            if rec.requirement_id.auto_verify_credential:
                if not cred.verified:
                    cred.action_verify()
            elif cred.verified:
                cred.action_reset_verification()
            cred.message_post(body=self.env._('Renewed by the completed training %s.', rec.name))
            rec.credential_id = cred

    # ------------------------------------------------------------------
    # Generation from the matrix (idempotent)
    # ------------------------------------------------------------------
    @api.model
    def _hc_coverage(self, employees, credential_types):
        """{(employee_id, credential_type_id): covered-until date} from verified, non expired
        credentials and completed, non expired trainings. ``date.max`` = no expiry."""
        today = fields.Date.context_today(self)
        cover = {}

        def _merge(rows):
            for employee, ctype, expiry_max, count_expiry, count_all in rows:
                until = datetime.date.max if count_all > count_expiry else expiry_max
                key = (employee.id, ctype.id)
                if until and (key not in cover or until > cover[key]):
                    cover[key] = until

        if not employees or not credential_types:
            return cover
        _merge(self.env['healthcare.hr.credential'].sudo()._read_group(
            [('employee_id', 'in', employees.ids), ('credential_type_id', 'in', credential_types.ids),
             ('verified', '=', True), '|', ('expiry_date', '=', False), ('expiry_date', '>=', today)],
            ['employee_id', 'credential_type_id'], ['expiry_date:max', 'expiry_date:count', '__count']))
        _merge(self.sudo()._read_group(
            [('employee_id', 'in', employees.ids), ('credential_type_id', 'in', credential_types.ids),
             ('state', '=', 'completed'), '|', ('expiry_date', '=', False), ('expiry_date', '>=', today)],
            ['employee_id', 'credential_type_id'], ['expiry_date:max', 'expiry_date:count', '__count']))
        return cover

    @api.model
    def _generate_assignments(self, employees=None):
        """Create the missing assignments of the matrix. Idempotent.

        Skipped: requirements with an open or waived assignment, and employees already compliant,
        i.e. covered by a verified credential (or a completed training) that does not expire within
        the company training alert window.
        """
        today = fields.Date.context_today(self)
        Requirement = self.env['healthcare.training.requirement'].sudo()
        if employees is None:
            employees = self.env['hr.employee'].sudo().search([])
        employees = employees.sudo().filtered('active')
        requirements = Requirement.search([('company_id', 'in', employees.company_id.ids)])
        if not employees or not requirements:
            return self
        busy = {(employee.id, requirement.id) for employee, requirement in self.sudo()._read_group(
            [('employee_id', 'in', employees.ids), ('requirement_id', 'in', requirements.ids),
             ('state', 'in', OPEN_STATES + ('waived',))], ['employee_id', 'requirement_id'])}
        cover = self._hc_coverage(employees, requirements.credential_type_id)
        vals_list = []
        for employee in employees:
            window_end = today + relativedelta(days=employee.company_id.hc_training_alert_days or 0)
            for req in requirements:
                if (employee.id, req.id) in busy or not req._applies_to(employee):
                    continue
                until = cover.get((employee.id, req.credential_type_id.id))
                if until and until > window_end:
                    continue
                due = today + relativedelta(days=req.due_days)
                if until:
                    due = min(due, until)
                vals_list.append({'employee_id': employee.id, 'requirement_id': req.id, 'due_date': due})
        created = self.sudo().create(vals_list)
        if created:
            _logger.info('Healthcare training: %s assignment(s) generated', len(created))
        return created

    # ------------------------------------------------------------------
    # Crons (idempotent)
    # ------------------------------------------------------------------
    @api.model
    def _cron_mark_expired(self):
        today = fields.Date.context_today(self)
        expired = self.sudo().search([('state', '=', 'completed'), ('expiry_date', '<', today)])
        expired.write({'state': 'expired'})
        # the stored compliance flag depends on today's date
        self.sudo().search([('state', '=', 'completed'), ('compliant', '=', False)])._compute_compliant()
        return expired

    @api.model
    def _cron_training_alerts(self):
        today = fields.Date.context_today(self)
        Alert = self.env['healthcare.hr.alert']
        completed = self.sudo().search([('state', '=', 'completed'), ('expiry_date', '>=', today),
                                        ('employee_id.active', '=', True)])
        for rec in completed:
            if rec.expiry_date > today + relativedelta(days=rec.company_id.hc_training_alert_days or 0):
                continue
            Alert.schedule(rec, f'training_{rec.id}_expiring', self.env._(
                '%(training)s expires on %(date)s: %(name)s',
                training=rec.requirement_id.name, date=rec.expiry_date, name=rec.employee_id.name),
                deadline=rec.expiry_date)
        missing = self.sudo().search([('state', 'in', OPEN_STATES), ('mandatory', '=', True),
                                      ('employee_id.active', '=', True)])
        for rec in missing:
            Alert.schedule(rec, f'training_{rec.id}_missing', self.env._(
                'Missing mandatory training %(training)s: %(name)s',
                training=rec.requirement_id.name, name=rec.employee_id.name),
                deadline=rec.due_date or today)
        return True

    @api.model
    def _cron_training(self):
        self._cron_mark_expired()
        self._generate_assignments()
        self._cron_training_alerts()
        return True
