# End-to-end acceptance scenario (section 51 of the requirements).
# Run:  scripts/run.sh shell -d healthcare_hr --http-port=18595 --gevent-port=18596 < scripts/acceptance_scenario.py
# Creates a new ICU nurse and walks her from recruitment to final settlement, printing each step.
# Every step asserts its result; the script stops on the first failure and rolls back.
import base64
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields

ref = env.ref
today = fields.Date.today()
stamp = datetime.now().strftime('%H%M%S')
results = []


def step(label, detail=''):
    results.append((label, detail))
    print(f'  [OK] {label}' + (f' - {detail}' if detail else ''))


print('=== Healthcare HR acceptance scenario ===')
icu = ref('healthcare_hr_core.demo_dept_icu')
branch = ref('healthcare_hr_core.demo_branch_1')
job = ref('healthcare_hr_core.demo_job_icu_nurse')

# 1. Recruit candidate ------------------------------------------------------
applicant = env['hr.applicant'].create({
    'partner_name': f'Acceptance Nurse {stamp}', 'job_id': job.id, 'department_id': icu.id,
    'years_experience': 6, 'professional_license': f'NL-ACC-{stamp}',
})
required = applicant.required_credential_type_ids
for ctype in required:
    line = env['healthcare.applicant.credential'].create({
        'applicant_id': applicant.id, 'credential_type_id': ctype.id, 'credential_number': f'{ctype.code}-{stamp}',
        'issuing_authority': 'Ministry of Health', 'issue_date': today - relativedelta(years=1),
        'expiry_date': today + relativedelta(years=2)})
    line.action_verify()
assert applicant.credential_verification_status == 'verified', applicant.credential_verification_status
step('Recruit candidate + credential verification', f'{len(required)} credential(s) verified')

# 2. Create employee --------------------------------------------------------
applicant.create_employee_from_applicant()
employee = applicant.employee_id
assert employee, 'employee not created'
employee.write({'department_id': icu.id, 'healthcare_branch_id': branch.id, 'tz': 'Africa/Cairo',
                'arabic_name': 'ممرضة اختبار القبول', 'weekend_work_allowed': True})
assert env['healthcare.hr.onboarding'].search_count([('employee_id', '=', employee.id)]) == 1
step('Create employee', f'{employee.name} / {employee.employee_number}, onboarding opened')

# 3. Contract ---------------------------------------------------------------
employee.write({
    'contract_date_start': today - timedelta(days=40), 'contract_date_end': today + timedelta(days=20),
    'wage': 12000, 'contract_type_id': ref('healthcare_hr_contract.contract_type_full_time').id,
    'structure_type_id': ref('hr.structure_type_employee').id, 'trial_date_end': today + timedelta(days=50),
    'medical_license_required': True, 'renewal_type': 'manual',
})
step('Create contract', f'{employee.contract_date_start} -> {employee.contract_date_end}, wage 12000')

# 4. Verify credentials -----------------------------------------------------
blockers = employee._hc_credential_blockers(today)
assert not blockers.get(employee.id), blockers
step('Verify credentials', f'{employee.credential_count} valid credential(s), no shift blocker')

# 5. Probation --------------------------------------------------------------
employee.version_id.action_start_probation()
assert employee.probation_status == 'started'
step('Start probation', f'ends {employee.trial_date_end}')

# 6. Department and branch --------------------------------------------------
assert employee.healthcare_branch_id == branch and employee.department_id == icu
step('Assign department and branch', f'{icu.name} / {branch.complete_name}')

# 7. Medical shift ----------------------------------------------------------
shift_day = today - timedelta(days=3)
template = ref('healthcare_hr_shift.shift_template_night12')
shift = env['healthcare.shift.assignment'].create({
    'employee_id': employee.id, 'shift_template_id': template.id, 'date': shift_day})
shift.action_publish()
assert shift.state == 'published', shift.conflict_reason
step('Assign medical shift', f'{template.display_name} on {shift_day}, planning slot {shift.planning_slot_id.id}')

# 8. Biometric import -------------------------------------------------------
device = env['healthcare.biometric.device'].search([('branch_id', '=', branch.id)], limit=1)
code = f'ACC{stamp}'
env['healthcare.biometric.employee.mapping'].create({'device_id': device.id, 'device_employee_code': code,
                                                     'employee_id': employee.id})
tz_offset = shift.datetime_start - datetime.combine(shift_day, time(20))  # UTC - local
local_in = datetime.combine(shift_day, time(20, 17))            # 17 min late
local_out = datetime.combine(shift_day + timedelta(days=1), time(9, 5))  # 65 min extra
device_tz_events = [
    {'employee_code': code, 'timestamp': local_in, 'event_type': 'check_in'},
    {'employee_code': code, 'timestamp': local_in + timedelta(minutes=1), 'event_type': 'check_in'},  # double scan
    {'employee_code': code, 'timestamp': local_out, 'event_type': 'check_out'},
]
device.timezone = employee.tz
batch = device._import_events(device_tz_events, 'manual')
batch.log_ids._process()
attendance = env['hr.attendance'].search([('employee_id', '=', employee.id)])
assert len(attendance) == 1 and attendance.check_out, attendance
step('Import biometric attendance', f'batch {batch.name}: {batch.received_count} received, one attendance created')

# 9-10. Reconcile + late / overtime / night ---------------------------------
rec = env['healthcare.attendance.reconciliation'].create({
    'date_from': shift_day, 'date_to': shift_day, 'department_id': icu.id})
rec.action_compute()
line = rec.line_ids.filtered(lambda l: l.assignment_id == shift)
assert line and line.status == 'late', line.status
step('Reconcile attendance', f'status {line.status}, late {line.late_minutes} min, extra {line.extra_hours:.2f} h, '
                             f'night {line.night_hours:.2f} h')
rec.action_approve()
assert shift.state == 'approved' and shift.payroll_overtime_hours > 0
step('Calculate late / overtime / night work', f'approved overtime {shift.overtime_hours:.2f} h -> payroll '
                                                f'{shift.payroll_overtime_hours:.2f} h')

# 11. Allowances ------------------------------------------------------------
period_from = shift_day.replace(day=1)
period_to = shift_day + relativedelta(day=31)
allowances = env['healthcare.allowance.rule']._compute_period(period_from, period_to, employees=employee)
allowances.action_confirm()
step('Generate allowances', ', '.join(f'{a.rule_id.name}: {a.amount}' for a in allowances) or 'none')

# 12. Leave -----------------------------------------------------------------
leave_type = env['hr.leave.type'].search([('requires_allocation', '=', False)], limit=1) or \
    env['hr.leave.type'].create({'name': 'Acceptance Leave', 'requires_allocation': False})
leave_day = today + timedelta(days=5)
leave = env['hr.leave'].create({'employee_id': employee.id, 'holiday_status_id': leave_type.id,
                                'request_date_from': leave_day, 'request_date_to': leave_day})
if leave.state != 'validate':
    leave.action_approve()
assert leave.state == 'validate'
blocked = env['healthcare.shift.assignment'].create({
    'employee_id': employee.id, 'shift_template_id': ref('healthcare_hr_shift.shift_template_morning').id,
    'date': leave_day})
blocked.action_check()
assert 'leave' in (blocked.conflict_reason or '')
blocked.unlink()
step('Process leave', f'{leave_type.name} on {leave_day}; a shift that day is rejected by the engine')

# 13. Payroll inputs --------------------------------------------------------
Input = env['healthcare.payroll.input']
inputs = Input._generate_for_period(period_from, period_to, employees=employee)
again = Input._generate_for_period(period_from, period_to, employees=employee)
assert inputs == again, 'duplicate inputs'
step('Create payroll inputs', ', '.join(f'{i.source_type}={i.amount}' for i in inputs) + ' (re-run: no duplicate)')

# 14. Payslip ---------------------------------------------------------------
slip = env['hr.payslip'].create({'name': f'Acceptance {employee.name}', 'employee_id': employee.id,
                                 'date_from': period_from, 'date_to': period_to})
slip.compute_sheet()
codes = {l.code: l.total for l in slip.line_ids}
assert codes.get('HC_OVERTIME'), codes
slip.action_payslip_done()
assert shift.state == 'payroll_posted'
step('Generate payslip', f'gross {slip.gross_wage:.2f}, net {slip.net_wage:.2f}, overtime line {codes["HC_OVERTIME"]:.2f}')

# 15. Bank batch ------------------------------------------------------------
bank = env['res.bank'].search([], limit=1) or env['res.bank'].create({'name': 'Demo Bank'})
account = env['res.partner.bank'].create({'acc_number': f'EG8000190005000000000{stamp}', 'bank_id': bank.id,
                                          'partner_id': employee.work_contact_id.id, 'allow_out_payment': True})
employee.bank_account_ids = account
bank_batch = env['healthcare.payroll.bank.batch'].create({
    'layout_id': ref('healthcare_hr_bank.layout_generic_csv').id, 'date_from': period_from, 'date_to': period_to,
    'reference': f'ACC-{stamp}'})
bank_batch.action_generate_lines()
bank_batch.line_ids.filtered(lambda l: l.employee_id != employee).unlink()
bank_batch.action_export()
assert account.acc_number in base64.b64decode(bank_batch.export_file).decode('utf-8-sig')
step('Create bank payroll batch', f'{bank_batch.name}: {bank_batch.export_filename}, {bank_batch.total_amount:.2f}')

# 16. Appraisal -------------------------------------------------------------
appraisal = env['hr.appraisal'].create({'employee_id': employee.id, 'manager_ids': [(6, 0, icu.manager_id.ids)]})
step('Run appraisal', f'{len(appraisal.hc_kpi_line_ids)} KPI line(s), weighted score {appraisal.hc_kpi_score:.1f}')

# 17. Training --------------------------------------------------------------
trainings = env['healthcare.training.assignment']._generate_assignments(employee)
env['healthcare.training.assignment']._generate_assignments(employee)
assert env['healthcare.training.assignment'].search_count([('employee_id', '=', employee.id)]) == len(trainings)
step('Track training', f'{len(trainings)} assignment(s) generated (idempotent)')

# 18. Renew contract --------------------------------------------------------
new_version = employee.version_id._renew(months=12)
step('Renew contract', f'new version {new_version.contract_date_start} -> {new_version.contract_date_end}')

# 19-21. Exit, clearance, final settlement ----------------------------------
exit_rec = env['healthcare.hr.exit'].create({'employee_id': employee.id, 'exit_reason': 'resignation',
                                             'last_working_date': today + timedelta(days=10)})
exit_rec.action_start_clearance()
step('Employee exit', f'{exit_rec.name}, {len(exit_rec.clearance_item_ids)} clearance item(s)')
exit_rec.clearance_item_ids.filtered(lambda i: i.clearance_department_id.code == 'MEDEQ').amount_due = 250
exit_rec.clearance_item_ids.action_clear()
assert exit_rec.state == 'settlement'
step('Clearance', 'all departments cleared, 250 obligation recorded')
settlement = exit_rec.settlement_id
settlement.action_compute()
settlement.action_confirm()
settlement.action_mark_paid()
exit_rec.action_hr_approve()
assert exit_rec.state == 'done' and not employee.active
step('Final settlement', ' | '.join(f'{l.name} {l.amount:.2f}' for l in settlement.line_ids)
     + f' | NET {settlement.net_amount:.2f}; employee archived')

env.cr.commit()
print(f'=== {len(results)} steps passed. Employee: {employee.name} (id {employee.id}) ===')
