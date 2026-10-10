from datetime import datetime, time

from odoo import api, fields, models
from odoo.exceptions import UserError

EXIT_REASONS = [
    ('resignation', 'Resignation'),
    ('termination', 'Termination'),
    ('retirement', 'Retirement'),
    ('contract_end', 'Contract End'),
    ('medical', 'Medical'),
    ('other', 'Other'),
]


class EmployeeExit(models.Model):
    _name = 'healthcare.hr.exit'
    _description = 'Employee Exit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(default=lambda self: self.env._('New'), readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    job_id = fields.Many2one(related='employee_id.job_id', store=True)
    exit_reason = fields.Selection(EXIT_REASONS, required=True, tracking=True)
    departure_reason_id = fields.Many2one('hr.departure.reason', string='Departure Reason (standard)')
    request_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    last_working_date = fields.Date(required=True, tracking=True)
    notice_days = fields.Integer(compute='_compute_notice_days', store=True)
    description = fields.Html()
    clearance_item_ids = fields.One2many('healthcare.hr.clearance.item', 'exit_id', string='Clearance')
    clearance_progress = fields.Float(compute='_compute_clearance_progress', store=True)
    settlement_ids = fields.One2many('healthcare.hr.final.settlement', 'exit_id', string='Settlements')
    settlement_id = fields.Many2one('healthcare.hr.final.settlement', string='Final Settlement', compute='_compute_settlement_id')
    state = fields.Selection([
        ('initiated', 'Exit Initiated'),
        ('clearance', 'Clearance Started'),
        ('settlement', 'Final Settlement'),
        ('hr_approval', 'HR Approval'),
        ('done', 'Employee Archived'),
        ('cancelled', 'Cancelled'),
    ], default='initiated', required=True, tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New')) == self.env._('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('healthcare.hr.exit') or '/'
        return super().create(vals_list)

    @api.depends('request_date', 'last_working_date')
    def _compute_notice_days(self):
        for rec in self:
            rec.notice_days = (rec.last_working_date - rec.request_date).days \
                if rec.request_date and rec.last_working_date else 0

    @api.depends('clearance_item_ids.state')
    def _compute_clearance_progress(self):
        for rec in self:
            items = rec.clearance_item_ids
            rec.clearance_progress = 100.0 * len(items.filtered(lambda i: i.state == 'cleared')) / len(items) if items else 0.0

    @api.depends('settlement_ids.state')
    def _compute_settlement_id(self):
        for rec in self:
            rec.settlement_id = rec.settlement_ids.filtered(lambda s: s.state != 'cancelled')[:1]

    # ------------------------------------------------------------------
    def action_start_clearance(self):
        Item = self.env['healthcare.hr.clearance.item']
        for rec in self.filtered(lambda r: r.state == 'initiated'):
            departments = self.env['healthcare.hr.clearance.department'].search(
                ['|', ('company_id', '=', False), ('company_id', '=', rec.company_id.id)])
            existing = rec.clearance_item_ids.clearance_department_id
            vals = []
            for dept in departments - existing:
                responsible = dept.responsible_user_id
                if not responsible and dept.code == 'DEPT':
                    responsible = rec.department_id.manager_id.user_id or rec.employee_id.parent_id.user_id
                vals.append({'exit_id': rec.id, 'clearance_department_id': dept.id, 'mandatory': dept.mandatory,
                             'responsible_user_id': (responsible or rec.company_id.hc_alert_user_id or self.env.user).id})
            items = Item.create(vals)
            for item in items:
                item.activity_schedule('mail.mail_activity_data_todo', user_id=item.responsible_user_id.id,
                                       date_deadline=rec.last_working_date,
                                       summary=self.env._('Clearance of %s', rec.employee_id.name))
            rec.state = 'clearance'
            rec.employee_id.sudo().employment_status = 'notice'

    def _check_clearance_complete(self):
        for rec in self.filtered(lambda r: r.state == 'clearance'):
            mandatory = rec.clearance_item_ids.filtered('mandatory')
            if mandatory and all(i.state == 'cleared' for i in mandatory):
                rec.state = 'settlement'
                if not rec.settlement_id:
                    self.env['healthcare.hr.final.settlement'].create({'exit_id': rec.id})
                self.env['healthcare.hr.alert'].schedule(
                    rec, 'final_settlement', self.env._('Final settlement pending: %s', rec.employee_id.name),
                    user=rec.company_id.hc_alert_user_id or None)

    def action_create_settlement(self):
        self.ensure_one()
        if self.state not in ('settlement', 'hr_approval'):
            raise UserError(self.env._('Complete the clearance first.'))
        settlement = self.settlement_id or self.env['healthcare.hr.final.settlement'].create({'exit_id': self.id})
        return {'type': 'ir.actions.act_window', 'res_model': settlement._name, 'res_id': settlement.id,
                'view_mode': 'form'}

    def action_hr_approve(self):
        """Archive the employee. Loans and pending payroll inputs are closed by the settlement."""
        for rec in self:
            if rec.state != 'hr_approval':
                raise UserError(self.env._('The final settlement of %s must be confirmed first.', rec.employee_id.name))
            employee = rec.employee_id.sudo()
            version = employee._get_version(rec.last_working_date)
            if version and (not version.contract_date_end or version.contract_date_end > rec.last_working_date):
                version.contract_date_end = rec.last_working_date
            # future shifts are cancelled (never deleted) so the roster shows the gap
            limit = fields.Datetime.to_datetime(datetime.combine(rec.last_working_date, time.max))
            shifts = self.env['healthcare.shift.assignment'].sudo().search([
                ('employee_id', '=', employee.id), ('datetime_start', '>', limit),
                ('state', 'in', ('draft', 'published', 'confirmed', 'conflict'))])
            shifts.action_cancel()
            employee.write({
                'employment_status': 'exited',
                'departure_date': rec.last_working_date,
                'departure_reason_id': rec.departure_reason_id.id or False,
            })
            employee.with_context(no_wizard=True).action_archive()
            rec.state = 'done'
            rec.message_post(body=self.env._('Employee archived; %s future shift(s) cancelled.', len(shifts)))

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(self.env._('The employee is already archived.'))
            rec.settlement_ids.filtered(lambda s: s.state != 'paid').write({'state': 'cancelled'})
            rec.state = 'cancelled'
            if rec.employee_id.employment_status == 'notice':
                rec.employee_id.sudo().employment_status = 'active'


class ClearanceItem(models.Model):
    _name = 'healthcare.hr.clearance.item'
    _description = 'Clearance Item'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'exit_id, sequence, id'

    exit_id = fields.Many2one('healthcare.hr.exit', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='exit_id.employee_id', store=True)
    company_id = fields.Many2one(related='exit_id.company_id', store=True)
    clearance_department_id = fields.Many2one('healthcare.hr.clearance.department', required=True)
    sequence = fields.Integer(related='clearance_department_id.sequence', store=True)
    checklist = fields.Text(related='clearance_department_id.checklist')
    mandatory = fields.Boolean(default=True)
    responsible_user_id = fields.Many2one('res.users', string='Clearance Responsible', tracking=True)
    state = fields.Selection([('pending', 'Pending'), ('cleared', 'Cleared'), ('blocked', 'Blocked')],
                             default='pending', required=True, tracking=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    amount_due = fields.Monetary(string='Obligation Amount', tracking=True,
                                 help="Amount owed by the employee (e.g. unreturned equipment). Deducted in the final settlement.")
    note = fields.Text()
    cleared_by = fields.Many2one('res.users', readonly=True)
    cleared_date = fields.Date(readonly=True)

    def _check_responsible(self):
        user = self.env.user
        if user.has_group('healthcare_hr_core.group_hc_officer'):
            return
        for item in self:
            if item.responsible_user_id != user:
                raise UserError(self.env._('Only %s can clear this item.', item.responsible_user_id.name))

    def action_clear(self):
        self._check_responsible()
        self.write({'state': 'cleared', 'cleared_by': self.env.uid, 'cleared_date': fields.Date.context_today(self)})
        self.activity_feedback(['mail.mail_activity_data_todo'])
        self.exit_id._check_clearance_complete()

    def action_block(self):
        self._check_responsible()
        for item in self:
            if not item.note:
                raise UserError(self.env._('Explain what blocks the clearance in the note.'))
        self.write({'state': 'blocked'})

    def action_reset(self):
        self.filtered(lambda i: i.exit_id.state == 'clearance').write(
            {'state': 'pending', 'cleared_by': False, 'cleared_date': False})
