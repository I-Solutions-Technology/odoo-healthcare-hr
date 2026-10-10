# Configuration

This guide takes you through setting up the suite for a hospital or clinic group, in the order a
consultant would do it. Each step builds on the previous one: the working schedule defines weekends
before shifts are validated, credential types exist before shifts are blocked, and payroll rules exist
before inputs reach payslips.

You need the **System Administrator** or **Healthcare HR Manager** group (and **Payroll Manager** for
steps 8 to 10). All paths start from the **Healthcare HR** app unless stated otherwise.

| Step | What you configure | Where |
|---|---|---|
| 1 | Company working schedule (weekend days) | Employees app / Settings |
| 2 | Public holidays | Time Off > Configuration > Public Holidays |
| 3 | Healthcare HR settings | Healthcare HR > Configuration > Settings |
| 4 | Facilities, branches, departments, units, jobs | Healthcare HR > Configuration > Organisation |
| 5 | Users: groups and branch access | Settings > Users & Companies > Users |
| 6 | Credential types | Healthcare HR > Configuration > Credential Types |
| 7 | Shift templates and coverage rules | Healthcare HR > Configuration > Shift Templates / Coverage Rules |
| 8 | Allowance types and rules | Healthcare HR > Configuration > Allowance Types / Allowance Rules |
| 9 | Payroll structure rules | Payroll app > Configuration > Structures |
| 10 | Bank file layouts | Healthcare HR > Configuration > Bank File Layouts |
| 11 | Clearance departments and settlement components | Healthcare HR > Configuration |
| 12 | Training requirements and appraisal KPI templates | Healthcare HR > Configuration |
| 13 | Biometric devices, mappings and push token | Healthcare HR > Configuration > Biometric |
| 14 | Scheduled actions | Settings > Technical > Scheduled Actions |

---

## 1. Company working schedule (weekend days)

The suite does not have its own weekend setting. **A weekday is a weekend day when the company working
schedule has no working hours on it.** The validation engine (weekend authorisation), the weekend
hours on shifts and attendances, and the weekend allowances all read it.

1. Open the working schedule used as the company's default working hours (Employees app >
   Configuration > Working Schedules).
2. Keep attendance lines only on the working days. For a Sunday to Thursday week, remove the Friday and
   Saturday lines.
3. Save. **Settings > Healthcare HR > Scheduling Rules > Weekend days** reminds you of this rule.

If the company has no working schedule, Saturday and Sunday are used.

The working schedule also gives the default hourly rate for overtime when *Monthly hours* is empty
(step 3): weekly hours x 52 / 12.

## 2. Public holidays as company calendar leaves

Public holiday hours on shifts and attendances come from **company-wide calendar leaves**: leaves with
no resource (employee), for your company or all companies, and either no working schedule or the
company schedule.

1. Go to **Time Off > Configuration > Public Holidays**.
2. Create one line per holiday with its start and end date-time. Leave the employee/resource empty.
3. Set the working schedule to the company schedule or leave it empty.

Holiday hours feed the *Public Holiday Hours* basis of allowance rules and the holiday allowance.

## 3. Healthcare HR settings

Go to **Healthcare HR > Configuration > Settings** (or **Settings > Healthcare HR**). Values are per
company.

### Alerts

| Setting | Default | Effect |
|---|---|---|
| Probation alerts | `30,14,7` | Days before the probation end at which a review activity is raised; reaching the largest threshold sets the probation to *Review Due* |
| Contract expiry alert | 60 | Days before the contract end at which a renewal activity is raised (a contract can override it) |
| Credential alerts | `90,60,30,7` | Reminder thresholds before a credential expires. A credential type's *Default Alert Days* becomes its first reminder; company thresholds below it still apply |
| Training alerts | 30 | Days before a completed training expires at which an alert is raised; also the window used to decide whether a new training assignment is needed |
| Default alert responsible | (empty) | Receives alerts when the employee has no HR responsible. Fallback order: employee's HR responsible, this user, the employee's manager, the administrator |

### Scheduling Rules

| Setting | Default | Effect |
|---|---|---|
| Night window | 22:00 to 06:00 | Local hours counted as night hours on shifts and attendances |
| Maximum weekly hours | 60 | Validation limit per employee and ISO week (0 = no limit). An employee's *Max Weekly Hours* overrides it |
| Maximum continuous shift (h) | 24 | Longer shifts are rejected |
| Default minimum rest (h) | 8 | Used when a shift template has no minimum rest |
| Attendance matching window (h) | 3 | A check-in up to this many hours before a shift start is matched to that shift |

### Attendance & Overtime Policy

| Setting | Default | Effect |
|---|---|---|
| Overtime threshold (min) | 30 | Worked extra time below this is not proposed as overtime |
| Payroll overtime rounding (min) | 15 | Approved overtime is rounded **down** to this step for payroll (0 = no rounding) |
| Propose overtime automatically | On | Pre-fills approved overtime with the extra time on templates that allow overtime; the approver can change it |
| Missing checkout after (h) | 2 | Hours after the planned shift end (16 h after check-in when unplanned) after which an open attendance is flagged *Missing Checkout* |

### Payroll

| Setting | Default | Effect |
|---|---|---|
| Overtime rate | 1.25 | Multiplier applied to the hourly wage for payroll overtime |
| Monthly hours | (empty) | Hourly rate = wage / monthly hours. Empty = weekly schedule hours x 52 / 12 |

## 4. Facilities, branches, departments and units

Go to **Healthcare HR > Configuration > Organisation**.

1. **Facilities & Branches.** Create the facility first (type *Hospital*, *Clinic* or *Medical Center*,
   no parent), then its branches with the facility as *Parent Facility*. The code must be unique per
   company; it appears on schedules, exports and biometric devices. Set the *Manager* so shortage
   alerts reach them.
2. **Departments.** On each department set *Branch* and *Healthcare Type* (clinical, nursing,
   diagnostic, pharmacy, support, administrative) and the department manager. Employees created in a
   department inherit its branch.
3. **Units.** Create units inside departments (ICU Bay A, ER Triage ...). The code is unique per branch.
4. **Job Positions.** Set *Healthcare Category* (doctor, nurse, pharmacist, lab technician ...) so new
   employees get the right category, and tick *Medical License Required* where applicable.
5. **Medical Specialties.** 22 specialties ship; add sub-specialties under their parent.
6. **Onboarding Items.** 13 checklist items ship (Employee Record, Contract Signed, ID Documents,
   Professional License Verified, Credentials Verified, Department Assigned, Branch Assigned, Shift
   Eligibility, Biometric Enrollment, System Access, Training Assigned, Payroll Bank Information,
   Probation Started). Mark items *Mandatory* or *Clinical only* as needed.

Example structure (the demo):

```text
Hospital A (hospital)
├── Branch 1: ER (ER Triage), ICU (ICU Bay A), Radiology (X-Ray), Laboratory, Pharmacy
└── Branch 2: Outpatient (OPD Clinics)
Administration department attached to Hospital A
```

## 5. Users: groups and branch access

Go to **Settings > Users & Companies > Users** and open each user.

1. In the access rights, choose a level for each Healthcare HR privilege:

   | Privilege | Levels |
   |---|---|
   | Healthcare HR | Healthcare HR User, Officer, Manager |
   | Healthcare Attendance | Attendance Officer, Attendance Manager |
   | Workforce Scheduling | Scheduling Officer, Scheduling Manager |
   | Healthcare Payroll | Payroll Officer, Payroll Manager |
   | Healthcare Talent | Training Officer, Recruitment Officer |
   | Healthcare Management | Department Manager, Hospital Director, System Administrator |

   Every internal user is automatically *Employee Self Service*. See the full matrix in
   [ARCHITECTURE.md](ARCHITECTURE.md#7-security-matrix).

2. On the **Healthcare Branches** tab, list the branches the user may work on. **Empty means every
   branch.** Selecting a facility grants all of its branches. HR Managers and Hospital Directors
   always see every branch.

3. Link each employee to their user (employee form, *Related User*) so self-service rules (own shifts,
   credentials, training, loans) work, and so department managers are recognised through the
   department's manager.

## 6. Credential types

Go to **Healthcare HR > Configuration > Credential Types**. 12 types ship:

| Type | Category | Mandatory | Blocks shifts | Clinical only | First alert (days) | Confidential |
|---|---|---|---|---|---|---|
| Medical License | License | Yes | Yes | Yes | 90 | No |
| Professional Classification | Registration | Yes | Yes | Yes | 90 | No |
| BLS | Certification | Yes | Yes | Yes | 60 | No |
| ACLS | Certification | No | No | Yes | 60 | No |
| PALS | Certification | No | No | Yes | 60 | No |
| Radiation Safety | Certification | No | No | Yes | 60 | No |
| Infection Control | Certification | No | Yes | Yes | 30 | No |
| Work Permit | Permit | No | No | No | 90 | Yes |
| Residency Permit | Permit | No | No | No | 90 | Yes |
| Passport | Identity | No | No | No | 180 | Yes |
| Malpractice Insurance | Insurance | No | No | Yes | 60 | Yes |
| Specialty Registration | Registration | No | No | Yes | 90 | No |

How the flags work:

- **Mandatory**: required for the employees in scope. Scope = *Clinical only* (doctors, nurses,
  pharmacists, technicians) and/or *Required for Jobs* (empty = everybody in scope). Missing mandatory
  credentials raise alerts. To create *Missing* placeholders, select employees in a list and use
  **Actions > Generate missing mandatory credentials** (HR Officer); it never creates duplicates.
- **Blocks shift assignment**: the validation engine refuses to publish a shift when the employee has
  no valid credential of the type on the shift date. **The block applies only when the type is also
  Mandatory** (so the shipped *Infection Control* type does not block until you make it mandatory).
- **Valid for shifts** means: verified, with a number or a document, and not expired on the shift date.
- **Confidential**: hidden from non-officers, department managers included.
- **Default Alert Days**: first reminder before expiry (empty = company thresholds).

## 7. Shift templates and coverage rules

### Shift templates

Go to **Healthcare HR > Configuration > Shift Templates** (Scheduling Manager). Seven templates ship,
shared by all companies:

| Template | Code | Type | Time | Break | Minimum rest after |
|---|---|---|---|---|---|
| Morning | MOR | Morning | 08:00-16:00 | 30 min | 8 h |
| Evening | EVE | Evening | 16:00-24:00 | 30 min | 8 h |
| Night | NGT | Night | 00:00-08:00 | 30 min | 11 h |
| 12 Hour Day | D12 | 12 Hours | 08:00-20:00 | 60 min | 11 h |
| 12 Hour Night | N12 | 12 Hours | 20:00-08:00 (next day) | 60 min | 11 h |
| 24 Hour | H24 | 24 Hours | 08:00-08:00 (next day) | 120 min | 24 h |
| On Call (Night) | ONC | On Call | 20:00-08:00 (next day) | 0 | 0 |

Field reference:

- **Start / end time**: local time. An end before the start ends the next day; for 24 hours use the
  same time as the start.
- **Break (min)**: unpaid; deducted from planned hours and from worked time.
- **Grace (min)**: default 10; tolerance before a check-in counts as late or a check-out as early.
- **Minimum rest (h)**: rest required after this shift.
- **Overtime allowed**: extra time on this template may be proposed as overtime.
- **Allowed Jobs**: only these positions can take the shift (empty = all).
- **Branch**: restricts the template to a branch and its sub-branches.
- **Weekend / public holiday shift**: informative flags for dedicated templates.

Employee-level authorisations are on the employee form, **Healthcare** tab, *Scheduling* group:
*24-hour Shifts Allowed* (off by default), *Weekend Work Allowed* (on by default) and *Max Weekly Hours*.

### Coverage rules

Go to **Healthcare HR > Configuration > Coverage Rules**. A rule sets the minimum (and optional
preferred) number of staff for a department and shift template, optionally narrowed by branch, unit,
healthcare category, job, weekdays (`0`=Monday ... `6`=Sunday, comma separated) and effective dates.

Tick **Block publication** to make the **Publish Roster** wizard refuse a period with a shortage on
that rule. The daily coverage cron snapshots the next 14 days and alerts the department manager (or
branch manager) on shortages.

Example (demo): ICU, Branch 1, 12 Hour Night, Nurse, minimum 2, preferred 3.

## 8. Allowance types and rules

### Allowance types

**Healthcare HR > Configuration > Allowance Types** (Payroll Manager). 16 types ship: Night Shift,
Weekend, Public Holiday, Risk, Transportation, Housing, Responsibility, On Call, Call In, Remote Area,
Infection Risk, ICU, ER, Operating Room, Performance, Other. Each has a unique code, a *Taxable* flag
(informative, for localisations) and a *Payslip Input*. Night, Weekend, Public Holiday, On Call and Call
In are mapped to their own payslip inputs; the others go to *Healthcare Allowance* (`HC_ALW`) unless you
set a payslip input.

### Allowance rules

**Healthcare HR > Configuration > Allowance Rules**. Rules are computed in *Sequence* order.

| Method | Quantity x rate |
|---|---|
| Fixed Amount per Period | 1 x amount |
| Per Shift | Number of shifts matching the *Shift Basis* (every shift, shifts with night / weekend hours, shifts on public holidays, on-call duties, call-ins) x amount |
| Per Hour | Hours of the *Hour Basis* (night, weekend, public holiday, worked, planned, payroll overtime, on-call standby, on-call call-in) x amount |
| Percentage of Basic | Wage x percentage |
| Percentage of Gross | (wage + amounts of the rules computed before it) x percentage |
| Formula | Python code setting `result`; variables `employee`, `version`, `wage`, `hours` (dict), `shifts` (dict of counts), `days` |

Filters: effective dates, employee category, department, branch, unit, job, contract type, shift type,
shift templates. For per-shift and per-hour rules the department, branch and unit filters apply to the
**shift**; for the other methods they apply to the **employee**. *Minimum* and *Maximum* bound the
amount per period.

Only **approved** (or payroll-posted) shifts and **approved** on-call duties are counted.

Demo rules you can copy:

| Rule | Method | Setting |
|---|---|---|
| Night allowance | Per Hour, Night Hours | 25 per hour |
| Weekend allowance | Per Shift, Shifts with Weekend Hours | 150 per shift |
| ICU allowance | Per Shift, Every Shift, department ICU | 100 per shift, maximum 2000 |
| On-call standby | Per Hour, On-call Standby Hours | 20 per hour |
| Call-in | Per Hour, On-call Worked Hours | 80 per hour |
| Transportation | Percentage of Basic | 10 %, maximum 3000 |
| Infection risk (nurses) | Fixed, category Nurse | 500 |

Formula example:

```python
# 40 per night shift plus 0.1 % of the wage
result = shifts.get('night', 0) * 40 + wage * 0.001
```

## 9. Payroll structure rules

Healthcare items reach payslips as standard **Other Inputs**. For them to affect the net salary, the
salary structure needs one salary rule per healthcare input type.

1. Open **Payroll app > Configuration > Structures** and the structure your employees use.
2. Click **Add Healthcare Input Rules**.

The button is idempotent. It adds, for each input type below, a rule with condition "input present":
earnings in the *Allowance* category (included in gross), deductions in the *Deduction* category with
a negative amount. Taxes stay with your country localisation. It runs automatically on the standard
*Regular Pay* structure when `healthcare_hr_payroll` is installed; run it yourself for localisation
structures.

| Input code | Name | Type |
|---|---|---|
| `HC_NIGHT` | Night Allowance | Earning |
| `HC_WEEKEND` | Weekend Allowance | Earning |
| `HC_HOLIDAY` | Public Holiday Allowance | Earning |
| `HC_ONCALL` | On-call Allowance | Earning |
| `HC_ALW` | Healthcare Allowance | Earning |
| `HC_OVERTIME` | Overtime | Earning |
| `HC_BONUS` | Bonus | Earning |
| `HC_DED` | Healthcare Deduction | Deduction |
| `HC_LOAN` | Loan Installment | Deduction |
| `HC_ADVANCE` | Salary Advance Recovery | Deduction |

Also make sure each employee has a *Salary Structure Type* on the contract and the employee's bank
account is set (step 10).

## 10. Bank layouts

**Healthcare HR > Configuration > Bank File Layouts** (Payroll Manager). Three layouts ship: *Generic
CSV* (UTF-8 with BOM), *Generic Excel* and *Fixed-width TXT (example)*.

Layout options: format (CSV, fixed-width TXT, XLSX), delimiter, header row, encoding (UTF-8, UTF-8 with
BOM, Windows-1256 Arabic, ASCII), decimal places, amount without separator (1234.50 becomes 123450),
date format (Python `strftime`, e.g. `%Y%m%d`), line ending (LF or CRLF).

Columns (in sequence order): header text, field, and for TXT a width, alignment and padding character.
Available fields: Employee Number, Employee Name, Arabic Name, National ID, Bank Name, Bank BIC / SWIFT,
IBAN, Account Number, Net Salary, Currency, Reference, Payment Date, Branch Code, Constant Value.

To build your bank's layout, duplicate the closest shipped layout and adjust the columns.

Employee bank accounts: set the employee's bank account and enable **Send Money** (trusted,
`allow_out_payment`) after you verify it. Batch lines for employees without an account or with an
untrusted account are flagged as errors and block the export.

*API provider* is *File Only*; sending through a bank API needs a connector module (see
[README.md](../README.md#known-limitations-and-next-steps)).

## 11. Clearance departments and settlement components

### Clearance departments

**Healthcare HR > Configuration > Clearance Departments**. Seven ship: HR, Finance, IT, Department
(code `DEPT`), Medical Equipment, Security, Administration, each with a checklist.

- Set a *Responsible* user per department. When empty, the `DEPT` item goes to the employee's
  department manager (or direct manager), and the others to the company's default alert responsible
  (or, if none, the user who starts the clearance).
- Only *Mandatory* items must be cleared before the final settlement starts.

### Settlement components

**Healthcare HR > Configuration > Settlement Components** (Payroll Manager). Eleven ship:

| Component | Type | Computation |
|---|---|---|
| Final Salary | Earning | Prorated wage of the last month (days worked x daily wage) |
| Unused Leave | Earning | Remaining leave days x daily wage |
| Pending Overtime | Earning | Confirmed, unpaid overtime inputs |
| Pending Allowances | Earning | Confirmed, unpaid allowance inputs |
| Bonuses | Earning | Confirmed, unpaid bonus inputs |
| End of Service | Earning | **Formula, ships as `result = 0`** |
| Deductions | Deduction | Confirmed, unpaid deduction inputs |
| Outstanding Loans | Deduction | Pending installments of active loans |
| Salary Advances | Deduction | Pending installments of active advances |
| Clearance Obligations | Deduction | Obligation amounts entered on clearance items |
| Other Obligations | Deduction | Manual line |

*Daily wage basis*: 30 days, or the calendar days of the last month.

**Configure End of Service before the first exit.** No labour-law rule is hard-coded. Formula variables:
`employee`, `version`, `wage`, `daily_wage`, `service_years`, `service_days`, `exit_reason`
(`resignation`, `termination`, `retirement`, `contract_end`, `medical`, `other`),
`last_working_date`, `hire_date`, `remaining_leave_days`.

Example (15 days per year for the first five years, 30 days per year after, nothing on termination);
check it against your country's law before use:

```python
if exit_reason == 'termination':
    result = 0
else:
    result = daily_wage * 15 * min(service_years, 5) + daily_wage * 30 * max(service_years - 5, 0)
```

## 12. Training requirements and appraisal KPI templates

### Training requirements

**Healthcare HR > Configuration > Training Requirements** (Training Officer or HR Manager). Each line
says which certification (credential type) is required for which job, healthcare category and/or
department (empty criteria match everybody):

| Field | Meaning |
|---|---|
| Certification | Credential type renewed when the training is completed |
| Renewal Period (months) | Validity after completion (0 = no expiry) |
| Days to Complete | Due date of a new assignment |
| Verify Credential on Completion | Trust the training provider: the renewed credential is verified immediately; otherwise it stays *Under Verification* |
| Mandatory | Missing mandatory training raises alerts and appears in reports |

The daily training cron creates the missing assignments. Employees who already hold a valid credential
of the type (not expiring within the *Training alerts* window) are skipped.

Demo lines: Nurse - BLS (24 months), ICU Nurse - ACLS (24 months), Radiology Technician - Radiation
Safety (12 months), Lab Technician - Infection Control (12 months, auto-verify).

### Appraisal KPI templates

**Healthcare HR > Configuration > Appraisal KPI Templates**. Three templates ship: Doctors, Nurses,
Administrative. A template applies to a healthcare category and/or job positions (a job match wins).
Weights must sum to 100. Measurement per KPI: *Manual*, *Attendance Rate*, *Late Arrival Rate* (lower is
better) or *Training Compliance*.

## 13. Biometric devices and push token

Go to **Healthcare HR > Configuration > Biometric > Devices** (Attendance Manager or System
Administrator).

1. Create the device: name, **code** (unique per company; sent by the device), vendor (ZKTeco,
   Suprema, Hikvision, Anviz, Generic), branch, and **timezone of the device clock** (naive timestamps
   are read in this timezone and stored in UTC).
2. Choose the **connection type**:

   | Type | How punches arrive |
   |---|---|
   | API Push | The device or middleware posts JSON to `/healthcare/biometric/push` |
   | API Pull | The pull cron (every 15 min) or **Sync now** calls the vendor adapter. Only the *Generic* JSON adapter is implemented |
   | File Import | CSV upload through **Import File** |
   | On-premise SDK connector | A local connector writes punches through the import service |

3. **Employee Mapping** (**Healthcare HR > Configuration > Biometric > Employee Mapping**): map each
   device employee code to an employee. Leave *Device* empty for a company-wide badge code; a
   device-specific mapping always wins.

### Push devices

1. On the device form click **Generate push token** (System Administrator only). The token is shown
   once in a notification; only its SHA-256 hash is stored. Generating a new token revokes the old one.
2. Configure the device or middleware:

   ```http
   POST /healthcare/biometric/push HTTP/1.1
   Host: <odoo-host>:8095
   Content-Type: application/json
   X-Device-Code: DEV-B1-01
   X-Device-Token: <token>

   {"events": [
     {"employee_code": "1001", "timestamp": "2026-09-24 08:00:00", "event_type": "check_in"},
     {"employee_code": "1001", "timestamp": "2026-09-24 20:05:00", "event_type": "check_out"}
   ]}
   ```

   A bare JSON list of events is accepted too. `event_type` is `check_in`, `check_out` or `unknown`
   (toggle). Timestamps without offset are in the device timezone; ISO timestamps with `Z` or an offset
   are accepted. Limits: 5,000 events and 5 MB per request.

   Response: `{"status": "ok", "batch": "BIO/2026/00001", "received": 2, "created": 2, "duplicates": 0, "invalid": 0}`.
   Errors: 401 (missing headers), 403 (unknown device or bad token), 400 (invalid JSON), 413 (too large).

3. The instance listens on `127.0.0.1` only (`http_interface` in `odoo.conf`). Devices on the network
   need a reverse proxy (with HTTPS) or a changed interface.

### Pull devices (generic JSON)

Set *API URL*, *API Username* and *API Secret* (the secret is visible to System Administrators only).
The adapter calls `GET <API URL>?since=<last sync>` with basic authentication and expects a list of
events (or `{"events": [...]}`) in the push format.

### CSV import

**Healthcare HR > Attendance > Biometric > Import File**: choose the device, the delimiter (comma,
semicolon, tab) and a UTF-8 file with the header `employee_code,timestamp,event_type`
(`event_type` is optional). *Process now* converts punches into attendances immediately. Maximum
100,000 rows per file.

## 14. Scheduled actions

Check **Settings > Technical > Scheduled Actions** (developer mode) and filter on *Healthcare HR*.
Nine of the ten crons are active on installation; **Healthcare HR: generate payroll inputs (current
month)** is inactive: enable it if you want inputs regenerated daily instead of on demand. The full list
is in [ARCHITECTURE.md](ARCHITECTURE.md#12-scheduled-jobs-crons).

## Configuration checklist

- [ ] Working schedule has no hours on weekend days
- [ ] Public holidays entered for the year
- [ ] Settings reviewed: alerts, scheduling rules, overtime policy, payroll rate
- [ ] Facilities, branches, departments (branch + manager), units, job categories
- [ ] Users have their groups and allowed branches; employees are linked to users
- [ ] Credential types reviewed; mandatory and blocking flags match your policy
- [ ] Shift templates and employee authorisations (24 h, weekend, weekly hours)
- [ ] Coverage rules for critical units
- [ ] Allowance rules created and tested on a past period
- [ ] **Add Healthcare Input Rules** clicked on every salary structure in use
- [ ] Bank layout matching your bank; employee bank accounts trusted
- [ ] Clearance responsibles set; **End of Service formula configured**
- [ ] Training requirement matrix and KPI templates
- [ ] Biometric devices, mappings and push tokens; devices reach the server
- [ ] Scheduled actions reviewed
