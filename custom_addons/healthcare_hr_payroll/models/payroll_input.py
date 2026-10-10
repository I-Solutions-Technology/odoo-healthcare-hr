import logging
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

from .hr_payslip_input_type import SOURCE_TYPES

_logger = logging.getLogger(__name__)


class PayrollInput(models.Model):
    """One payable (or deductible) item waiting for payroll.

    ``processing_key`` identifies the source ("allowance:12", "overtime:340", "loan:7") and is
    unique per company, so running the generation again never creates a second input.
    """
    _name = 'healthcare.payroll.input'
    _description = 'Healthcare Payroll Input'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_to desc, employee_id, id'
    _check_company_auto = True

    name = fields.Char(required=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    date_from = fields.Date(required=True, index=True, string='Period Start')
    date_to = fields.Date(required=True, index=True, string='Period End')
    source_type = fields.Selection(SOURCE_TYPES, required=True, index=True, tracking=True)
    input_type_id = fields.Many2one('hr.payslip.input.type', required=True,
                                    domain=[('healthcare_source_type', '!=', False)])
    quantity = fields.Float(help="Hours, shifts or 1.")
    amount = fields.Monetary(required=True, tracking=True, aggregator='sum')
    source_model = fields.Char(readonly=True)
    source_res_id = fields.Many2oneReference(model_field='source_model', readonly=True, string='Source Record')
    processing_key = fields.Char(required=True, readonly=True, index=True, copy=False)
    payslip_id = fields.Many2one('hr.payslip', readonly=True, copy=False, index='btree_not_null')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('included', 'In Payslip'),
        ('done', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='confirmed', required=True, index=True, tracking=True, copy=False)
    note = fields.Text()

    _key_uniq = models.Constraint('unique (processing_key, company_id)',
                                  'This source was already sent to payroll.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('processing_key'):
                # manual bonus / deduction
                vals['processing_key'] = f"manual:{self.env['ir.sequence'].next_by_code('healthcare.payroll.input.manual') or fields.Datetime.now()}"
                vals.setdefault('state', 'draft')
            if vals.get('source_type') and not vals.get('input_type_id'):
                vals['input_type_id'] = self._input_type_for(vals['source_type']).id
        return super().create(vals_list)

    @api.model
    def _input_type_for(self, source_type):
        return self.env['hr.payslip.input.type'].search([('healthcare_source_type', '=', source_type)], limit=1)

    @api.onchange('source_type')
    def _onchange_source_type(self):
        if self.source_type:
            self.input_type_id = self._input_type_for(self.source_type)

    def action_confirm(self):
        self.filtered(lambda i: i.state == 'draft').write({'state': 'confirmed'})

    def action_cancel(self):
        if self.filtered(lambda i: i.state in ('included', 'done')):
            raise UserError(self.env._('Inputs already in a payslip cannot be cancelled; cancel the payslip first.'))
        self.write({'state': 'cancelled'})

    def action_draft(self):
        if self.filtered(lambda i: i.state in ('included', 'done')):
            raise UserError(self.env._('Inputs already in a payslip cannot be reset.'))
        self.write({'state': 'draft'})

    def unlink(self):
        if self.filtered(lambda i: i.state in ('included', 'done')):
            raise UserError(self.env._('Inputs already in a payslip cannot be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    @api.model
    def _hc_collect_sources(self, date_from, date_to, company, employees=None):
        """Return a list of input values (with processing_key) for the period.
        Extended by other modules (loans ...). Only approved data is collected."""
        vals_list = []
        # Allowances
        domain = [('company_id', '=', company.id), ('state', '=', 'confirmed'),
                  ('date_from', '>=', date_from), ('date_to', '<=', date_to)]
        if employees:
            domain.append(('employee_id', 'in', employees.ids))
        mapping = {
            'night_shift': 'night_allowance', 'weekend': 'weekend_allowance',
            'public_holiday': 'holiday_allowance', 'on_call': 'on_call', 'call_in': 'on_call',
        }
        for result in self.env['healthcare.allowance.result'].sudo().search(domain):
            input_type = result.type_id.payslip_input_type_id
            source_type = input_type.healthcare_source_type or mapping.get(result.category, 'allowance')
            vals_list.append({
                'name': result.rule_id.name, 'employee_id': result.employee_id.id, 'company_id': company.id,
                'date_from': date_from, 'date_to': date_to, 'source_type': source_type,
                'input_type_id': (input_type or self._input_type_for(source_type)).id,
                'quantity': result.quantity, 'amount': result.amount,
                'source_model': result._name, 'source_res_id': result.id,
                'processing_key': f'allowance:{result.id}',
            })
        # Approved overtime (payroll overtime hours after rounding)
        # the processing key (not payroll_processed) prevents duplicates: a shift can feed
        # both an allowance and an overtime input
        domain = [('company_id', '=', company.id), ('state', 'in', ('approved', 'payroll_posted')),
                  ('payroll_overtime_hours', '>', 0), ('date', '>=', date_from), ('date', '<=', date_to)]
        if employees:
            domain.append(('employee_id', 'in', employees.ids))
        overtime_type = self._input_type_for('overtime')
        for shift in self.env['healthcare.shift.assignment'].sudo().search(domain):
            version = shift.employee_id._get_version(shift.date)
            hourly = company._hc_hourly_rate(version.wage or 0.0, version.resource_calendar_id)
            amount = round(shift.payroll_overtime_hours * hourly * (company.hc_overtime_rate or 1.0), 2)
            vals_list.append({
                'name': self.env._('Overtime %(date)s (%(hours).2f h)', date=shift.date, hours=shift.payroll_overtime_hours),
                'employee_id': shift.employee_id.id, 'company_id': company.id,
                'date_from': date_from, 'date_to': date_to, 'source_type': 'overtime',
                'input_type_id': overtime_type.id, 'quantity': shift.payroll_overtime_hours, 'amount': amount,
                'source_model': shift._name, 'source_res_id': shift.id,
                'processing_key': f'overtime:{shift.id}',
            })
        return vals_list

    @api.model
    def _generate_for_period(self, date_from, date_to, company=None, employees=None):
        """Create missing inputs, refresh unconsumed ones. Never duplicates, never touches
        inputs already in a payslip."""
        company = company or self.env.company
        vals_list = [v for v in self._hc_collect_sources(date_from, date_to, company, employees) if v.get('amount')]
        keys = [v['processing_key'] for v in vals_list]
        existing = {i.processing_key: i for i in self.sudo().with_context(active_test=False).search(
            [('company_id', '=', company.id), ('processing_key', 'in', keys)])}
        to_create, touched = [], self.browse()
        for vals in vals_list:
            record = existing.get(vals['processing_key'])
            if record:
                touched |= record
                if record.state in ('draft', 'confirmed') and abs(record.amount - vals['amount']) > 0.001:
                    record.write({'amount': vals['amount'], 'quantity': vals.get('quantity', 0.0)})
            else:
                to_create.append(dict(vals, state='confirmed'))
        created = self.sudo().create(to_create)
        _logger.info('Healthcare payroll inputs %s..%s: %s created, %s already present',
                     date_from, date_to, len(created), len(touched))
        return created | touched

    # ------------------------------------------------------------------
    # Payslip lifecycle hooks
    # ------------------------------------------------------------------
    def _hc_mark_sources_processed(self):
        groups = defaultdict(list)
        for record in self:
            groups[record.source_model].append(record.source_res_id)
        if groups.get('healthcare.allowance.result'):
            results = self.env['healthcare.allowance.result'].sudo().browse(groups['healthcare.allowance.result'])
            results.write({'state': 'processed'})
            results.assignment_ids.write({'payroll_processed': True})
            results.oncall_ids.write({'payroll_processed': True})
        if groups.get('healthcare.shift.assignment'):
            self.env['healthcare.shift.assignment'].sudo().browse(groups['healthcare.shift.assignment']).write(
                {'payroll_processed': True})

    def _hc_release_sources(self):
        groups = defaultdict(list)
        for record in self:
            groups[record.source_model].append(record.source_res_id)
        if groups.get('healthcare.allowance.result'):
            results = self.env['healthcare.allowance.result'].sudo().browse(groups['healthcare.allowance.result'])
            results.filtered(lambda r: r.state == 'processed').write({'state': 'confirmed'})
            results.assignment_ids.write({'payroll_processed': False})
            results.oncall_ids.write({'payroll_processed': False})
        if groups.get('healthcare.shift.assignment'):
            self.env['healthcare.shift.assignment'].sudo().browse(groups['healthcare.shift.assignment']).write(
                {'payroll_processed': False})

    @api.model
    def _cron_generate_current_month(self):
        today = fields.Date.context_today(self)
        date_from = today.replace(day=1)
        date_to = fields.Date.end_of(today, 'month')
        for company in self.env['res.company'].search([]):
            self.with_company(company)._generate_for_period(date_from, date_to, company)
        return True

    @api.model
    def _hc_load_demo_payroll(self):
        """Approve the demo reconciliation, compute allowances, generate inputs and draft payslips."""
        today = fields.Date.context_today(self)
        date_from, date_to = today.replace(day=1), fields.Date.end_of(today, 'month')
        structure_type = self.env.ref('hr.structure_type_employee', raise_if_not_found=False)
        employees = self.env['hr.employee'].search([('employee_number', '!=', False),
                                                    ('company_id', '=', self.env.company.id)])
        if structure_type:
            employees.filtered(lambda e: not e.structure_type_id).write({'structure_type_id': structure_type.id})
        for rec in self.env['healthcare.attendance.reconciliation'].search([('state', '=', 'computed')]):
            rec.action_approve()
        results = self.env['healthcare.allowance.rule']._compute_period(date_from, date_to)
        results.action_confirm()
        self._generate_for_period(date_from, date_to)
        self.create({
            'name': 'Excellence bonus', 'employee_id': self.env.ref('healthcare_hr_core.demo_emp_nurse_mona').id,
            'source_type': 'bonus', 'date_from': date_from, 'date_to': date_to, 'amount': 750,
            'note': 'Demo: approved by the nursing director', 'state': 'confirmed'})
        slips = self.env['hr.payslip']
        for xmlid in ('nurse_mona', 'dr_sara', 'nurse_hala'):
            employee = self.env.ref(f'healthcare_hr_core.demo_emp_{xmlid}')
            slips |= self.env['hr.payslip'].create({
                'name': f'Demo payslip {employee.name}', 'employee_id': employee.id,
                'date_from': date_from, 'date_to': date_to})
        slips.compute_sheet()
        return slips
