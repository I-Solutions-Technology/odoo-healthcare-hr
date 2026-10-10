import calendar

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

COMPUTATIONS = [
    ('final_salary', 'Final Salary (prorated wage of the last month)'),
    ('unused_leave', 'Unused Leave (remaining days x daily wage)'),
    ('pending_overtime', 'Pending Approved Overtime'),
    ('pending_allowances', 'Pending Approved Allowances'),
    ('bonuses', 'Approved Bonuses'),
    ('deductions', 'Approved Deductions'),
    ('outstanding_loans', 'Outstanding Loans'),
    ('salary_advances', 'Outstanding Salary Advances'),
    ('clearance_obligations', 'Clearance Obligations'),
    ('formula', 'Formula (e.g. end of service)'),
    ('manual', 'Manual'),
]


class SettlementComponent(models.Model):
    """Final settlement building block. Components are data, so each country / company
    configures its own end-of-service formula instead of relying on hard-coded law."""
    _name = 'healthcare.hr.settlement.component'
    _description = 'Final Settlement Component'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    component_type = fields.Selection([('earning', 'Earning'), ('deduction', 'Deduction')], required=True,
                                      default='earning')
    computation = fields.Selection(COMPUTATIONS, required=True, default='manual')
    formula = fields.Text(help="Python code setting `result` (positive number). Variables: employee, version, "
                               "wage, daily_wage, service_years, service_days, exit_reason, last_working_date, "
                               "hire_date, remaining_leave_days.")
    daily_wage_basis = fields.Selection([('30', '30 days'), ('calendar', 'Calendar days of the month')],
                                        default='30', required=True)
    company_id = fields.Many2one('res.company', help="Empty = all companies.")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('unique (code, company_id)', 'The component code must be unique.')


class FinalSettlement(models.Model):
    _name = 'healthcare.hr.final.settlement'
    _description = 'Final Settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    exit_id = fields.Many2one('healthcare.hr.exit', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='exit_id.employee_id', store=True)
    company_id = fields.Many2one(related='exit_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='exit_id.branch_id', store=True)
    department_id = fields.Many2one(related='exit_id.department_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    last_working_date = fields.Date(related='exit_id.last_working_date', store=True)
    exit_reason = fields.Selection(related='exit_id.exit_reason', store=True)
    line_ids = fields.One2many('healthcare.hr.final.settlement.line', 'settlement_id', string='Lines')
    total_earnings = fields.Monetary(compute='_compute_totals', store=True)
    total_deductions = fields.Monetary(compute='_compute_totals', store=True)
    net_amount = fields.Monetary(compute='_compute_totals', store=True, aggregator='sum')
    state = fields.Selection([
        ('draft', 'Draft'), ('computed', 'Computed'), ('confirmed', 'Confirmed'), ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    payment_date = fields.Date(tracking=True)
    payment_reference = fields.Char(tracking=True)

    @api.depends('employee_id', 'last_working_date')
    def _compute_name(self):
        for rec in self:
            rec.name = self.env._('Final settlement - %(name)s (%(date)s)', name=rec.employee_id.name or '',
                                  date=rec.last_working_date or '')

    @api.depends('line_ids.amount')
    def _compute_totals(self):
        for rec in self:
            earnings = sum(line.amount for line in rec.line_ids if line.amount > 0)
            deductions = -sum(line.amount for line in rec.line_ids if line.amount < 0)
            rec.total_earnings, rec.total_deductions = earnings, deductions
            rec.net_amount = earnings - deductions

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------
    def _context_values(self):
        self.ensure_one()
        employee = self.employee_id.sudo()
        last_day = self.last_working_date
        version = employee._get_version(last_day)
        wage = version.wage or 0.0
        hire_date = employee.hire_date or version.contract_date_start or last_day
        service_days = max((last_day - hire_date).days + 1, 0)
        try:
            remaining_leave = float(employee.allocation_remaining_display or 0.0)
        except ValueError:
            remaining_leave = 0.0
        return {
            'employee': employee, 'version': version, 'wage': wage, 'hire_date': hire_date,
            'service_days': service_days, 'service_years': round(service_days / 365.25, 4),
            'exit_reason': self.exit_reason, 'last_working_date': last_day,
            'remaining_leave_days': remaining_leave,
        }

    def _pending_inputs(self, source_types):
        return self.env['healthcare.payroll.input'].sudo().search([
            ('employee_id', '=', self.employee_id.id), ('state', '=', 'confirmed'),
            ('source_type', 'in', source_types)])

    def _compute_component(self, component, values):
        """Return (amount (signed), note, records) for one component."""
        self.ensure_one()
        _ = self.env._
        wage = values['wage']
        days_in_month = 30 if component.daily_wage_basis == '30' else calendar.monthrange(
            values['last_working_date'].year, values['last_working_date'].month)[1]
        daily_wage = wage / days_in_month if days_in_month else 0.0
        sign = 1 if component.component_type == 'earning' else -1
        records = None
        method = component.computation
        if method == 'final_salary':
            worked_days = min(values['last_working_date'].day, days_in_month)
            amount, note = daily_wage * worked_days, _('%(days)s day(s) x %(rate).2f', days=worked_days, rate=daily_wage)
        elif method == 'unused_leave':
            days = values['remaining_leave_days']
            amount, note = daily_wage * days, _('%(days)s day(s) x %(rate).2f', days=days, rate=daily_wage)
        elif method in ('pending_overtime', 'pending_allowances', 'bonuses', 'deductions'):
            types = {
                'pending_overtime': ['overtime'],
                'pending_allowances': ['night_allowance', 'weekend_allowance', 'holiday_allowance', 'on_call', 'allowance'],
                'bonuses': ['bonus'],
                'deductions': ['deduction'],
            }[method]
            records = self._pending_inputs(types)
            amount, note = sum(records.mapped('amount')), _('%s approved input(s) not yet paid', len(records))
        elif method in ('outstanding_loans', 'salary_advances'):
            loan_type = 'loan' if method == 'outstanding_loans' else 'advance'
            records = self.env['healthcare.hr.loan'].sudo().search([
                ('employee_id', '=', self.employee_id.id), ('loan_type', '=', loan_type),
                ('state', 'in', ('approved', 'active'))])
            # installments already in a payslip are recovered by that payslip
            pending = records.installment_ids.filtered(lambda i: i.state == 'pending')
            amount, note = sum(pending.mapped('amount')), ', '.join(records.mapped('name'))
        elif method == 'clearance_obligations':
            items = self.exit_id.clearance_item_ids.filtered('amount_due')
            amount = sum(items.mapped('amount_due'))
            note = ', '.join(items.clearance_department_id.mapped('name'))
        elif method == 'formula':
            local = dict(values, daily_wage=daily_wage, result=0.0)
            try:
                safe_eval(component.formula or 'result = 0', local, mode='exec')
            except Exception as error:
                raise UserError(_('Error in the formula of settlement component "%(name)s": %(error)s',
                                  name=component.name, error=error))
            amount, note = float(local.get('result') or 0.0), _('Formula')
        else:
            return None
        return round(sign * abs(amount), 2), note, records

    def action_compute(self):
        for rec in self:
            if rec.state not in ('draft', 'computed'):
                raise UserError(self.env._('Only draft settlements can be recomputed.'))
            values = rec._context_values()
            components = self.env['healthcare.hr.settlement.component'].search(
                ['|', ('company_id', '=', False), ('company_id', '=', rec.company_id.id)])
            manual = rec.line_ids.filtered(lambda l: l.component_id.computation == 'manual' or not l.component_id)
            (rec.line_ids - manual).unlink()
            vals = []
            for component in components:
                computed = rec._compute_component(component, values)
                if computed is None:
                    continue
                amount, note, _records = computed
                if amount:
                    vals.append({'settlement_id': rec.id, 'component_id': component.id, 'name': component.name,
                                 'amount': amount, 'computation_note': note, 'sequence': component.sequence})
            self.env['healthcare.hr.final.settlement.line'].create(vals)
            rec.state = 'computed'

    def action_confirm(self):
        for rec in self:
            if rec.state != 'computed':
                raise UserError(self.env._('Compute the settlement first.'))
            rec.state = 'confirmed'
            rec.exit_id.state = 'hr_approval'
            self.env['healthcare.hr.alert'].schedule(
                rec.exit_id, 'exit_hr_approval', self.env._('Approve the exit of %s', rec.employee_id.name),
                user=rec.company_id.hc_alert_user_id or None)

    def action_mark_paid(self):
        """Close what the settlement paid or recovered: pending payroll inputs and loans."""
        for rec in self.filtered(lambda r: r.state == 'confirmed'):
            inputs = rec._pending_inputs(['overtime', 'night_allowance', 'weekend_allowance', 'holiday_allowance',
                                          'on_call', 'allowance', 'bonus', 'deduction'])
            inputs._hc_mark_sources_processed()
            inputs.write({'state': 'done', 'note': self.env._('Paid in %s', rec.name)})
            loans = self.env['healthcare.hr.loan'].sudo().search([
                ('employee_id', '=', rec.employee_id.id), ('state', '=', 'active')])
            loans.action_settle()
            rec.write({'state': 'paid', 'payment_date': rec.payment_date or fields.Date.context_today(self)})

    def action_reset(self):
        self.filtered(lambda r: r.state in ('computed', 'confirmed')).write({'state': 'draft'})
        self.exit_id.filtered(lambda e: e.state == 'hr_approval').write({'state': 'settlement'})


class FinalSettlementLine(models.Model):
    _name = 'healthcare.hr.final.settlement.line'
    _description = 'Final Settlement Line'
    _order = 'sequence, id'

    settlement_id = fields.Many2one('healthcare.hr.final.settlement', required=True, ondelete='cascade', index=True)
    component_id = fields.Many2one('healthcare.hr.settlement.component')
    sequence = fields.Integer(default=100)
    name = fields.Char(required=True)
    currency_id = fields.Many2one(related='settlement_id.currency_id')
    amount = fields.Monetary(help="Positive = paid to the employee, negative = recovered.")
    computation_note = fields.Char()
