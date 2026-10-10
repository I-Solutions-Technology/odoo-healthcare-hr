# Test Plan

This plan covers the automated tests shipped with the suite, how to run them, how they map to the
minimum tests required in section 49 of the requirements, and the manual user-acceptance (UAT)
checklist to run on the demo database before go-live.

**Status of the last full run:** 148 tests, 0 failures, 0 errors, with all 16 modules installed
together (`logs/test.log`: "0 failed, 0 error(s) of 148 tests when loading database
'healthcare_hr_test'"). Upgrading all modules on the demo database is clean and idempotent.

## 1. How to run the tests

### Full suite

```bash
cd "/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
scripts/test.sh healthcare_hr_suite,healthcare_hr_core,healthcare_hr_contract,healthcare_hr_credentials,healthcare_hr_shift,healthcare_hr_attendance,healthcare_hr_biometric,healthcare_hr_allowance,healthcare_hr_payroll,healthcare_hr_loan,healthcare_hr_training,healthcare_hr_appraisal,healthcare_hr_recruitment,healthcare_hr_clearance,healthcare_hr_bank,healthcare_hr_dashboard
```

`scripts/test.sh <modules> [database]`:

1. terminates connections to the test database, drops it and creates it again (default
   `healthcare_hr_test`);
2. installs the listed modules with `--test-enable` on a random HTTP port (18000-18899);
3. runs the tests tagged `/<module>` for each listed module;
4. writes `logs/test.log` and prints the failure lines and the summary.

> **Warning:** The script deletes the target database. Never pass `healthcare_hr`.

Expected end of output:

```text
--- results ---
... 0 failed, 0 error(s) of 148 tests when loading database 'healthcare_hr_test'
```

### One module or a few

```bash
scripts/test.sh healthcare_hr_shift
scripts/test.sh healthcare_hr_payroll,healthcare_hr_loan,healthcare_hr_bank
```

Dependencies are installed automatically; only the tests of the listed modules run.

### One test class or method

After `scripts/test.sh` has created the test database, re-run a single test with Odoo's test-tag syntax
`/module:Class.method`:

```bash
BASE="/Users/jamalswilam/Desktop/Odoo19 Healthcare HR"
~/Desktop/odoo19/.venv/bin/python ~/Desktop/odoo19/odoo-bin -c "$BASE/odoo.conf" \
    -d healthcare_hr_test --db-filter='^healthcare_hr_test$' --http-port=18123 --gevent-port=18124 \
    -u healthcare_hr_shift --test-enable \
    --test-tags '/healthcare_hr_shift:TestShiftEngine.test_leave_conflict' \
    --stop-after-init --logfile="$BASE/logs/test.log"
```

### Test design

- All tests are `TransactionCase` tagged `post_install`, `-at_install`, `healthcare`, except the
  biometric push endpoint tests (`HttpCase`, real HTTP requests).
- Shared fixtures:
  - `HealthcareCommon` (core): a hospital with two branches, ICU and ER departments, an ICU unit, nurse
    and doctor jobs, a nurse (Branch 1) and a doctor (Branch 2), UTC timezone.
  - `ShiftCommon` (shift): adds contracts, verified mandatory credentials, the shipped templates, a
    Monday 8 to 14 days ahead and fixed company scheduling limits (night 22:00-06:00, 60 h per week,
    24 h maximum shift, 8 h rest).
  - `PayrollCommon` (payroll): adds the *Regular Pay* structure with healthcare rules, overtime rate 1.5,
    200 monthly hours, and disables demo allowance rules.
- Tests do not depend on demo data; they build their own records and deactivate demo allowance rules.

## 2. Test inventory

| Module | Test file(s) | Test methods |
|---|---|---|
| healthcare_hr_core | `test_core.py` | 7 |
| healthcare_hr_contract | `test_contract.py` | 5 |
| healthcare_hr_credentials | `test_credentials.py` | 8 |
| healthcare_hr_shift | `test_shift.py` | 26 |
| healthcare_hr_attendance | `test_attendance.py` | 10 |
| healthcare_hr_biometric | `test_biometric.py`, `test_controller.py` | 24 + 4 = 28 |
| healthcare_hr_allowance | `test_allowance.py` | 8 |
| healthcare_hr_payroll | `test_payroll.py` | 6 |
| healthcare_hr_loan | `test_loan.py` | 6 |
| healthcare_hr_bank | `test_bank.py` | 5 |
| healthcare_hr_clearance | `test_clearance.py` | 4 |
| healthcare_hr_training | `test_training.py` | 13 |
| healthcare_hr_appraisal | `test_appraisal.py` | 8 |
| healthcare_hr_recruitment | `test_recruitment.py` | 8 |
| healthcare_hr_dashboard | `test_dashboard.py`, `test_security.py` | 2 + 4 = 6 |
| **Total** | | **148** |

The 148 test methods above are the 148 tests of the full run.

The lead developer's last per-module runs reported these counts: allowance 10, appraisal 10,
attendance 12, bank 7, biometric 32, clearance 6, contract 7, core 9, credentials 10, dashboard 10,
loan 8, payroll 8, recruitment 10, shift 28, training 15 (recorded as including inherited test
classes). Each is the method count above plus two per test class, so they add up to 182, not 148. Use
the full-run total of 148 as the reference figure.

## 3. Test matrix against section 49

### Shift

| Required test | Test method(s) in `healthcare_hr_shift/tests/test_shift.py` |
|---|---|
| Cross-midnight shift | `test_cross_midnight_shift` |
| Overlapping shifts | `test_overlapping_shifts` |
| Leave conflict | `test_leave_conflict`, `test_leave_approved_after_publication_flags_shift` |
| Expired credential | `test_expired_credential_blocks` |
| Minimum rest violation | `test_minimum_rest_violation` |
| Valid assignment | `test_valid_assignment_published_and_planning` |
| 12-hour shift | `test_twelve_hour_shift` |
| 24-hour shift | `test_twenty_four_hour_shift` |

Additional shift tests: `test_timezone_conversion`, `test_duplicate_assignment`,
`test_two_branches_simultaneously`, `test_contract_expired_blocks`, `test_weekly_hours_limit`,
`test_weekend_authorisation`, `test_incompatible_pattern`, `test_batch_publish_partial`,
`test_force_publish_requires_manager_and_reason`, `test_coverage_shortage`,
`test_publish_wizard_blocking_rule`, `test_shift_swap`, `test_swap_rejects_unqualified_colleague`,
`test_split_hours_weekend_holiday`, `test_oncall_hours`, `test_generate_is_idempotent`,
`test_locked_after_approval`.

### Attendance

| Required test | Test method(s) in `healthcare_hr_attendance/tests/test_attendance.py` |
|---|---|
| Late check-in | `test_late_within_and_beyond_grace` |
| Early checkout | `test_early_checkout` |
| Overtime | `test_overtime_separation`, `test_overtime_below_threshold_not_proposed`, `test_payroll_overtime_rounding` |
| Missing checkout | `test_missing_checkout` |
| Attendance without shift | `test_attendance_without_shift` |
| Shift across midnight | `test_shift_across_midnight` |

Additional: `test_on_time`, `test_absence_and_idempotent_reconciliation`.

### Biometric

| Required test | Test method(s) in `healthcare_hr_biometric/tests/` |
|---|---|
| Duplicate event | `test_duplicate_event_in_batch_and_across_imports`, `test_same_timestamp_on_other_device_is_not_a_duplicate` |
| Unknown employee | `test_unknown_employee` |
| Valid mapping | `test_valid_mapping_creates_attendance_matched_to_shift`, `test_device_specific_mapping_precedence`, `test_mapping_uniqueness` |
| Idempotent import | `test_idempotent_import_and_process`, `test_push_creates_logs_idempotently` (HTTP) |
| Failed log processing | `test_failed_processing_then_retry`, `test_retry_after_fixing_mapping`, `test_retry_limit_and_invalid_payload`, `test_invalid_rows_become_error_logs` |

Additional: `test_timezone_conversion`, `test_batch_counts`, `test_chronological_processing`,
`test_open_attendance_rules`, `test_check_out_before_check_in_is_error`,
`test_unknown_event_type_toggles`, `test_cron_process_pending`, `test_csv_import_wizard`,
`test_push_token`, `test_pull_generic`, `test_pull_not_implemented_vendor_never_raises`,
`test_access_rights`, `test_datetime_object_input`; push endpoint (`test_controller.py`):
`test_rejects_missing_headers`, `test_rejects_bad_token_or_device`, `test_rejects_bad_payloads`.

### Allowance

| Required test | Test method(s) in `healthcare_hr_allowance/tests/test_allowance.py` |
|---|---|
| Per-hour | `test_per_hour_night` |
| Per-shift | `test_per_shift_weekend`, `test_per_shift_department_and_maximum` |
| Percentage | `test_percentage_basic_and_gross` |
| Night shift | `test_per_hour_night` |
| Weekend | `test_per_shift_weekend` |

Additional: `test_category_filter_and_minimum`, `test_formula`, `test_idempotent_and_only_approved`,
`test_oncall_allowance`.

### Payroll

| Required test | Test method(s) |
|---|---|
| No duplicate input generation | `test_no_duplicate_generation` (payroll), repeated generation in `test_installment_through_payroll` (loan) |
| Correct source linkage | `test_overtime_input` (source model, record and processing key), `test_allowance_input` |
| Loan installment | `test_installment_through_payroll` (loan) |
| Overtime input | `test_overtime_input` |
| Allowance input | `test_allowance_input` (draft results are not sent, confirmed ones are, on `HC_NIGHT`) |

Additional payroll: `test_payslip_integration_and_lifecycle` (inputs on the payslip, no second payslip
can take them, validate and cancel lifecycle), `test_structure_rules_idempotent`,
`test_department_manager_has_no_payroll_access`. Loan: `test_schedule`,
`test_completion_and_settlement`, `test_postpone`, `test_advance_limit`, `test_self_service_access`.
Bank: `test_missing_bank_account_blocks_export`, `test_csv_content`, `test_fixed_width_and_xlsx`,
`test_done_marks_payslips_paid`, `test_bank_data_restricted`.

### Credentials

| Required test | Test method(s) in `healthcare_hr_credentials/tests/test_credentials.py` |
|---|---|
| Valid | `test_status_valid` |
| Expiring | `test_status_expiring` |
| Expired | `test_status_expired` |
| Blocked shift | `test_blocked_shift_check` (and `test_expired_credential_blocks` in shift) |

Additional: `test_status_missing_and_under_verification`, `test_new_number_requires_reverification`,
`test_alerts_idempotent`, `test_generate_missing`.

### Security

| Required test | Test method(s) |
|---|---|
| Employee access | `test_employee_sees_only_own_records` (dashboard/test_security), `test_self_service_access` (loan), `test_self_service_rule` (training), `test_access_rights` (biometric) |
| Department manager access | `test_department_manager_scope` (dashboard/test_security) |
| Payroll restriction | `test_payroll_restriction` (dashboard/test_security), `test_department_manager_has_no_payroll_access` (payroll), `test_bank_data_restricted` (bank), `test_payroll_tiles_hidden_for_non_payroll` (dashboard) |
| Multi-company isolation | `test_multi_company_isolation` (core and dashboard/test_security) |

Also: branch-level access, `test_branch_rule_for_officer` (core).

### Areas beyond section 49

| Module | Test methods |
|---|---|
| Core | `test_employee_defaults_from_job_and_department`, `test_employee_number_unique_per_company`, `test_branch_hierarchy`, `test_practitioner_link_resolution`, `test_onboarding_checklist`, `test_branch_rule_for_officer`, `test_multi_company_isolation` |
| Contract | `test_start_probation_and_alerts`, `test_review_never_terminates`, `test_review_pass_and_extend`, `test_renew_contract`, `test_under_contract_check` |
| Training | `test_applies_to`, `test_generation_idempotent`, `test_generation_skips_compliant_employee`, `test_completion_creates_credential`, `test_completion_renews_existing_credential`, `test_completion_requires_certificate`, `test_expiry_marking_and_compliance_flag`, `test_compliance_report`, `test_waiver_counts_as_compliant`, `test_alerts_idempotent`, `test_unique_open_assignment`, `test_self_service_rule`, `test_training_officer_completes_training` |
| Appraisal | `test_template_loading_by_category`, `test_job_template_wins_and_reload`, `test_template_weights_must_sum_to_100`, `test_weighted_score`, `test_attendance_kpi_from_shifts`, `test_training_compliance_from_credentials`, `test_no_side_effect_on_contracts`, `test_employee_cannot_rate_himself` |
| Recruitment | `test_stage_placed_before_hiring`, `test_required_credentials_default_from_job`, `test_verification_gate`, `test_failed_verification_blocks`, `test_expired_or_empty_line_cannot_be_verified`, `test_employee_creation_copies_data`, `test_create_employee_requires_verification`, `test_recruitment_officer_uses_standard_recruitment` |
| Clearance | `test_full_exit_flow`, `test_configurable_end_of_service`, `test_pending_inputs_in_settlement`, `test_block_requires_note_and_responsible` |
| Dashboard | `test_kpis_and_drilldown`, `test_payroll_tiles_hidden_for_non_payroll` |

### Not covered by automated tests

- Bank API sending (only the file-only refusal is tested; no provider exists).
- Vendor pull adapters other than the generic JSON one (they raise a not-implemented message by design).
- The PDF final settlement report rendering and the dashboard form layout.
- Performance at 5,000+ employees (no load test is shipped).
- The Arabic translation completeness.

These are covered by the manual checklist below or listed as limitations in the README.

## 4. Manual UAT checklist

Run on a copy of the demo database (or `healthcare_hr` itself) with users for each role. The complete
end-to-end scenario is described step by step in
[USER_GUIDE.md](USER_GUIDE.md#10-acceptance-scenario-walkthrough). Tick each line; record the tester
and date.

### Installation and upgrade

- [ ] `scripts/upgrade.sh` on all 16 modules finishes without errors or warnings from the suite
- [ ] A second upgrade creates no duplicate demo records (shifts, attendances, inputs, payslips)
- [ ] The **Healthcare HR** app opens for `admin`; the menu matches USER_GUIDE section 1
- [ ] Switching the user language to Arabic shows translated labels for the translated modules and an RTL layout

### Organisation and security

- [ ] An HR Officer limited to Branch 1 does not see Branch 2 employees; limited to Hospital A they see both
- [ ] An HR Manager and a Hospital Director see every branch
- [ ] A Department Manager of ICU sees ICU shifts and swaps, cannot open Payroll menus, loans or wages
- [ ] A plain employee sees only their own shifts, credentials, training and on-call duties
- [ ] Confidential credential types (passport, permits, malpractice insurance) are hidden from a Department Manager
- [ ] A user of a second company sees none of the first company's healthcare records

### Contracts, probation and credentials

- [ ] Start Probation requires a probation end date; employee status becomes *On Probation*
- [ ] Contract alert cron raises one activity per threshold, never duplicates on a second run
- [ ] Probation review *Recommend Termination* does not archive the employee
- [ ] Contract renewal creates a new version the day after the old end; *Non Renewable* is refused
- [ ] Credential statuses: valid, expiring, expired, missing, under verification behave as documented
- [ ] Editing the number of a verified credential resets the verification

### Scheduling

- [ ] Generate Shifts skips existing shifts; Publish Roster shows shortages and respects *Block publication*
- [ ] Each validation check refuses the shift with a readable reason (use the table in USER_GUIDE section 3)
- [ ] Publish Anyway is visible only to Scheduling Managers and requires an override reason, logged in the chatter
- [ ] Approving a leave over a published shift moves it to *Conflict* and removes its Planning slot
- [ ] Published shifts appear in the Planning Gantt at the right local times (check an Africa/Cairo employee)
- [ ] Shift swap: request, accept, manager approve, apply; an unqualified colleague is refused
- [ ] Coverage Status and the shortage alert match the coverage rules

### Attendance and biometric

- [ ] Push endpoint: a correct request returns `status: ok`; wrong token 403; missing headers 401; invalid JSON 400
- [ ] CSV import with a duplicate row and an unknown code gives the documented counters and a *Partial* batch
- [ ] Re-importing the same file creates nothing
- [ ] Fixing a mapping then **Retry** processes the failed log
- [ ] Late, early leave, missing checkout, unplanned and on-leave statuses appear as documented
- [ ] Reconciliation: proposed overtime above the 30-minute threshold only; approved overtime cannot exceed worked extra time; approval locks the shift

### Allowances, payroll, loans and bank

- [ ] Allowance computation counts only approved shifts and approved on-call duties; recomputing changes nothing
- [ ] Generate Inputs twice: no duplicate input; processing keys are unique
- [ ] A payslip shows the `HC_` inputs and salary lines; a second payslip in the same period gets none
- [ ] Validating the payslip marks inputs paid, allowances in payroll, shifts payroll posted; cancelling releases them
- [ ] A structure without healthcare rules gets them with **Add Healthcare Input Rules** (idempotent)
- [ ] Loan: approve, mark paid, installment deducted through the payslip, postpone, early settlement
- [ ] Bank batch: missing or untrusted accounts block the export; CSV, TXT and XLSX files open correctly in the bank's format; Confirm Payment marks payslips paid

### Talent

- [ ] Training cron creates missing assignments only; completing a training creates or renews the credential
- [ ] Training Compliance report shows the expected rate by department
- [ ] Appraisal loads the right KPI template; automatic KPIs fill; the employee cannot edit their own KPIs; contracts unchanged
- [ ] An applicant cannot be hired or converted to employee before credential verification; after conversion the credentials and onboarding exist

### Exit

- [ ] Start Clearance creates one item per clearance department with activities
- [ ] Only the responsible user (or an HR Officer) can clear an item; Block needs a note
- [ ] Final settlement lines match the configured components; End of Service follows the configured formula
- [ ] HR Approve & Archive ends the contract, cancels future shifts and archives the employee
- [ ] The final settlement PDF prints

### Dashboard and reports

- [ ] Every dashboard tile opens the filtered records it counts; the branch filter applies
- [ ] Payroll tiles are hidden for non-payroll users
- [ ] All reports under **Reports** open and can be grouped and exported

### Scheduled actions

- [ ] Each cron in ARCHITECTURE section 12 runs manually without error and a second run creates no duplicate alerts
