import logging
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from odoo.addons.healthcare_hr_core.models.hr_employee import EMPLOYEE_CATEGORIES
from odoo.addons.healthcare_hr_shift.models.shift_template import SHIFT_TYPES

_logger = logging.getLogger(__name__)

HOUR_BASES = [
    ('night_hours', 'Night Hours'),
    ('weekend_hours', 'Weekend Hours'),
    ('holiday_hours', 'Public Holiday Hours'),
    ('worked_hours', 'Worked Hours'),
    ('planned_hours', 'Planned Hours'),
    ('overtime_hours', 'Payroll Overtime Hours'),
    ('oncall_standby_hours', 'On-call Standby Hours'),
    ('oncall_worked_hours', 'On-call Worked (Call-in) Hours'),
]
SHIFT_BASES = [
    ('all', 'Every Shift'),
    ('night', 'Shifts with Night Hours'),
    ('weekend', 'Shifts with Weekend Hours'),
    ('holiday', 'Shifts on Public Holidays'),
    ('oncall', 'On-call Duties'),
    ('callin', 'On-call Call-ins'),
]
SHIFT_METHODS = ('per_shift', 'per_hour')


class AllowanceRule(models.Model):
    _name = 'healthcare.allowance.rule'
    _description = 'Allowance Rule'
    _inherit = ['mail.thread']
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(required=True, translate=True, tracking=True)
    sequence = fields.Integer(default=10, help="Rules are computed in this order (percentage of gross uses the "
                                               "amounts of the rules computed before it).")
    type_id = fields.Many2one('healthcare.allowance.type', required=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    calculation_method = fields.Selection([
        ('fixed', 'Fixed Amount per Period'),
        ('per_shift', 'Per Shift'),
        ('per_hour', 'Per Hour'),
        ('percentage_basic', 'Percentage of Basic'),
        ('percentage_gross', 'Percentage of Gross'),
        ('formula', 'Formula'),
    ], required=True, default='fixed', tracking=True)
    hour_basis = fields.Selection(HOUR_BASES, default='night_hours')
    shift_basis = fields.Selection(SHIFT_BASES, default='all')
    amount = fields.Monetary(tracking=True, help="Fixed amount, amount per shift or rate per hour.")
    percentage = fields.Float(tracking=True)
    minimum = fields.Monetary(help="Minimum per period when the rule applies (0 = none).")
    maximum = fields.Monetary(help="Maximum per period (0 = none).")
    formula = fields.Text(
        help="Python code setting `result`. Available: employee, version (contract), wage, hours (dict of "
             "night_hours, weekend_hours, holiday_hours, worked_hours, planned_hours, overtime_hours, "
             "oncall_standby_hours, oncall_worked_hours), shifts (dict of all, night, weekend, holiday, "
             "oncall, callin counts), days (period length).")
    # Filters
    effective_from = fields.Date()
    effective_to = fields.Date()
    employee_category = fields.Selection(EMPLOYEE_CATEGORIES)
    department_id = fields.Many2one('hr.department', check_company=True,
                                    help="Shift-based rules: department of the shift. Others: employee department.")
    branch_id = fields.Many2one('healthcare.hr.branch', check_company=True)
    unit_id = fields.Many2one('healthcare.hr.unit', check_company=True)
    job_id = fields.Many2one('hr.job', check_company=True)
    contract_type_id = fields.Many2one('hr.contract.type')
    shift_type = fields.Selection(SHIFT_TYPES)
    shift_template_ids = fields.Many2many(
        'healthcare.shift.template', 'healthcare_allowance_rule_shift_template_rel', 'rule_id', 'template_id',
        string='Shift Templates')
    taxable = fields.Boolean(related='type_id.taxable')
    active = fields.Boolean(default=True)

    @api.constrains('calculation_method', 'formula', 'percentage', 'minimum', 'maximum', 'effective_from', 'effective_to')
    def _check_rule(self):
        for rule in self:
            if rule.calculation_method == 'formula' and not (rule.formula or '').strip():
                raise ValidationError(self.env._('A formula rule needs a formula.'))
            if rule.maximum and rule.minimum and rule.maximum < rule.minimum:
                raise ValidationError(self.env._('The maximum cannot be lower than the minimum.'))
            if rule.effective_from and rule.effective_to and rule.effective_to < rule.effective_from:
                raise ValidationError(self.env._('The end date is before the start date.'))

    # ------------------------------------------------------------------
    # Applicability
    # ------------------------------------------------------------------
    def _effective_in(self, date_from, date_to):
        self.ensure_one()
        return (not self.effective_from or self.effective_from <= date_to) and \
               (not self.effective_to or self.effective_to >= date_from)

    def _applies_to_employee(self, employee, version):
        self.ensure_one()
        if self.employee_category and employee.employee_category != self.employee_category:
            return False
        if self.job_id and employee.job_id != self.job_id:
            return False
        if self.contract_type_id and version.contract_type_id != self.contract_type_id:
            return False
        if self.calculation_method not in SHIFT_METHODS:
            if self.department_id and self.department_id not in (employee.department_id | employee.medical_department_id):
                return False
            if self.branch_id and not (employee.healthcare_branch_id and
                                       employee.healthcare_branch_id.parent_path.startswith(self.branch_id.parent_path)):
                return False
            if self.unit_id and employee.healthcare_unit_id != self.unit_id:
                return False
        return True

    def _shift_matches(self, shift):
        self.ensure_one()
        if self.department_id and shift.department_id != self.department_id:
            return False
        if self.unit_id and shift.unit_id != self.unit_id:
            return False
        if self.branch_id and not (shift.branch_id and shift.branch_id.parent_path.startswith(self.branch_id.parent_path)):
            return False
        if self.shift_type and shift.shift_type != self.shift_type:
            return False
        if self.shift_template_ids and shift.shift_template_id not in self.shift_template_ids:
            return False
        if self.effective_from and shift.date < self.effective_from:
            return False
        if self.effective_to and shift.date > self.effective_to:
            return False
        return True

    def _oncall_matches(self, oncall):
        self.ensure_one()
        if self.department_id and oncall.department_id != self.department_id:
            return False
        if self.branch_id and not (oncall.branch_id and oncall.branch_id.parent_path.startswith(self.branch_id.parent_path)):
            return False
        return True

    # ------------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------------
    @staticmethod
    def _shift_quantities(shifts, oncalls):
        hours = defaultdict(float)
        counts = defaultdict(int)
        for shift in shifts:
            hours['night_hours'] += shift.night_hours
            hours['weekend_hours'] += shift.weekend_hours
            hours['holiday_hours'] += shift.holiday_hours
            hours['worked_hours'] += shift.actual_worked_hours
            hours['planned_hours'] += shift.planned_hours
            hours['overtime_hours'] += shift.payroll_overtime_hours
            counts['all'] += 1
            counts['night'] += 1 if shift.night_hours else 0
            counts['weekend'] += 1 if shift.weekend_hours else 0
            counts['holiday'] += 1 if shift.holiday_hours else 0
        for oncall in oncalls:
            hours['oncall_standby_hours'] += oncall.standby_hours
            hours['oncall_worked_hours'] += oncall.worked_hours
            counts['oncall'] += 1
            counts['callin'] += 1 if oncall.called_in else 0
        return hours, counts

    def _compute_amount(self, employee, version, shifts, oncalls, date_from, date_to, previous_total):
        """Return (quantity, rate, amount, note) for one employee over the period."""
        self.ensure_one()
        method = self.calculation_method
        wage = version.wage or 0.0
        if method in SHIFT_METHODS:
            shifts = shifts.filtered(self._shift_matches)
            oncalls = oncalls.filtered(self._oncall_matches)
        hours, counts = self._shift_quantities(shifts, oncalls)
        if method == 'fixed':
            quantity, rate = 1.0, self.amount
        elif method == 'per_shift':
            quantity, rate = float(counts[self.shift_basis or 'all']), self.amount
        elif method == 'per_hour':
            quantity, rate = round(hours[self.hour_basis or 'night_hours'], 2), self.amount
        elif method == 'percentage_basic':
            quantity, rate = wage, self.percentage / 100.0
        elif method == 'percentage_gross':
            quantity, rate = wage + previous_total, self.percentage / 100.0
        else:
            context = {
                'employee': employee, 'version': version, 'wage': wage, 'hours': dict(hours),
                'shifts': dict(counts), 'days': (date_to - date_from).days + 1, 'result': 0.0,
            }
            try:
                safe_eval(self.formula, context, mode='exec')
            except Exception as error:
                raise UserError(self.env._('Error in the formula of allowance rule "%(rule)s": %(error)s',
                                           rule=self.name, error=error))
            quantity, rate = 1.0, float(context.get('result') or 0.0)
        amount = quantity * rate
        if amount and self.minimum:
            amount = max(amount, self.minimum)
        if self.maximum:
            amount = min(amount, self.maximum)
        note = self.env._('%(qty)s x %(rate)s', qty=round(quantity, 2), rate=round(rate, 4))
        return quantity, rate, round(amount, 2), note, shifts, oncalls

    @api.model
    def _compute_period(self, date_from, date_to, employees=None, company=None):
        """(Re)compute allowance results for the period. Idempotent: existing results are
        updated in place, processed (payroll) results are never modified."""
        company = company or self.env.company
        rules = self.search([('company_id', '=', company.id)]).filtered(
            lambda r: r._effective_in(date_from, date_to))
        Shift = self.env['healthcare.shift.assignment'].sudo()
        shift_domain = [('company_id', '=', company.id), ('state', 'in', ('approved', 'payroll_posted')),
                        ('date', '>=', date_from), ('date', '<=', date_to)]
        oncall_domain = [('company_id', '=', company.id), ('state', '=', 'approved'),
                         ('start_datetime', '>=', fields.Datetime.to_datetime(date_from)),
                         ('start_datetime', '<', fields.Datetime.to_datetime(fields.Date.add(date_to, days=1)))]
        emp_domain = [('company_id', '=', company.id)]
        if employees:
            shift_domain.append(('employee_id', 'in', employees.ids))
            oncall_domain.append(('employee_id', 'in', employees.ids))
            emp_domain.append(('id', 'in', employees.ids))
        shifts = Shift.search(shift_domain)
        oncalls = self.env['healthcare.shift.oncall'].sudo().search(oncall_domain)
        shifts_by_emp, oncalls_by_emp = defaultdict(lambda: Shift.browse()), defaultdict(
            lambda: self.env['healthcare.shift.oncall'].sudo().browse())
        for shift in shifts:
            shifts_by_emp[shift.employee_id.id] |= shift
        for oncall in oncalls:
            oncalls_by_emp[oncall.employee_id.id] |= oncall
        all_employees = self.env['hr.employee'].sudo().search(emp_domain)

        Result = self.env['healthcare.allowance.result'].sudo()
        existing = {(r.employee_id.id, r.rule_id.id): r for r in Result.search([
            ('rule_id', 'in', rules.ids), ('date_from', '=', date_from), ('date_to', '=', date_to),
            ('employee_id', 'in', all_employees.ids)])}
        to_create, touched = [], Result.browse()
        oncall_amounts = defaultdict(float)
        for employee in all_employees:
            version = employee._get_version(date_to)
            if not employee._hc_is_under_contract(date_to) and not shifts_by_emp.get(employee.id):
                continue
            running_total = 0.0
            for rule in rules:
                if not rule._applies_to_employee(employee, version):
                    continue
                if rule.calculation_method in SHIFT_METHODS and not (
                        shifts_by_emp.get(employee.id) or oncalls_by_emp.get(employee.id)):
                    continue
                qty, rate, amount, note, used_shifts, used_oncalls = rule._compute_amount(
                    employee, version, shifts_by_emp[employee.id], oncalls_by_emp[employee.id],
                    date_from, date_to, running_total)
                running_total += amount
                if rule.type_id.category in ('on_call', 'call_in') and used_oncalls and amount:
                    total_hours = sum(used_oncalls.mapped('standby_hours')) + sum(used_oncalls.mapped('worked_hours'))
                    for oncall in used_oncalls:
                        share = (oncall.standby_hours + oncall.worked_hours) / total_hours if total_hours else 1 / len(used_oncalls)
                        oncall_amounts[oncall.id] += amount * share
                result = existing.get((employee.id, rule.id))
                vals = {'quantity': qty, 'rate': rate, 'amount': amount, 'computation_note': note,
                        'assignment_ids': [fields.Command.set(used_shifts.ids)],
                        'oncall_ids': [fields.Command.set(used_oncalls.ids)]}
                if result:
                    touched |= result
                    if result.state in ('processed', 'cancelled'):
                        continue
                    if abs(result.amount - amount) > 0.001 or result.quantity != qty:
                        vals['state'] = 'draft'
                        result.write(vals)
                elif amount:
                    to_create.append(dict(vals, employee_id=employee.id, rule_id=rule.id,
                                          date_from=date_from, date_to=date_to))
        created = Result.create(to_create)
        # results that no longer apply (e.g. shift reset) are removed while still draft
        (Result.browse([r.id for r in existing.values()]) - touched).filtered(
            lambda r: r.state == 'draft').unlink()
        (touched.filtered(lambda r: r.state == 'draft' and not r.amount)).unlink()
        for oncall in oncalls:
            if not oncall.payroll_processed:
                oncall.allowance_amount = round(oncall_amounts.get(oncall.id, 0.0), 2)
        return (created | touched).exists()
