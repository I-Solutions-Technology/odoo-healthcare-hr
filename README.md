# Healthcare HR Management Suite for Odoo 19

> Hospital and clinic HR on standard Odoo 19: medical rosters with a validation engine, biometric
> attendance, reconciliation, healthcare allowances, payroll inputs, credentials, training,
> recruitment, appraisal, loans, exit and bank payroll, in 16 modules.

Version `19.0.1.0.0` · License LGPL-3 · Author iSolutions Technology · Requires Odoo 19 Community +
Enterprise

## Why this exists

Hospitals run 24/7 on 8-, 12- and 24-hour shifts, and a nurse with an expired BLS or an unverified
license must not be on the roster. Pay depends on what was actually worked: nights, weekends, holidays,
on-call and approved overtime, not on the planned schedule. Standard Odoo HR manages employees, leave,
attendance and payroll well but knows nothing about shifts that cross midnight, clinical credentials
or healthcare allowances. This suite adds that healthcare layer **on top of** standard Odoo 19 without
forking or replacing its engines.

## Quick start

The instance lives in `/Users/jamalswilam/Desktop/Odoo19 Healthcare HR` and already has the database
`healthcare_hr` with demo data.

```bash
cd "/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
scripts/run.sh
```

Open http://127.0.0.1:8095, log in with `admin` / `admin` and open the **Healthcare HR** app. Start
with **Dashboard > Overview**, then follow the
[acceptance scenario walkthrough](docs/USER_GUIDE.md#10-acceptance-scenario-walkthrough).

| Instance fact | Value |
|---|---|
| Odoo source (shared, read-only) | `~/Desktop/odoo19` and its `.venv` |
| Enterprise addons | `~/Downloads/enterprise-19.0` |
| HTTP / gevent port | 8095 / 8096 (bound to 127.0.0.1) |
| Database | `healthcare_hr` (demo data, `admin`/`admin`, Arabic `ar_001` loaded) |
| PostgreSQL role | `odoo19_user` |
| Custom code | `custom_addons/healthcare_hr_*` only |

Scripts:

| Script | Purpose |
|---|---|
| `scripts/run.sh [odoo-bin args]` | Start the server |
| `scripts/upgrade.sh <modules> [-i]` | Upgrade (default) or install modules on `healthcare_hr`, then stop |
| `scripts/test.sh <modules> [db]` | Run module tests on a throw-away database (default `healthcare_hr_test`, dropped and recreated) |

New database, upgrades and troubleshooting: [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Modules

| Module | What it adds | Depends on |
|---|---|---|
| `healthcare_hr_core` | Facility/branch hierarchy, units, specialties, healthcare employee data, practitioner bridge, onboarding checklist, security groups, branch record rules, alert service | hr, mail |
| `healthcare_hr_contract` | Contract types, probation workflow and reviews, renewal policy, expiry alerts on Odoo 19 `hr.version` | core |
| `healthcare_hr_credentials` | Licenses, certifications, permits, insurance; verification, status, alerts, shift blocking | contract |
| `healthcare_hr_shift` | Shift templates, assignments, validation engine, coverage rules, swaps, on-call, Planning mirror | credentials, hr_holidays, planning |
| `healthcare_hr_attendance` | Attendance matched to shifts, late/early/extra/night/weekend/holiday hours, reconciliation to approved work data | shift, hr_attendance |
| `healthcare_hr_biometric` | Devices (push, pull, CSV, SDK), raw logs, idempotent sync batches, conversion to attendance | attendance |
| `healthcare_hr_allowance` | Allowance types and rule engine computed from approved work data | attendance |
| `healthcare_hr_payroll` | Idempotent payroll inputs injected into standard payslips; salary rules per input | allowance, hr_payroll |
| `healthcare_hr_loan` | Loans and salary advances with installments deducted through payroll | payroll |
| `healthcare_hr_bank` | Salary transfer batches with configurable CSV / TXT / XLSX layouts | payroll |
| `healthcare_hr_clearance` | Exit workflow, department clearance, configurable final settlement | loan |
| `healthcare_hr_dashboard` | KPI dashboard with drill-down, by branch | clearance |
| `healthcare_hr_training` | Training requirement matrix, assignments that renew credentials, compliance | credentials |
| `healthcare_hr_appraisal` | Healthcare KPI templates and computed KPIs on standard appraisals | attendance, hr_appraisal |
| `healthcare_hr_recruitment` | Applicant healthcare data, credential verification gate, handover to employee | credentials, hr_recruitment |
| `healthcare_hr_suite` | Meta module installing all of the above | all 15 modules |

Every module installs on its own with its dependencies. Dependency graph, models and security matrix:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## How it works

```text
Shift + Attendance + Leave + Public holidays + Overtime policy
        -> Reconciliation -> Approved work data
        -> Allowances -> Payroll inputs -> Payslip -> Accounting -> Bank batch
```

- **Validation before publication.** Every shift is checked for archived employee, contract, approved
  leave, blocking credentials, allowed jobs, template branch, weekend and 24-hour authorisation, maximum
  shift length, duplicates, overlaps, another branch at the same time, minimum rest and weekly hours.
  Conflicts are stored with their reasons; a scheduling manager can publish anyway with a logged reason.
- **Three overtime figures.** Worked extra time is not approved overtime, which is not payroll
  overtime (approved, then rounded down per the company setting). Nothing is paid automatically.
- **Only approved data is paid.** Only approved shifts, approved on-call duties and confirmed allowances
  produce payroll inputs. Each input has a unique processing key (`allowance:<id>`, `overtime:<shift
  id>`, `loan_installment:<id>`, `manual:<seq>`), so re-running never duplicates. Validating a payslip
  marks the sources processed and the shifts *Payroll Posted*; cancelling releases them.
- **Standard engines.** Payroll computes the payslip; the suite only feeds standard "Other Inputs" and
  adds one salary rule per input type with a button (automatic on *Regular Pay*). Leave is standard
  Time Off. Published shifts appear in Planning.
- **Security by branch.** Users see the branches listed on their user (empty = all; a facility includes
  its branches). Department managers see their teams, employees their own records. Payroll, allowance,
  loan and bank data are closed to department managers and employees.

## Documentation

| Document | For | Content |
|---|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Administrators | Prerequisites, new database, start, upgrade, tests, languages, troubleshooting |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Consultants | Step-by-step setup from working schedule to biometric devices |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | End users | Work per role, menu paths, the 21-step acceptance walkthrough |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Developers | Implementation analysis (standard reuse, models, fields, dependency graph, workflows, security matrix, risks), data flow, crons |
| [docs/TEST_PLAN.md](docs/TEST_PLAN.md) | QA | Running the tests, test matrix, manual UAT checklist |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Everyone | Release notes |

## Quality

- 148 automated tests, 0 failures, with all modules installed together.
- Upgrading all modules on the demo database is clean and idempotent.
- Crons are idempotent and alerts are never duplicated while open.

## Known limitations and next steps

| Item | Current state | Next step |
|---|---|---|
| End-of-service benefit | The *End of Service* settlement component ships with `result = 0` | Configure the formula per the applicable labour law ([CONFIGURATION.md](docs/CONFIGURATION.md#settlement-components)) |
| Biometric pull adapters | Only the generic JSON adapter is implemented; ZKTeco, Suprema, Hikvision and Anviz raise a clear "not implemented" message | Use push or generic JSON middleware, or implement `_pull_events_<vendor>` |
| Bank API sending | File export works (CSV, TXT, XLSX); sending through an API is an extension point (`_send_<provider>`) | Build a connector module per bank |
| Salary split across bank accounts | The batch pays the net salary to the employee's primary bank account only | Add split rules if needed |
| Open shifts | The dashboard's "open shifts" tile counts draft shifts; there is no unassigned-shift model | Add an open-shift pool if required |
| Payroll input cron | Daily generation of payroll inputs ships inactive | Enable it in Scheduled Actions if wanted |
| Network exposure | The instance listens on 127.0.0.1; the biometric push endpoint is not reachable by devices as is | Put a reverse proxy with HTTPS in front before connecting devices |
| PDF indexation warning (`pdfminer.six`) | Appears in the log | Unrelated to the suite |

## License

LGPL-3. © iSolutions Technology.
