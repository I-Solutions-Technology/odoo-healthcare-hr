from odoo import api, fields, models
from odoo.exceptions import UserError


class AllowanceResult(models.Model):
    _name = 'healthcare.allowance.result'
    _description = 'Allowance Result'
    _inherit = ['mail.thread']
    _order = 'date_from desc, employee_id, rule_id'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, check_company=True)
    rule_id = fields.Many2one('healthcare.allowance.rule', required=True, index=True, ondelete='restrict')
    type_id = fields.Many2one(related='rule_id.type_id', store=True)
    category = fields.Selection(related='rule_id.type_id.category', store=True)
    taxable = fields.Boolean(related='rule_id.type_id.taxable', store=True)
    company_id = fields.Many2one(related='rule_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True)
    date_from = fields.Date(required=True, index=True)
    date_to = fields.Date(required=True, index=True)
    quantity = fields.Float(digits=(16, 2))
    rate = fields.Float(digits=(16, 4))
    amount = fields.Monetary(aggregator='sum', tracking=True)
    computation_note = fields.Char()
    assignment_ids = fields.Many2many('healthcare.shift.assignment', string='Shifts')
    oncall_ids = fields.Many2many('healthcare.shift.oncall', string='On-call Duties')
    state = fields.Selection([
        ('draft', 'Draft'), ('confirmed', 'Confirmed'), ('processed', 'In Payroll'), ('cancelled', 'Cancelled'),
    ], default='draft', required=True, index=True, tracking=True)

    _period_uniq = models.Constraint('unique (employee_id, rule_id, date_from, date_to)',
                                     'One result per employee, rule and period.')

    @api.depends('employee_id', 'rule_id', 'date_from')
    def _compute_name(self):
        for rec in self:
            rec.name = f'{rec.rule_id.name or ""} - {rec.employee_id.name or ""} ({rec.date_from or ""})'

    def action_confirm(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'confirmed'})

    def action_draft(self):
        if self.filtered(lambda r: r.state == 'processed'):
            raise UserError(self.env._('Allowances already in payroll cannot be reset.'))
        self.write({'state': 'draft'})

    def action_cancel(self):
        if self.filtered(lambda r: r.state == 'processed'):
            raise UserError(self.env._('Allowances already in payroll cannot be cancelled.'))
        self.write({'state': 'cancelled'})

    def unlink(self):
        if self.filtered(lambda r: r.state == 'processed'):
            raise UserError(self.env._('Allowances already in payroll cannot be deleted.'))
        return super().unlink()
