from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from odoo.addons.healthcare_hr_shift.models.shift_utils import get_tz, local_to_utc

_lt = LazyTranslate(__name__)

ACTIVE_SHIFT = ('published', 'confirmed', 'working', 'completed', 'approved', 'payroll_posted')

# key: (label, model, branch field, domain builder name)
KPIS = {
    # Headcount
    'employees': (_lt('Employees'), 'hr.employee', 'healthcare_branch_id', '_d_employees'),
    'doctors': (_lt('Doctors'), 'hr.employee', 'healthcare_branch_id', '_d_doctors'),
    'nurses': (_lt('Nurses'), 'hr.employee', 'healthcare_branch_id', '_d_nurses'),
    'technicians': (_lt('Technicians'), 'hr.employee', 'healthcare_branch_id', '_d_technicians'),
    'administrative': (_lt('Administrative'), 'hr.employee', 'healthcare_branch_id', '_d_administrative'),
    'new_hires': (_lt('New Hires (30 d)'), 'hr.employee', 'healthcare_branch_id', '_d_new_hires'),
    'exits': (_lt('Exits (30 d)'), 'healthcare.hr.exit', 'branch_id', '_d_exits'),
    # Attendance
    'present': (_lt('Present Today'), 'hr.attendance', 'branch_id', '_d_present'),
    'absent': (_lt('Absent Today'), 'healthcare.shift.assignment', 'branch_id', '_d_absent'),
    'late': (_lt('Late Today'), 'hr.attendance', 'branch_id', '_d_late'),
    'on_leave': (_lt('On Leave Today'), 'hr.leave', None, '_d_on_leave'),
    'missing_checkout': (_lt('Missing Checkout'), 'hr.attendance', 'branch_id', '_d_missing_checkout'),
    'overtime_shifts': (_lt('Shifts with Overtime (month)'), 'healthcare.shift.assignment', 'branch_id', '_d_overtime'),
    # Workforce
    'scheduled': (_lt('Scheduled Today'), 'healthcare.shift.assignment', 'branch_id', '_d_scheduled'),
    'shortages': (_lt('Shift Shortages (14 d)'), 'healthcare.shift.coverage.snapshot', 'branch_id', '_d_shortages'),
    'open_shifts': (_lt('Draft Shifts (7 d)'), 'healthcare.shift.assignment', 'branch_id', '_d_open_shifts'),
    'conflicts': (_lt('Conflicts'), 'healthcare.shift.assignment', 'branch_id', '_d_conflicts'),
    'night_shifts': (_lt('Night Shifts Today'), 'healthcare.shift.assignment', 'branch_id', '_d_night'),
    # Compliance
    'contracts_expiring': (_lt('Contracts Expiring (60 d)'), 'hr.version', None, '_d_contracts_expiring'),
    'probation_ending': (_lt('Probation Ending (30 d)'), 'hr.version', None, '_d_probation_ending'),
    'licenses_expiring': (_lt('Licenses Expiring'), 'healthcare.hr.credential', 'branch_id', '_d_licenses_expiring'),
    'credentials_expired': (_lt('Expired / Missing Credentials'), 'healthcare.hr.credential', 'branch_id', '_d_credentials_expired'),
    'training_missing': (_lt('Missing Training'), 'healthcare.training.assignment', 'branch_id', '_d_training_missing'),
    'training_expired': (_lt('Expired Training'), 'healthcare.training.assignment', 'branch_id', '_d_training_expired'),
}


class HealthcareDashboard(models.TransientModel):
    _name = 'healthcare.hr.dashboard'
    _description = 'Healthcare HR Dashboard'

    branch_id = fields.Many2one('healthcare.hr.branch', string='Branch')
    date = fields.Date(default=fields.Date.context_today, required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    training_installed = fields.Boolean(compute='_compute_kpis')
    payroll_visible = fields.Boolean(compute='_compute_kpis')

    # counters (one field per KPI)
    employees = fields.Integer(compute='_compute_kpis')
    doctors = fields.Integer(compute='_compute_kpis')
    nurses = fields.Integer(compute='_compute_kpis')
    technicians = fields.Integer(compute='_compute_kpis')
    administrative = fields.Integer(compute='_compute_kpis')
    new_hires = fields.Integer(compute='_compute_kpis')
    exits = fields.Integer(compute='_compute_kpis')
    present = fields.Integer(compute='_compute_kpis')
    absent = fields.Integer(compute='_compute_kpis')
    late = fields.Integer(compute='_compute_kpis')
    on_leave = fields.Integer(compute='_compute_kpis')
    missing_checkout = fields.Integer(compute='_compute_kpis')
    overtime_shifts = fields.Integer(compute='_compute_kpis')
    scheduled = fields.Integer(compute='_compute_kpis')
    shortages = fields.Integer(compute='_compute_kpis')
    open_shifts = fields.Integer(compute='_compute_kpis')
    conflicts = fields.Integer(compute='_compute_kpis')
    night_shifts = fields.Integer(compute='_compute_kpis')
    contracts_expiring = fields.Integer(compute='_compute_kpis')
    probation_ending = fields.Integer(compute='_compute_kpis')
    licenses_expiring = fields.Integer(compute='_compute_kpis')
    credentials_expired = fields.Integer(compute='_compute_kpis')
    training_missing = fields.Integer(compute='_compute_kpis')
    training_expired = fields.Integer(compute='_compute_kpis')
    overtime_hours = fields.Float(compute='_compute_kpis', string='Approved Overtime (h, month)')
    payroll_total = fields.Monetary(compute='_compute_kpis', string='Net Payroll (month)')
    overtime_cost = fields.Monetary(compute='_compute_kpis', string='Overtime Cost (month)')
    allowance_cost = fields.Monetary(compute='_compute_kpis', string='Allowance Cost (month)')

    # ------------------------------------------------------------------
    # Period helpers
    # ------------------------------------------------------------------
    def _day_bounds_utc(self):
        tz = get_tz(self.env.user.tz or self.company_id.partner_id.tz)
        start = local_to_utc(datetime.combine(self.date, time.min), tz)
        return start, start + timedelta(days=1)

    def _month(self):
        return self.date.replace(day=1), self.date + relativedelta(day=31)

    # ------------------------------------------------------------------
    # Domains (one per KPI, reused by the drill-down)
    # ------------------------------------------------------------------
    def _d_employees(self):
        return [('company_id', '=', self.company_id.id)]

    def _d_doctors(self):
        return self._d_employees() + [('employee_category', 'in', ('doctor', 'radiology_doctor'))]

    def _d_nurses(self):
        return self._d_employees() + [('employee_category', '=', 'nurse')]

    def _d_technicians(self):
        return self._d_employees() + [('employee_category', 'in', (
            'lab_technician', 'radiology_technician', 'medical_technician', 'pharmacist'))]

    def _d_administrative(self):
        return self._d_employees() + [('is_clinical', '=', False)]

    def _d_new_hires(self):
        return self._d_employees() + [('hire_date', '>=', self.date - timedelta(days=30))]

    def _d_exits(self):
        return [('company_id', '=', self.company_id.id), ('state', '=', 'done'),
                ('last_working_date', '>=', self.date - timedelta(days=30))]

    def _d_present(self):
        start, end = self._day_bounds_utc()
        return [('employee_id.company_id', '=', self.company_id.id), ('check_in', '>=', start), ('check_in', '<', end)]

    def _d_absent(self):
        now = fields.Datetime.now()
        return [('company_id', '=', self.company_id.id), ('date', '=', self.date),
                '|', ('attendance_status', '=', 'absent'),
                '&', '&', ('state', 'in', ('published', 'confirmed')), ('datetime_start', '<', now - timedelta(minutes=30)),
                ('attendance_ids', '=', False)]

    def _d_late(self):
        return self._d_present() + [('late_minutes', '>', 0)]

    def _d_on_leave(self):
        start, end = self._day_bounds_utc()
        return [('employee_id.company_id', '=', self.company_id.id), ('state', '=', 'validate'),
                ('date_from', '<', end), ('date_to', '>', start)] + (
            [('employee_id.healthcare_branch_id', 'child_of', self.branch_id.id)] if self.branch_id else [])

    def _d_missing_checkout(self):
        return [('employee_id.company_id', '=', self.company_id.id), ('attendance_status', '=', 'missing_checkout')]

    def _d_overtime(self):
        month_start, month_end = self._month()
        return [('company_id', '=', self.company_id.id), ('date', '>=', month_start), ('date', '<=', month_end),
                ('overtime_hours', '>', 0)]

    def _d_scheduled(self):
        return [('company_id', '=', self.company_id.id), ('date', '=', self.date), ('state', 'in', ACTIVE_SHIFT)]

    def _d_shortages(self):
        return [('company_id', '=', self.company_id.id), ('date', '>=', self.date),
                ('date', '<=', self.date + timedelta(days=14)), ('status', '=', 'short')]

    def _d_open_shifts(self):
        return [('company_id', '=', self.company_id.id), ('state', '=', 'draft'), ('date', '>=', self.date),
                ('date', '<=', self.date + timedelta(days=7))]

    def _d_conflicts(self):
        return [('company_id', '=', self.company_id.id), ('state', '=', 'conflict'), ('date', '>=', self.date)]

    def _d_night(self):
        return self._d_scheduled() + [('night_hours', '>', 0)]

    def _d_contracts_expiring(self):
        return [('company_id', '=', self.company_id.id), ('employee_id.active', '=', True),
                ('contract_date_end', '>=', self.date), ('contract_date_end', '<=', self.date + timedelta(days=60))] + (
            [('employee_id.healthcare_branch_id', 'child_of', self.branch_id.id)] if self.branch_id else [])

    def _d_probation_ending(self):
        return [('company_id', '=', self.company_id.id), ('employee_id.active', '=', True),
                ('probation_status', 'in', ('started', 'review_due', 'extended')),
                ('trial_date_end', '<=', self.date + timedelta(days=30))] + (
            [('employee_id.healthcare_branch_id', 'child_of', self.branch_id.id)] if self.branch_id else [])

    def _d_licenses_expiring(self):
        return [('company_id', '=', self.company_id.id), ('credential_category', 'in', ('license', 'registration')),
                ('status', '=', 'expiring')]

    def _d_credentials_expired(self):
        return [('company_id', '=', self.company_id.id), ('status', 'in', ('expired', 'missing')),
                ('employee_id.active', '=', True)]

    def _d_training_missing(self):
        return [('company_id', '=', self.company_id.id), ('state', 'in', ('assigned', 'in_progress')),
                ('due_date', '<', self.date)]

    def _d_training_expired(self):
        return [('company_id', '=', self.company_id.id), ('state', '=', 'expired')]

    def _kpi_domain(self, key):
        _label, model, branch_field, builder = KPIS[key]
        domain = getattr(self, builder)()
        if self.branch_id and branch_field:
            domain = domain + [(branch_field, 'child_of', self.branch_id.id)]
        return model, domain

    # ------------------------------------------------------------------
    @api.depends('branch_id', 'date', 'company_id')
    def _compute_kpis(self):
        for dash in self:
            for key in KPIS:
                model, domain = dash._kpi_domain(key)
                if model not in self.env or not self.env[model].has_access('read'):
                    dash[key] = 0
                    continue
                try:
                    dash[key] = self.env[model].search_count(domain)
                except AccessError:  # e.g. contract dates are restricted to HR managers
                    dash[key] = 0
            dash.training_installed = 'healthcare.training.assignment' in self.env
            month_start, month_end = dash._month()
            shift_model, shift_domain = dash._kpi_domain('overtime_shifts')
            dash.overtime_hours = (self.env[shift_model]._read_group(shift_domain, [], ['overtime_hours:sum'])[0][0]
                                   if self.env[shift_model].has_access('read') else 0.0) or 0.0
            payroll = self.env.user.has_group('healthcare_hr_core.group_hc_payroll_officer')
            dash.payroll_visible = payroll
            if not payroll:
                dash.payroll_total = dash.overtime_cost = dash.allowance_cost = 0.0
                continue
            branch = [('healthcare_branch_id', 'child_of', dash.branch_id.id)] if dash.branch_id else []
            dash.payroll_total = self.env['hr.payslip']._read_group(
                [('company_id', '=', dash.company_id.id), ('state', 'in', ('validated', 'paid')),
                 ('date_to', '>=', month_start), ('date_to', '<=', month_end)] + branch, [], ['net_wage:sum'])[0][0] or 0.0
            branch = [('branch_id', 'child_of', dash.branch_id.id)] if dash.branch_id else []
            dash.overtime_cost = self.env['healthcare.payroll.input']._read_group(
                [('company_id', '=', dash.company_id.id), ('source_type', '=', 'overtime'), ('state', '!=', 'cancelled'),
                 ('date_to', '>=', month_start), ('date_to', '<=', month_end)] + branch, [], ['amount:sum'])[0][0] or 0.0
            dash.allowance_cost = self.env['healthcare.allowance.result']._read_group(
                [('company_id', '=', dash.company_id.id), ('state', '!=', 'cancelled'),
                 ('date_to', '>=', month_start), ('date_to', '<=', month_end)] + branch, [], ['amount:sum'])[0][0] or 0.0

    # ------------------------------------------------------------------
    @api.model
    def action_open_dashboard(self):
        dashboard = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Healthcare HR Dashboard'),
            'res_model': self._name,
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_open_kpi(self):
        self.ensure_one()
        key = self.env.context.get('kpi')
        if key not in KPIS:
            raise UserError(self.env._('Unknown indicator.'))
        label, model, _branch_field, _builder = KPIS[key]
        _model, domain = self._kpi_domain(key)
        views = {
            'hr.employee': 'list,kanban,form', 'hr.attendance': 'list,form', 'hr.leave': 'list,form',
            'hr.version': 'list', 'healthcare.shift.coverage.snapshot': 'list,pivot',
        }
        return {
            'type': 'ir.actions.act_window',
            'name': str(label),
            'res_model': model,
            'view_mode': views.get(model, 'list,form'),
            'domain': domain,
            'target': 'current',
        }

    def action_open_payroll(self):
        self.ensure_one()
        target = self.env.context.get('target_action')
        return self.env['ir.actions.actions']._for_xml_id(target)
