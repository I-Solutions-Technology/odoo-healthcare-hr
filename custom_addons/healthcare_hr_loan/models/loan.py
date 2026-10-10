from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class HrLoan(models.Model):
    _name = 'healthcare.hr.loan'
    _description = 'Employee Loan / Salary Advance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(default=lambda self: self.env._('New'), readonly=True, copy=False)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True, tracking=True,
                                  default=lambda self: self.env.user.employee_id)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    loan_type = fields.Selection([('loan', 'Loan'), ('advance', 'Salary Advance')], required=True, default='loan',
                                 tracking=True)
    requested_amount = fields.Monetary(required=True, tracking=True)
    approved_amount = fields.Monetary(tracking=True, copy=False)
    request_date = fields.Date(required=True, default=fields.Date.context_today)
    approval_date = fields.Date(readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    payment_date = fields.Date(readonly=True, copy=False, help="Date the money was handed to the employee.")
    payment_reference = fields.Char(copy=False)
    installment_count = fields.Integer(required=True, default=1, tracking=True)
    installment_amount = fields.Monetary(compute='_compute_amounts', store=True)
    first_deduction_date = fields.Date(required=True, tracking=True,
                                       default=lambda self: fields.Date.end_of(
                                           fields.Date.context_today(self) + relativedelta(months=1), 'month'))
    installment_ids = fields.One2many('healthcare.hr.loan.installment', 'loan_id', string='Installments', copy=False)
    paid_amount = fields.Monetary(compute='_compute_amounts', store=True)
    remaining_amount = fields.Monetary(compute='_compute_amounts', store=True, aggregator='sum')
    reason = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New')) == self.env._('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('healthcare.hr.loan') or '/'
        return super().create(vals_list)

    @api.depends('state', 'approved_amount', 'requested_amount', 'installment_count', 'installment_ids.amount',
                 'installment_ids.state')
    def _compute_amounts(self):
        for loan in self:
            principal = loan.approved_amount or loan.requested_amount
            loan.installment_amount = float_round(principal / loan.installment_count, 2) if loan.installment_count else 0.0
            paid = sum(loan.installment_ids.filtered(lambda i: i.state == 'paid').mapped('amount'))
            loan.paid_amount = paid
            loan.remaining_amount = (principal - paid) if loan.state not in ('draft', 'refused', 'cancelled') else 0.0

    @api.constrains('requested_amount', 'approved_amount', 'installment_count')
    def _check_amounts(self):
        for loan in self:
            if loan.requested_amount <= 0 or loan.approved_amount < 0:
                raise ValidationError(self.env._('Loan amounts must be positive.'))
            if loan.installment_count < 1:
                raise ValidationError(self.env._('At least one installment is required.'))
            if loan.loan_type == 'advance' and loan.installment_count > 3:
                raise ValidationError(self.env._('A salary advance is recovered in at most 3 installments.'))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        self.filtered(lambda l: l.state == 'draft').write({'state': 'submitted'})

    def action_approve(self):
        for loan in self.filtered(lambda l: l.state == 'submitted'):
            loan.write({
                'state': 'approved',
                'approved_amount': loan.approved_amount or loan.requested_amount,
                'approval_date': fields.Date.context_today(self),
                'approved_by': self.env.uid,
            })
            loan._generate_installments()

    def action_refuse(self):
        self.filtered(lambda l: l.state in ('submitted', 'approved')).write({'state': 'refused'})

    def action_mark_paid(self):
        for loan in self.filtered(lambda l: l.state == 'approved'):
            loan.write({'state': 'active', 'payment_date': loan.payment_date or fields.Date.context_today(self)})
            loan.message_post(body=self.env._('Amount handed to the employee. Deductions start on %s.',
                                              loan.first_deduction_date))

    def action_cancel(self):
        for loan in self:
            if loan.installment_ids.filtered(lambda i: i.state in ('included', 'paid')):
                raise UserError(self.env._('%s already has deducted installments.', loan.name))
        self.installment_ids.unlink()
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.filtered(lambda l: l.state in ('refused', 'cancelled')).write({'state': 'draft'})

    def _generate_installments(self):
        for loan in self:
            if loan.installment_ids.filtered(lambda i: i.state != 'pending'):
                raise UserError(self.env._('Installments of %s were already deducted.', loan.name))
            loan.installment_ids.unlink()
            total = loan.approved_amount
            base = float_round(total / loan.installment_count, 2)
            vals = []
            for index in range(loan.installment_count):
                amount = base if index < loan.installment_count - 1 else float_round(total - base * index, 2)
                due = fields.Date.end_of(loan.first_deduction_date + relativedelta(months=index), 'month')
                vals.append({'loan_id': loan.id, 'sequence': index + 1, 'due_date': due, 'amount': amount})
            self.env['healthcare.hr.loan.installment'].create(vals)

    def _check_completion(self):
        for loan in self.filtered(lambda l: l.state == 'active'):
            if loan.installment_ids and all(i.state == 'paid' for i in loan.installment_ids):
                loan.state = 'completed'

    def action_settle(self, amount=None):
        """Early settlement (or final settlement): mark remaining installments settled."""
        for loan in self.filtered(lambda l: l.state == 'active'):
            loan.installment_ids.filtered(lambda i: i.state == 'pending').write(
                {'state': 'paid', 'settled': True})
            loan.message_post(body=self.env._('Remaining balance settled.'))
            loan._check_completion()


class HrLoanInstallment(models.Model):
    _name = 'healthcare.hr.loan.installment'
    _description = 'Loan Installment'
    _order = 'loan_id, sequence'

    loan_id = fields.Many2one('healthcare.hr.loan', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='loan_id.employee_id', store=True)
    company_id = fields.Many2one(related='loan_id.company_id', store=True)
    currency_id = fields.Many2one(related='loan_id.currency_id')
    sequence = fields.Integer()
    due_date = fields.Date(required=True, index=True)
    amount = fields.Monetary(required=True)
    state = fields.Selection([('pending', 'Pending'), ('included', 'In Payslip'), ('paid', 'Paid')],
                             default='pending', required=True, index=True)
    settled = fields.Boolean(help="Paid by early / final settlement instead of payroll.")
    payroll_input_id = fields.Many2one('healthcare.payroll.input', readonly=True)

    def action_postpone(self):
        """Move a pending installment one month after the last one."""
        for inst in self:
            if inst.state != 'pending':
                raise UserError(self.env._('Only pending installments can be postponed.'))
            if inst.payroll_input_id and inst.payroll_input_id.state in ('included', 'done'):
                raise UserError(self.env._('The installment is already in a payslip.'))
            last = max(inst.loan_id.installment_ids.mapped('due_date'))
            inst.payroll_input_id.sudo().unlink()
            inst.write({'due_date': fields.Date.end_of(last + relativedelta(months=1), 'month'),
                        'sequence': max(inst.loan_id.installment_ids.mapped('sequence')) + 1})
            inst.loan_id.message_post(body=self.env._('Installment postponed to %s.', inst.due_date))
