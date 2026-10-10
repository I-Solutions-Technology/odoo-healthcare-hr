# Installation

This guide gets the Healthcare HR Management Suite running on the isolated Odoo 19 instance in
`/Users/jamalswilam/Desktop/Odoo19 Healthcare HR`. After it you will have the suite installed, the
server running on http://127.0.0.1:8095 and, optionally, the demo hospital loaded.

If the instance already exists (database `healthcare_hr`), skip to [Start the server](#4-start-the-server).

## 1. Prerequisites

| Item | Value on this machine | Notes |
|---|---|---|
| Odoo 19 Community source | `~/Desktop/odoo19` | Shared and **read-only**: never modify it |
| Python virtual environment | `~/Desktop/odoo19/.venv` (Python 3.12) | Used by every script |
| Odoo 19 Enterprise addons | `~/Downloads/enterprise-19.0` | Required: `planning`, `hr_payroll`, `hr_appraisal` are Enterprise modules |
| PostgreSQL | localhost:5432 (PostgreSQL 16) | Role `odoo19_user` with password `admin` and the right to create databases |
| Python packages | `requests`, `xlsxwriter` | Both ship with the Odoo requirements; `requests` is declared as an external dependency of `healthcare_hr_biometric`, `xlsxwriter` is used by the bank XLSX export |

Check the Python packages:

```bash
~/Desktop/odoo19/.venv/bin/python -c "import requests, xlsxwriter; print('ok')"
```

## 2. Instance layout

```text
Odoo19 Healthcare HR/
├── odoo.conf              instance configuration
├── custom_addons/         the 16 healthcare_hr_* modules (the only custom code)
├── scripts/
│   ├── run.sh             start the server (extra odoo-bin arguments are passed through)
│   ├── upgrade.sh         install or upgrade modules on healthcare_hr, then stop
│   └── test.sh            run module tests on a throw-away database
├── docs/                  this documentation
├── logs/                  odoo.log, test.log
└── .odoo_data/            filestore and sessions (data_dir)
```

Key `odoo.conf` settings:

| Setting | Value |
|---|---|
| `addons_path` | `custom_addons`, Enterprise, Community `addons`, `odoo/addons` (in this order) |
| `db_name` / `dbfilter` | `healthcare_hr` / `^healthcare_hr$` |
| `db_user` / `db_password` | `odoo19_user` / `admin` |
| `http_interface` / `http_port` / `gevent_port` | `127.0.0.1` / `8095` / `8096` |
| `workers` | `0` (threaded, development mode) |
| `limit_time_cpu` / `limit_time_real` | 600 / 1200 seconds |
| `logfile` | `logs/odoo.log` |
| `data_dir` | `.odoo_data` |
| `admin_passwd` | `admin` (database manager master password; change it outside development) |

## 3. Create a new database (first install only)

The suite is installed through the meta module `healthcare_hr_suite`, which installs the 15 functional
modules and their standard dependencies (hr, mail, hr_holidays, hr_attendance, hr_recruitment,
planning, hr_payroll, hr_appraisal).

**With the demo hospital** (recommended for evaluation and training):

```bash
cd "/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
scripts/run.sh -d healthcare_hr -i healthcare_hr_suite --with-demo --load-language=ar_001 --stop-after-init
```

**Without demo data** (production-like):

```bash
scripts/run.sh -d healthcare_hr -i healthcare_hr_suite --load-language=ar_001 --stop-after-init
```

Odoo creates the database if it does not exist. The command ends when installation is complete; watch
`logs/odoo.log` for errors. Log in afterwards with `admin` / `admin` and change the password.

> **Note:** In Odoo 19 demo data is not loaded by default. Pass `--with-demo` when you create the
> database.

The existing `healthcare_hr` database was created with demo data, `admin`/`admin`, and Arabic
(`ar_001`) loaded.

### What the demo contains

| Area | Demo records |
|---|---|
| Organisation | Hospital A with Branch 1 and Branch 2; departments ER, ICU, Radiology, Laboratory, Pharmacy, Outpatient, Administration; units ER Triage, ICU Bay A, X-Ray, OPD Clinics |
| Employees | 11: 2 doctors, 4 nurses, 1 pharmacist, 1 lab technician, 1 radiology technician, 2 administrative |
| Contracts | One contract per employee; nurse Laila Mahmoud on probation ending in 10 days |
| Credentials | Full credential sets; Hala Youssef's BLS is expired and Laila Mahmoud's license is unverified, so both are blocked from shifts |
| Roster | Coverage rules for ICU and ER, and a 2-week roster (past week and next week) published through the validation engine, plus an on-call duty with a call-in |
| Attendance | Past-week attendance with on-time, late, early leave, overtime, a missing checkout and an absence; the reconciliation is approved |
| Pay | Allowance rules (night, weekend, ICU, on-call, call-in, transportation, infection risk) and results, payroll inputs, an excellence bonus, draft payslips for 3 employees, an active loan and a submitted salary advance |
| Biometric | Two devices (push and file import), badge mappings for all employees, logs from today including a duplicate and an unknown badge |
| Talent | Training requirements (Nurse BLS, ICU Nurse ACLS, Radiology Radiation Safety, Lab Infection Control) with generated assignments, appraisal KPI templates and 2 appraisals, 2 applicants (one in Credential Verification) |

## 4. Start the server

```bash
cd "/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
scripts/run.sh
```

Open http://127.0.0.1:8095, log in as `admin` / `admin`, and open the **Healthcare HR** app.

`run.sh` passes extra arguments to `odoo-bin`, for example `scripts/run.sh --dev=xml` or
`scripts/run.sh --log-level=debug`.

## 5. Install or upgrade modules

Stop the server first, then:

```bash
# upgrade one module or a comma-separated list
scripts/upgrade.sh healthcare_hr_shift
scripts/upgrade.sh healthcare_hr_core,healthcare_hr_shift,healthcare_hr_attendance

# upgrade the whole suite
scripts/upgrade.sh healthcare_hr_suite,healthcare_hr_core,healthcare_hr_contract,healthcare_hr_credentials,healthcare_hr_shift,healthcare_hr_attendance,healthcare_hr_biometric,healthcare_hr_allowance,healthcare_hr_payroll,healthcare_hr_loan,healthcare_hr_training,healthcare_hr_appraisal,healthcare_hr_recruitment,healthcare_hr_clearance,healthcare_hr_bank,healthcare_hr_dashboard

# install a module that is not installed yet
scripts/upgrade.sh healthcare_hr_bank -i
```

`upgrade.sh` always targets the `healthcare_hr` database, uses ports 18595/18596 so it does not clash
with a running server, and stops when done. Upgrading all modules on the demo database is clean and
idempotent: records created by the demo loaders are not created twice.

Upgrades never overwrite your configuration: record rules, crons, sequences and shipped
configuration records are `noupdate`.

### Installing a subset

Every module can be installed on its own; Odoo installs its dependencies automatically. Common
subsets:

| Goal | Install |
|---|---|
| Organisation, contracts and credentials only | `healthcare_hr_credentials` |
| Rosters with the validation engine | `healthcare_hr_shift` |
| Rosters and attendance reconciliation | `healthcare_hr_attendance` |
| Add biometric devices | `healthcare_hr_biometric` |
| Allowances and payroll integration | `healthcare_hr_payroll` |
| Everything | `healthcare_hr_suite` |

See the dependency graph in [ARCHITECTURE.md](ARCHITECTURE.md#5-module-dependency-graph).

## 6. Run the tests

```bash
scripts/test.sh <modules> [database]
```

The script **drops and recreates** the target database (default `healthcare_hr_test`), installs the
modules with `--test-enable`, runs the tests tagged for those modules and prints a summary from
`logs/test.log`.

> **Warning:** Never pass `healthcare_hr` as the database argument: the script deletes the database
> before running.

Full run (148 tests, 0 failures on the last run):

```bash
scripts/test.sh healthcare_hr_suite,healthcare_hr_core,healthcare_hr_contract,healthcare_hr_credentials,healthcare_hr_shift,healthcare_hr_attendance,healthcare_hr_biometric,healthcare_hr_allowance,healthcare_hr_payroll,healthcare_hr_loan,healthcare_hr_training,healthcare_hr_appraisal,healthcare_hr_recruitment,healthcare_hr_clearance,healthcare_hr_bank,healthcare_hr_dashboard
```

The last lines should read:

```text
... 148 post-tests in ...
... 0 failed, 0 error(s) of 148 tests when loading database 'healthcare_hr_test'
```

See [TEST_PLAN.md](TEST_PLAN.md) for the test matrix and the manual acceptance checklist.

## 7. Languages

Arabic (`ar_001`) is loaded on `healthcare_hr`. To load it on another database, use **Settings >
Languages > Add Languages**, or:

```bash
scripts/run.sh -d <database> --load-language=ar_001 --stop-after-init
```

Arabic translations (`i18n/ar.po`) ship for all 15 functional modules (the suite meta module has no
labels). After a module update, reload them with `--i18n-overwrite`.

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Address already in use` on 8095 | Another server is running. Stop it, or start with `scripts/run.sh --http-port=<port> --gevent-port=<port+1>` |
| "Database not found" or a database selector appears | `dbfilter` only allows `healthcare_hr`. Use `-d <name> --db-filter=^<name>$` for another database |
| `Module not found: planning / hr_payroll / hr_appraisal` | The Enterprise path is missing from `addons_path`. Check `~/Downloads/enterprise-19.0` exists |
| Warning about PDF indexation and `pdfminer.six` in the log | Unrelated to the suite (attachment indexing). Install `pdfminer.six` in the venv if you want PDF content indexing |
| Biometric push returns 403 | Wrong device code or token, or the device is not of type *API Push*. Generate a new push token (System Administrator) |
| Test run fails on `createdb` / `dropdb` | The `odoo19_user` role needs the CREATEDB privilege. The script already terminates other connections to the test database before dropping it |
| Payslip shows no healthcare lines | The salary structure has no healthcare rules. Open the structure and click **Add Healthcare Input Rules** (see [CONFIGURATION.md](CONFIGURATION.md#9-payroll-structure-rules)) |

## 9. Uninstalling

Uninstall from **Apps** in reverse dependency order (dashboard first, core last), or uninstall
`healthcare_hr_core` to remove everything that depends on it. Uninstalling deletes the suite's data
(shifts, credentials, allowances, payroll inputs ...). Take a database backup first.
