# Changelog

All notable changes to the Healthcare HR Management Suite are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow Odoo's
`<odoo version>.<major>.<minor>.<patch>` scheme.

## [19.0.1.0.0] - 2026-09-24

First release for Odoo 19 (Community + Enterprise): 15 functional modules and the
`healthcare_hr_suite` meta module.

### Added

**healthcare_hr_core**
- Facility / branch hierarchy (`healthcare.hr.branch`, hospital, clinic, medical centre, branch) and
  units inside departments.
- Healthcare employee data: employee number (sequence `EMP-`, unique per company), Arabic name, hire
  date, healthcare category, clinical flag, employment status, branch, unit, medical department,
  specialty and sub-specialty (22 specialties shipped), professional registration number.
- Practitioner bridge to external clinical systems (`healthcare.employee.practitioner.link`) with a
  lookup service.
- Onboarding checklist with 13 configurable items.
- Security: 15 groups (14 grouped in Odoo 19 privileges, plus Employee Self Service implied by every
  internal user), allowed branches per user, branch and multi-company record
  rules, idempotent alert service (`healthcare.hr.alert`).
- Settings: probation, contract, credential and training alert thresholds, default alert responsible.

**healthcare_hr_contract**
- Nine healthcare contract types (Full-Time, Part-Time, Hourly, Locum Doctor, Visiting Doctor,
  Consultant, Trainee, Intern, Outsourced).
- Probation workflow on `hr.version` and probation reviews (scores, recommendation); a review never
  terminates an employee.
- Renewal policy (manual, automatic, non-renewable), renewal wizard creating a new employee version,
  licence and insurance flags.
- Daily probation and contract expiry alerts; automatic renewal of expired automatic contracts.

**healthcare_hr_credentials**
- 12 credential types (Medical License, Professional Classification, BLS, ACLS, PALS, Radiation
  Safety, Infection Control, Work Permit, Residency Permit, Passport, Malpractice Insurance, Specialty
  Registration) with mandatory, clinical-only, job scope, blocking and confidential flags.
- Credentials with verification, stored status (valid, expiring, expired, missing, under
  verification), re-verification on number or expiry change, attachments.
- Daily status refresh and alerts at configurable thresholds; missing-credential placeholders.
- Credential blocker service used by the shift engine.

**healthcare_hr_shift**
- Seven shift templates (Morning, Evening, Night, 12 Hour Day, 12 Hour Night, 24 Hour, On Call) with
  midnight crossing, breaks, grace, rest rules, allowed jobs and branch restriction.
- Shift assignments computed in the employee timezone and stored in UTC, with planned, night, weekend
  and holiday hours and a 9-state workflow; approved and payroll-posted shifts are locked.
- Batch validation engine (14 checks) with stored conflict reasons and a logged "Publish Anyway"
  override for scheduling managers.
- Coverage rules, daily coverage snapshots and shortage alerts, publication wizard with optional
  blocking, shift generation wizard.
- Shift swap workflow (request, colleague, manager, scheduling) with re-validation at every step.
- On-call duties with standby and call-in hours.
- Published shifts mirrored as Planning slots; approved leave after publication flags shifts as
  conflicts.
- Settings: night window, maximum weekly hours, maximum continuous shift, default rest, attendance
  matching window.

**healthcare_hr_attendance**
- Attendance matched to planned shifts (cross-midnight aware), late and early minutes, extra time vs
  shift, night/weekend/holiday hours and status.
- Reconciliation batches turning shifts, attendance, leave, public holidays and the overtime policy
  into approved work data, with editable approved overtime and payroll overtime rounding.
- Daily reconciliation of yesterday (never approves) and missing-checkout alerts every 4 hours.
- Settings: overtime threshold, payroll rounding, automatic proposal, missing-checkout delay.

**healthcare_hr_biometric**
- Devices for ZKTeco, Suprema, Hikvision, Anviz or generic middleware with push, pull, CSV import or
  SDK connection, device timezone and hashed push token.
- Authenticated push endpoint `POST /healthcare/biometric/push` (payload validation, size limits).
- Raw logs deduplicated per device, employee code and timestamp; sync batches with counters and error
  log; chronological processing into attendance; retry with a limit.
- Device-specific and company-wide employee mappings; CSV import wizard; generic JSON pull adapter.
- Crons: process punches every 10 minutes (5,000 per run), pull devices every 15 minutes.

**healthcare_hr_allowance**
- 16 allowance types and a rule engine: fixed, per shift, per hour, percentage of basic, percentage of
  gross, formula; minimum and maximum; filters by dates, category, department, branch, unit, job,
  contract type, shift type and templates.
- Idempotent allowance results computed from approved shifts and approved on-call duties only.

**healthcare_hr_payroll**
- Payroll inputs with a unique processing key per source (allowance, overtime, loan installment,
  manual), generation wizard and optional daily cron (inactive by default).
- Ten payslip input types (`HC_NIGHT`, `HC_WEEKEND`, `HC_HOLIDAY`, `HC_ONCALL`, `HC_ALW`,
  `HC_OVERTIME`, `HC_BONUS`, `HC_DED`, `HC_LOAN`, `HC_ADVANCE`).
- Inputs injected as payslip Other Inputs; sources marked processed on validation and released on
  cancellation.
- "Add Healthcare Input Rules" button on salary structures, run automatically on Regular Pay.
- Overtime pay from payroll overtime hours, hourly rate and company overtime rate; payroll reports by
  branch and department.

**healthcare_hr_loan**
- Loans and salary advances (at most 3 installments) with approval workflow, installment schedule,
  deduction through payroll inputs, postponement and early settlement.

**healthcare_hr_bank**
- Bank batches from validated payslips by period, pay run and branch; missing or untrusted accounts
  flagged.
- Configurable layouts (CSV, fixed-width TXT, XLSX) with three shipped examples; API extension point.

**healthcare_hr_clearance**
- Exit workflow (initiated, clearance, final settlement, HR approval, archived) with seven clearance
  departments and obligation amounts.
- Final settlement with 11 configurable components (formula-based end of service) and a PDF report.
- HR approval ends the contract, cancels future shifts and archives the employee.

**healthcare_hr_dashboard**
- Dashboard with headcount, attendance, workforce, compliance and payroll tiles, branch filter and
  drill-down; payroll tiles for payroll officers only.

**healthcare_hr_training**
- Training requirement matrix, idempotent assignment generation skipping compliant employees,
  completion creating or renewing the credential, waivers, expiry cron and alerts.
- Reports: Missing Training, Expiring Certifications, Training Compliance (SQL view).

**healthcare_hr_appraisal**
- KPI templates for doctors, nurses and administrative staff; KPI lines on standard appraisals with
  computed attendance rate, late rate and training compliance; weighted score with no effect on
  contracts.

**healthcare_hr_recruitment**
- Applicant healthcare data, applicant credential lines with verification, "Credential Verification"
  stage, hiring gate, and handover of credentials and onboarding to the new employee.

**healthcare_hr_suite**
- Meta module installing all modules.

**Cross-cutting**
- 25 reports under Healthcare HR > Reports (list, pivot and graph views).
- Arabic translations (`ar.po`) for all 15 functional modules; `.pot` templates for all.
- Demo data: Hospital A with two branches, seven departments, 11 employees with contracts and
  credentials, a published two-week roster, attendance, reconciliation, allowances, payroll inputs,
  draft payslips, a loan and an advance, biometric devices and logs, training, appraisals and
  applicants.
- 148 automated tests.

### Design decisions

- Contracts extend `hr.version`, because `hr.contract` does not exist in Odoo 19; contract dates are
  read with sudo, never written, outside the contract module.
- Recruitment extends `hr.applicant`, because `hr.candidate` does not exist in Odoo 19.
- Shift worked time is computed from raw check-in/out minus the template break, because the standard
  `worked_hours` deducts the working-schedule lunch break.
- The shift-based extra time is named `extra_time_hours` (attendance) and `extra_hours` (shift) because
  `overtime_hours` already exists on attendance.
- Recruitment and appraisal are separate modules to keep `hr_recruitment` and `hr_appraisal` optional;
  onboarding and the practitioner bridge live in core; leave reuses the standard Time Off menus.

### Known limitations

- End-of-service formula ships as 0 and must be configured per labour law.
- Only the generic JSON biometric pull adapter is implemented.
- Bank API sending is an extension point; file export works.
- Salary is paid to the employee's primary bank account only.
- "Open shifts" on the dashboard are draft shifts; there is no unassigned-shift model.
- The PDF indexation warning about `pdfminer.six` in the log is unrelated to the suite.
