# User Guide

This guide explains the daily work in the **Healthcare HR** app for each role, then walks through the
full employee lifecycle (the acceptance scenario) on the demo database.

Menu paths are written as they appear, starting from the app: **Healthcare HR > Workforce Planning >
Publish Roster**. What you see depends on your groups (see
[ARCHITECTURE.md](ARCHITECTURE.md#7-security-matrix)) and on the branches your user is allowed to
work on.

Contents

1. [Menu map](#1-menu-map)
2. [HR officer](#2-hr-officer)
3. [Scheduler](#3-scheduler)
4. [Attendance officer](#4-attendance-officer)
5. [Payroll officer](#5-payroll-officer)
6. [Department manager](#6-department-manager)
7. [Employee self-service](#7-employee-self-service)
8. [Hospital director](#8-hospital-director)
9. [Training and recruitment officers](#9-training-and-recruitment-officers)
10. [Acceptance scenario walkthrough](#10-acceptance-scenario-walkthrough)
11. [Alerts you will receive](#11-alerts-you-will-receive)

---

## 1. Menu map

```text
Healthcare HR
├── Dashboard
│   └── Overview
├── Employees
│   ├── Employees
│   ├── Onboarding
│   └── Practitioner Links
├── Contracts
│   ├── Contracts
│   ├── Contract Expiry
│   ├── Probation
│   └── Probation Reviews
├── Attendance
│   ├── Attendances
│   ├── Attendance Issues
│   ├── Reconciliation
│   ├── Overtime Approval
│   └── Biometric
│       ├── Devices
│       ├── Raw Logs
│       ├── Sync Batches
│       ├── Employee Mapping
│       └── Import File
├── Workforce Planning
│   ├── My Shifts
│   ├── Shift Assignments
│   ├── Generate Shifts
│   ├── Publish Roster
│   ├── Shift Templates
│   ├── Coverage
│   │   ├── Coverage Status
│   │   ├── Refresh Coverage
│   │   └── Coverage Rules
│   ├── Shift Swaps
│   └── On-Call
├── Leave
│   ├── Time Off
│   └── My Time Off
├── Payroll
│   ├── Allowances
│   │   ├── Compute Allowances
│   │   ├── Allowance Results
│   │   └── Allowance Rules
│   ├── Overtime
│   ├── Payroll Inputs
│   │   ├── Generate Inputs
│   │   ├── All Inputs
│   │   └── Bonuses & Deductions
│   ├── Payslips
│   ├── Pay Runs
│   ├── Loans
│   └── Bank Batches
├── Credentials
│   ├── All Credentials
│   └── Needs Attention
├── Training
│   ├── Assignments
│   ├── My Training
│   └── Requirement Matrix
├── Recruitment
│   ├── Job Positions
│   └── Applications
├── Performance
│   ├── Appraisals
│   └── KPI Templates
├── Employee Exit
│   ├── Exits
│   ├── My Clearance Tasks
│   └── Final Settlements
├── Reports
└── Configuration
```

**Reports** contains: Employee Master Data, Employee Turnover, Absenteeism, Late Attendance, Early
Leave, Shift Coverage, Shift Shortage, Night Shifts, Weekend Shifts, Overtime, Contract Expiry,
Probation Expiry, License Expiry, Credential Compliance, Allowance Analysis, Missing Training, Expiring
Certifications, Training Compliance, Leave Balance, Recruitment Funnel, Leave Utilization, Payroll
Summary, Payroll by Branch, Payroll by Department, Final Settlement. Most open as list, pivot and graph
views, so you can group, filter and export them to Excel.

**Configuration** is covered in [CONFIGURATION.md](CONFIGURATION.md).

## 2. HR officer

Groups: Healthcare HR Officer (HR Manager for contract dates and wages).

### Maintain employees

**Healthcare HR > Employees > Employees**. On the employee form, the **Healthcare** tab holds:

- *Identification*: employee number (generated `EMP-00001` when empty, unique per company), Arabic
  name, hire date, healthcare category, employment status.
- *Organisation*: branch, unit, medical department (when the clinical department differs from the
  administrative one), and the *Scheduling* group (24-hour shifts allowed, weekend work allowed, max
  weekly hours).
- *Clinical Profile* (clinical staff): specialty, sub-specialty, professional registration number.
- *Clinical System Links*: practitioner reference and links to external systems.

The employee's category comes from the job position and the branch from the department when you
leave them empty. Smart buttons open the employee's credentials, shifts, training and loans.

National ID, passport and nationality are the standard fields on the **Personal** tab.

### Contracts and probation (HR Manager)

Contract dates, wage and type are on the employee's **Payroll** tab (Odoo 19 stores the contract on
the employee version). The *Healthcare Contract Terms* group adds the renewal policy, licence and
insurance flags, and three buttons:

| Button | Effect |
|---|---|
| **Start Probation** | Needs *Probation End*; sets the probation to *Started* and the employee to *On Probation* |
| **Probation Review** | Creates a review for the employee's manager |
| **Renew Contract** | Opens the renewal wizard: months and optional new wage; creates a new version starting the day after the current end |

Lists: **Contracts > Contracts**, **Contract Expiry**, **Probation**, **Probation Reviews**.

A probation review holds attendance, competency and conduct scores (0 to 100; the overall score is
their average) and a recommendation: *Confirm Employment*, *Extend Probation* (new end date required)
or *Recommend Termination*. **Submit**, then **Approve** applies it. A termination recommendation only
flags the contract and raises an activity: open the exit yourself if you confirm it.

### Onboarding

**Employees > Onboarding**. A checklist is generated from the onboarding items (clinical-only items
only for clinical staff). **Start** sets the employee to *Onboarding*; tick items as they are done
(who and when is recorded); **Complete** is refused while a mandatory item is open and sets the
employee back to *Active*.

### Credentials

**Credentials > All Credentials** and **Credentials > Needs Attention** (expired, expiring, missing,
under verification).

| Status | Meaning |
|---|---|
| Missing | No number, no document, not verified |
| Under Verification | Number or document entered, not verified yet |
| Valid | Verified and not expiring soon |
| Expiring | Verified, expiry within the first alert threshold |
| Expired | Expiry date passed |

1. Enter the number, issuing authority, dates and scanned documents.
2. Click **Verify** (a number or a document is required). Changing the number or expiry date of a
   verified credential resets the verification.
3. To create placeholders for missing mandatory credentials, select employees in a list and use
   **Actions > Generate missing mandatory credentials**.

Only verified, non-expired credentials count for shifts. A missing or invalid *blocking* credential
stops the employee's shifts from being published.

### Practitioner links

**Employees > Practitioner Links** links an employee to a practitioner code in a clinical system (EMR,
LIS, RIS, PACS, pharmacy) with validity dates, so integrations can find the employee behind a
practitioner code.

### Exits

See steps 19 to 21 of the [walkthrough](#10-acceptance-scenario-walkthrough).

## 3. Scheduler

Groups: Scheduling Officer (Scheduling Manager to override conflicts and manage templates and coverage
rules).

### Build the roster

1. **Workforce Planning > Generate Shifts**: pick employees, a shift template, a date range and the
   weekdays, then **Generate Draft Shifts**. Existing shifts for the same employee, template and day are
   skipped.
2. Review in **Workforce Planning > Shift Assignments** (calendar, Gantt, list, pivot and graph views;
   filters by branch, department, unit, job, category, employee, shift type, date and state).
3. **Workforce Planning > Publish Roster**: choose the period and optionally a branch or department.
   The wizard shows the number of draft shifts and the coverage shortages *as if* the drafts were
   published. Rules with *Block publication* stop the publication. Click **Validate & Publish**.

You can also publish one shift with **Publish**, or run the checks without publishing with **Check
Conflicts**.

### Validation engine

Before a shift is published the engine checks, for the employee on that date:

| Check | Refused when |
|---|---|
| Archived employee | The employee is archived |
| Contract | No contract covers the shift date |
| Leave | An approved leave overlaps the shift |
| Credentials | A mandatory, blocking credential is missing, unverified or expired on the shift date |
| Allowed jobs | The template lists allowed jobs and the employee's job is not one of them |
| Template branch | The template belongs to another branch |
| Weekend | The shift falls on a weekend day and the employee is not allowed weekend work |
| 24-hour shift | The shift lasts 24 hours and the employee is not authorised |
| Maximum continuous shift | The shift is longer than the company limit |
| Duplicate | Same template, same day already assigned |
| Overlap | Another shift of the employee overlaps |
| Other branch | The overlapping shift is in another branch |
| Minimum rest | Rest before or after a neighbouring shift is below the required minimum |
| Weekly hours | Planned hours in the ISO week would exceed the employee's or the company's limit |

In a batch, when two new shifts clash, the earlier record wins and only the later one is flagged.
Shifts that fail go to **Conflict** with every reason stored on the shift. Publishing a batch reports
"N published, M in conflict"; filter on *Conflict* to review them.

To resolve a conflict: fix the cause (another employee, template or date, or verify the credential)
and publish again, or **Reset to Draft**. A **Scheduling Manager** can click **Publish Anyway** after
entering an *Override Reason*; the reason and the conflicts are logged in the chatter.

When a leave is approved after publication, the overlapping shifts move to **Conflict** with the reason
and an alert; their Planning slot is removed.

Published shifts are mirrored in the Odoo **Planning** app (Gantt).

### Coverage

**Workforce Planning > Coverage > Coverage Status** shows, per rule and day, assigned staff against
the minimum and preferred numbers (Shortage, Minimum Met, Preferred Met). **Refresh Coverage**
recomputes it now; the daily cron refreshes the next 14 days and alerts the department manager of
each shortage. Reports: **Shift Coverage** and **Shift Shortage**.

### Shift swaps

**Workforce Planning > Shift Swaps**. A swap goes Requested > Colleague Accepted > Manager Approved >
Applied. As scheduling officer you can accept for the colleague, and you do the last step with
**Approve & Apply**, which re-validates and swaps the employees on the shifts (and in Planning). A
daily reminder is sent for swaps waiting for approval.

### On-call

**Workforce Planning > On-Call**: create the duty (employee, start, end), **Schedule** it, record the
call-in (*Called In At*, *Call Ended At*), **Mark Done**, then **Approve**. Standby hours = duty length
minus call-in time. Only approved duties feed the on-call and call-in allowances.

## 4. Attendance officer

Groups: Attendance Officer (Attendance Manager for devices and approval resets).

### Attendance and issues

Attendances come from the standard check-in/check-out, the kiosk or biometric devices. Each
attendance is matched to its planned shift (a check-in up to 3 hours before the start, by default) and
shows: planned shift, late minutes, early leave minutes, extra time vs shift, night, weekend and
holiday hours, and a status:

| Status | Meaning |
|---|---|
| Present | On time (within the template grace minutes) |
| Late | Checked in after the start plus grace |
| Early Leave | Checked out before the end minus grace |
| Partial | Late and early |
| On Leave | An approved leave overlaps the attendance |
| Missing Checkout | Still open 2 hours after the planned end (16 hours after check-in when unplanned) |
| Unplanned | No planned shift matched |

**Attendance > Attendance Issues** lists missing checkouts, unplanned and partial attendances. Correct
the times or the *Planned Shift* directly on the attendance. A missing-checkout alert is raised once
per attendance (cron every 4 hours).

### Biometric devices

**Attendance > Biometric**:

- **Sync Batches**: one per import, with Received, Created, Duplicates, Processed, Pending and Failed
  counters, state (Done, Partial, Failed) and an error log. **Retry failed** re-processes failed logs.
- **Raw Logs**: every punch as received. Status Pending, Done, Duplicate, Ignored or Error, with the
  error message and the attendance created. **Retry** works up to 5 times; invalid rows (missing data,
  bad timestamp) cannot be retried and must be resent.
- **Employee Mapping**: device codes to employees. An *Unknown employee code* error is fixed by adding
  the mapping, then **Retry**.
- **Import File**: CSV upload (`employee_code,timestamp,event_type`).
- On a device: **Sync now** (pull devices), **Import File**, **Process pending**.

Punches are processed in chronological order into attendances, never duplicated: a repeated scan
within 5 minutes is a duplicate, a punch inside an existing attendance is ignored, a check-out without
an open attendance is an error. The device never invents a check-out: an attendance left open longer
than 16 hours (or the shift end plus the missing-checkout delay) must be corrected by hand.

### Reconciliation

**Attendance > Reconciliation** turns finished shifts into approved work data.

1. **New**: period, optionally branch and department. **Compute** creates one line per finished shift
   (published, confirmed, working or completed, plus conflicting shifts that were actually worked).
2. Each line shows status (including *Absent* when there is no attendance and no leave), planned and
   worked hours, late and early minutes, worked extra time, night, weekend and holiday hours, and
   **Approved Overtime**.
3. Approved overtime is proposed automatically (extra time above 30 minutes on templates that allow
   overtime). Change it on the line or in **Attendance > Overtime Approval**; it must stay between 0
   and the worked extra time. Your edits survive a **Recompute**.
4. **Approve Work Data**: every shift gets its approved overtime, its payroll overtime (rounded down to
   15 minutes by default) and moves to **Approved**, ready for allowances and payroll. Absent and
   on-leave lines get 0 overtime.

**Reset** returns the batch to draft, unless some shifts are already in payroll. A daily cron creates or
refreshes a company-wide batch for yesterday and alerts on issues; it never approves.

You can also approve a single worked shift with **Approve Work** on the shift (Attendance Manager:
**Reset Approval**).

Reports: **Absenteeism**, **Late Attendance**, **Early Leave**, **Overtime**, **Night Shifts**,
**Weekend Shifts**.

## 5. Payroll officer

Groups: Payroll Officer (Payroll Manager for rules, layouts and settlement components).

Only approved work data is paid. The chain is: approved shifts and on-call duties > allowance results
(confirmed) > payroll inputs > payslip > bank batch.

### Allowances

**Payroll > Allowances > Compute Allowances**: period (the current month by default), optional
employees, optional *Confirm results*. The engine recomputes the period idempotently: it updates
existing results, removes draft results that no longer apply and never touches results already in
payroll. **Allowance Results** lists each result with quantity, rate, amount, computation note and the
shifts or on-call duties used. **Confirm** the results you accept; only confirmed results go to payroll.

### Overtime

**Payroll > Overtime** lists shifts with approved overtime. Payroll pays *payroll overtime* hours x
hourly rate x overtime rate (1.25 by default).

### Payroll inputs

**Payroll > Payroll Inputs > Generate Inputs**: period, optional employees, *Compute allowances*
(recompute and confirm the period's allowances first). The result is one input per source:

| Source | Processing key | Payslip input |
|---|---|---|
| Confirmed allowance result | `allowance:<id>` | Night, Weekend, Holiday, On-call or Healthcare Allowance |
| Shift with payroll overtime | `overtime:<shift id>` | Overtime |
| Loan or advance installment due in the period | `loan_installment:<id>` | Loan Installment or Salary Advance Recovery |
| Manual bonus or deduction | `manual:<sequence>` | Bonus or Healthcare Deduction |

Running the generation again never duplicates an input and never changes an input already in a
payslip. **Bonuses & Deductions**: create manual items (they start as *Draft*), then **Confirm** them.

### Payslips

**Payroll > Payslips** or **Payroll > Pay Runs** (standard Odoo Payroll).

1. Create the payslip and **Compute Sheet**. The employee's confirmed inputs whose period ends inside
   the payslip period appear under *Other Inputs* (`HC_...` codes) and on the **Healthcare Sources**
   tab. They are reserved for this payslip.
2. **Validate**: inputs become *Paid*, allowance results *In Payroll*, loan installments *Paid*, and the
   shifts *Payroll Posted*.
3. **Cancel** releases everything back to *Confirmed* / *Approved*. **Reset to draft** keeps the inputs
   on the payslip and releases the sources.

If no healthcare lines affect the net, the structure needs its healthcare rules (see
[CONFIGURATION.md](CONFIGURATION.md#9-payroll-structure-rules)).

### Loans and salary advances

**Payroll > Loans**. **Approve** a submitted request (you can change the approved amount): the
installment schedule is generated from the amount, count and first deduction date. **Mark as Paid** when
the money is handed over: the loan becomes *Active* and installments are deducted through payroll
inputs. On an installment, **Postpone** moves it one month after the last one. **Early Settlement**
closes the remaining balance. A salary advance is recovered in at most 3 installments.

### Bank batches

**Payroll > Bank Batches** > **New**:

1. Choose the layout, payment date and scope (payslip period, pay run and/or branch). **Load Payslips**
   adds one line per validated payslip with a positive net, skipping payslips already in another active
   batch.
2. Lines without a bank account, or with an untrusted account (*Send Money* not enabled), are in error
   and block the export. Fix the account and reload, or remove the line.
3. **Export File** produces the CSV, TXT or XLSX file on the batch. Upload it to the bank portal.
4. **Mark as Sent** (or **Send via API** when a bank connector is installed), then **Confirm Payment**:
   the payslips are marked *Paid*.

Reports: **Payroll Summary**, **Payroll by Branch**, **Payroll by Department**, **Allowance Analysis**,
**Final Settlement**.

## 6. Department manager

Groups: Department Manager. You manage a department when you are its manager (department form) and
your employee is linked to your user.

You see the shifts, on-call duties, swaps, probation reviews, training assignments, exits and
clearance items of the departments you manage and of your direct reports. You do **not** see payroll
inputs, allowances, loans, bank batches or settlements, nor wages or confidential credentials.

Daily tasks:

- **Workforce Planning > Shift Swaps**: **Manager Approve** swaps your team accepted.
- **Workforce Planning > Shift Assignments** and **Coverage Status**: check your roster and shortages
  (you receive shortage alerts).
- **Contracts > Probation Reviews**: fill the reviews assigned to you and **Submit**.
- **Employee Exit > My Clearance Tasks**: clear the *Department* item (handover of patients, duties and
  documents) for leavers of your department.
- **Leave > Time Off**: approve leave as in standard Odoo; the shift engine takes it into account.

## 7. Employee self-service

Every internal user has self-service access to their own records only.

| What | Where |
|---|---|
| Your shifts | **Workforce Planning > My Shifts** (also in the Planning app) |
| Swap a shift | **Workforce Planning > Shift Swaps** > New |
| Your on-call duties | **Workforce Planning > On-Call** |
| Your credentials | **Credentials > All Credentials** (read only) |
| Your training | **Training > My Training** |
| Time off | **Leave > My Time Off** |
| Your appraisal | **Performance > Appraisals** (standard appraisal access) |

To swap a shift: **New**, choose *Shift to Give* (your published or confirmed shift), the *Colleague*
and a *Reason*, then **Send Request**. Leave *Shift to Take* empty for a one-way hand-over; because you
only see your own shifts, a two-way swap is usually entered by a scheduling officer. The request is
checked immediately: the colleague must be in the same healthcare category and department, and the
validation engine must accept the result. Your colleague receives an activity and clicks **Accept**.

You can read your KPI lines on your appraisal but cannot rate yourself.

Loan requests: open **Healthcare HR > My Loan Requests** to create and follow your own loan or salary
advance requests; you can edit them while they are draft or submitted.

## 8. Hospital director

Groups: Hospital Director (read across all branches).

**Dashboard > Overview** opens one screen per user, computed when you open it. Filter by *Branch*
(includes sub-branches) and *Date*; every tile opens the underlying records.

| Section | Tiles |
|---|---|
| Headcount | Employees, Doctors, Nurses, Technicians, Administrative, New Hires (30 d), Exits (30 d) |
| Attendance today | Present, Absent, Late, On Leave, Missing Checkout, Shifts with Overtime (month), approved overtime hours |
| Workforce | Scheduled Today, Shift Shortages (14 d), Draft Shifts (7 d), Conflicts, Night Shifts Today |
| Compliance | Contracts Expiring (60 d), Probation Ending (30 d), Licenses Expiring, Expired / Missing Credentials, Missing Training, Expired Training (training tiles only when the training module is installed) |
| Payroll (payroll officers only) | Net Payroll, Overtime Cost and Allowance Cost for the month, with links to Payroll Summary, Payroll Inputs, Allowance Analysis, Payroll by Department and Payroll by Branch |

"Draft Shifts" counts unpublished shifts in the next 7 days; there is no separate open-shift model.
Tiles you are not allowed to read show 0 (for example contract dates, which Odoo 19 restricts to HR
managers).

Use **Reports** for trends: Employee Master Data (grouped by branch), Employee Turnover, Absenteeism,
Shift Coverage and Shortage, Contract / Probation / License Expiry, Credential and Training Compliance.

## 9. Training and recruitment officers

**Training Officer**: **Training > Assignments** (**Start**, **Mark Completed**, **Waive** with a reason,
**Cancel Waiver**) and **Training > Requirement Matrix**. Completing a training requires a certificate
number or an attached certificate, and creates or renews the employee's credential of the required type
(expiry = completion + renewal period). Reports: **Missing Training**, **Expiring Certifications**,
**Training Compliance** (compliance rate by department, branch or requirement).

**Recruitment Officer**: **Recruitment > Applications** in the standard pipeline, with the healthcare
data on the **Healthcare** tab. See steps 1 and 2 below. Report: **Recruitment Funnel**.

---

## 10. Acceptance scenario walkthrough

This walkthrough follows section 51 of the requirements on the demo database (`healthcare_hr`, user
`admin`, who holds every group). Dates are relative to today because the demo is generated relative to
the installation date. Each step says what to check.

### Step 1. Recruit the candidate

1. **Recruitment > Applications**, open **Reem Saber** (ICU Nurse, stage *Credential Verification*).
2. **Healthcare** tab: specialty ICU Nursing, 6 years of experience, license RN-55021, classification
   Registered Nurse. *Required Credentials* are the mandatory clinical types: Medical License,
   Professional Classification, BLS.
3. The license line is verified, the BLS line is not, and there is no Professional Classification line:
   *Credential Verification* shows **In Progress**.
4. Try to drag the applicant to a hired stage. **Check:** the move is refused with the list of missing
   credentials.

### Step 2. Create the employee

1. Add a *Professional Classification* line with a number and an expiry date; click **Verify** on it
   and on the BLS line. **Check:** status **Verified**.
2. Move the applicant to the hired stage and create the employee (standard **Create Employee**).
3. **Check** on the new employee: category Nurse, specialty, Arabic name, *Professional Registration
   No.* = RN-55021, hire date, an employee number `EMP-...`; the three credentials exist and are
   verified; an onboarding checklist exists under **Employees > Onboarding**.

### Step 3. Create the contract

On the employee's **Payroll** tab set the contract start and end dates, wage and contract type
(for example *Full-Time*), the salary structure type, the renewal
policy (*Manual*) and *Medical License Required*. **Check:** the employee appears in **Contracts >
Contracts**.

### Step 4. Verify credentials

Open the employee's **Credentials** smart button. **Check:** all three are *Valid*. For comparison, open
**Credentials > Needs Attention**: Hala Youssef's BLS is *Expired* and Laila Mahmoud's Medical License is
*Under Verification*.

### Step 5. Start probation

1. On the **Payroll** tab set *Probation End* (for example today + 90 days) and click **Start
   Probation**. **Check:** probation *Started*, employment status *On Probation*.
2. In **Employees > Onboarding**, **Start** the checklist, tick the items and **Complete** it.
3. For an existing probation, open Laila Mahmoud (probation ending in 10 days): after the daily cron she
   is *Review Due* with an activity. Click **Probation Review**, choose *Confirm Employment*, **Submit**,
   **Approve**. **Check:** probation *Passed*, status *Active*.

### Step 6. Assign department and branch

On the employee: *Department* ICU (the branch becomes Branch 1), **Healthcare** tab: *Unit* ICU Bay A;
*Scheduling*: weekend work allowed. Link the employee to a user if they will use self-service, and add
a badge code in **Attendance > Biometric > Employee Mapping** (for example `2001` on device DEV-B1-01).

### Step 7. Assign a medical shift

1. **Workforce Planning > Generate Shifts**: the new nurse, template *12 Hour Day*, the next 7 days,
   Monday to Friday. **Generate Draft Shifts**.
2. **Workforce Planning > Publish Roster**: the same period, department ICU. Review the shortage
   summary (demo ICU rules: 1 nurse on 12 Hour Day, 2 on 12 Hour Night), then **Validate & Publish**.
3. **Check:** the shifts are *Published* and appear in the Planning Gantt. In the demo roster, filter on
   *Conflict*: Hala Youssef's shifts after her BLS expired and Laila Mahmoud's shifts are in conflict
   ("has no valid BLS", "has no valid Medical License"). As Scheduling Manager, enter an *Override
   Reason* on one of them and click **Publish Anyway** to see the logged override.
4. Try a 24 Hour shift for the new nurse. **Check:** refused, "not authorised for 24-hour shifts".

### Step 8. Import biometric attendance

Use a past shift for this step (future punches are rejected). Create a CSV file:

```text
employee_code,timestamp,event_type
2001,<date of a past shift> 08:12:00,check_in
2001,<same date> 20:55:00,check_out
2001,<same date> 20:55:00,check_out
9999,<same date> 08:00:00,check_in
```

**Attendance > Biometric > Import File**, device DEV-B1-01, *Process now*. **Check** the sync batch:
4 received, 3 created, 1 duplicate, the `9999` log in *Error* ("Unknown employee code 9999 on device
DEV-B1-01"), batch state *Partial*. The nurse has one attendance matched to the shift. Importing the same
file again creates nothing.

To use a past date for the new nurse, create a shift on a past day first, or run the step with a demo
employee (codes 1001 to 1011).

### Step 9. Reconcile attendance

**Attendance > Reconciliation > New**, period covering the shift, **Compute**. **Check** the line: status
*Late* (12 minutes, above the 10-minute grace), extra time 0.92 h (55 minutes after the end), approved
overtime proposed 0.92. In **Overtime Approval** set it to 0.75, then **Approve Work Data**. **Check:**
the shift is *Approved* with approved overtime 0.75 h and payroll overtime 0.75 h.

The demo database already has an approved reconciliation for the past week (late, early, overtime,
missing checkout and absence cases).

### Step 10. Late, overtime and night work

**Check** in **Reports > Late Attendance**, **Reports > Overtime** and **Reports > Night Shifts**. Night,
weekend and holiday hours are computed on each attendance and shift: a 12 Hour Night shift
(20:00-08:00) worked in full shows 8 night hours with the default 22:00-06:00 night window; a shift on a
weekend day of the working schedule shows weekend hours; a shift on a public holiday shows holiday
hours.

### Step 11. Generate allowances

**Payroll > Allowances > Compute Allowances**, current month, *Confirm results*. **Check** in
**Allowance Results** for the new nurse, with the demo rules: ICU allowance (100 per approved ICU shift,
capped at 2,000), transportation (10 % of the wage, capped at 3,000) and infection risk for nurses
(500). Night-shift nurses also get the night allowance (25 per night hour). Each result lists the shifts
it used. Computing again changes nothing.

### Step 12. Process leave

1. The new nurse requests a day off on a day with a published shift (**Leave > My Time Off**, or the
   Time Off app); approve it in **Leave > Time Off**.
2. **Check:** the shift is now in *Conflict* with "Approved leave ... overlaps this shift" and an alert
   "Shift uncovered by approved leave". Publishing a new shift on a leave day is refused.

### Step 13. Create payroll inputs

**Payroll > Payroll Inputs > Generate Inputs**, current month. **Check** in **All Inputs**: one input
per allowance result and one *Overtime* input per shift with payroll overtime (keys `allowance:<id>`,
`overtime:<id>`); the demo loan of Mona Ali produces a `loan_installment:<id>` input when an installment
is due in the month. Generate again: nothing is duplicated. Add a *Bonus* in **Bonuses & Deductions**
and **Confirm** it.

### Step 14. Generate the payslip

**Payroll > Payslips**, create a payslip for the nurse for the current month and **Compute Sheet**.
**Check:** *Other Inputs* show `HC_OVERTIME`, `HC_ALW` / `HC_NIGHT` and `HC_BONUS`; the salary lines
include them; the **Healthcare Sources** tab lists the inputs. **Validate**. **Check:** inputs *Paid*,
allowance results *In Payroll*, shifts *Payroll Posted*. (The demo also has draft payslips for Mona Ali,
Dr. Sara Khalil and Hala Youssef.)

### Step 15. Create the bank payroll batch

1. Give the nurse a bank account and enable *Send Money* on it.
2. **Payroll > Bank Batches > New**, layout *Generic CSV*, the current month, **Load Payslips**.
3. **Export File**, download it, **Mark as Sent**, **Confirm Payment**. **Check:** the file contains the
   IBAN and net salary; the payslip is *Paid*.

### Step 16. Run the appraisal

**Performance > Appraisals**, create an appraisal for the nurse. **Check:** the **Healthcare KPIs** tab
is loaded from the *Nurses* template (Attendance 25, Shift Compliance 20, Medication Compliance 20,
Patient Feedback 15, Training Compliance 20). **Refresh Automatic KPIs** fills attendance rate, late
rate and training compliance from the shifts and credentials; enter the manual actuals; the *KPI Score*
is the weighted total. **Check:** nothing on the contract or probation changes.

### Step 17. Track training

**Training > Assignments**: the daily training cron assigns *Nurse - BLS* and *ICU Nurse - ACLS* to nurses
who are not covered by a valid credential (run it now from **Settings > Technical > Scheduled Actions >
Healthcare HR: training assignments, expiry and alerts > Run Manually**). The new nurse has a valid BLS,
so she only gets ACLS. Open that assignment, **Start**, enter a certificate number, **Mark
Completed**. **Check:** an ACLS credential is created with expiry = completion + 24 months, *Under
Verification* (the requirement does not auto-verify); the **Training Compliance** report updates.

### Step 18. Renew the contract

Employee **Payroll** tab > **Renew Contract**, 12 months, optional new wage, **Renew**. **Check:** a new
employee version starts the day after the old end date and ends 12 months later. With renewal type
*Non Renewable* the renewal is refused. Contracts with renewal type *Automatic* are renewed by the daily
cron once they have expired.

### Step 19. Employee exit

**Employee Exit > Exits > New**: the nurse, reason *Resignation*, last working date, standard departure
reason. **Start Clearance**. **Check:** seven clearance items (HR, Finance, IT, Department, Medical
Equipment, Security, Administration) with activities for their responsibles; the employee is *Notice
Period*.

### Step 20. Clearance

**Employee Exit > My Clearance Tasks**. On *Medical Equipment* enter an obligation amount (for example
400 for an unreturned pager). **Clear** each item (**Block** needs a note). **Check:** when the last
mandatory item is cleared, the exit moves to *Final Settlement* and a settlement is created, with an
alert.

### Step 21. Final settlement

1. **Employee Exit > Final Settlements**, open the settlement, **Compute**. **Check:** Final Salary
   (days worked in the last month x daily wage on a 30-day basis), Unused Leave, pending
   overtime/allowances/bonuses, Outstanding Loans, Clearance Obligations (-400). *End of Service* is 0
   until you configure its formula (see [CONFIGURATION.md](CONFIGURATION.md#settlement-components)).
2. **Confirm**: the exit moves to *HR Approval*. **Mark as Paid**: pending inputs are closed and loans
   settled. Click **Print** for the settlement PDF.
3. On the exit, **HR Approve & Archive**. **Check:** the contract ends on the last working date, future
   shifts are *Cancelled*, the employee is *Exited* with the departure date and is archived.

---

## 11. Alerts you will receive

All alerts are To-Do activities, created once per record and situation (no daily repeats while the
activity is open). They go to the employee's HR responsible, else the company's default alert
responsible, else the employee's manager, else the administrator, unless stated.

| Alert | When | Recipient |
|---|---|---|
| Probation ends in N days | 30, 14, 7 days before (configurable) | HR responsible |
| Termination recommended after probation | Review approved with that recommendation | HR responsible |
| Contract expires in N days | 60 days before (configurable, per contract) | HR responsible |
| Credential expires in N days / EXPIRED / missing mandatory | Thresholds 90, 60, 30, 7 days and on expiry | HR responsible |
| Shift shortage | Coverage below minimum in the next 14 days | Department manager, else branch manager |
| Shift uncovered by approved leave | Leave approved over a published shift | HR responsible |
| Pending shift swap | Swap accepted or manager-approved and waiting | Department manager (accepted) / HR responsible |
| Missing checkout | Open attendance past the limit | HR responsible |
| Attendance issues to review | Daily reconciliation of yesterday finds issues | Default alert responsible |
| Biometric sync failed | Pull device error | Default alert responsible, else administrator |
| Training expires / missing mandatory training | Within the training alert window / open mandatory assignment | HR responsible |
| Clearance of an employee | Clearance started | Clearance item responsible |
| Final settlement pending / Approve the exit | Clearance completed / settlement confirmed | Default alert responsible |
