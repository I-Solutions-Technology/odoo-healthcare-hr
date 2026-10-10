from collections import defaultdict
from datetime import timedelta

from odoo import api, models

from .shift_assignment import ACTIVE_STATES


class ShiftValidator(models.AbstractModel):
    """Validation engine run before publishing shifts and before applying swaps.

    Works in batch: every lookup (other shifts, leaves, contracts, credentials) is done with
    a handful of queries for the whole recordset, never per assignment. Reads are sudo'd
    because schedulers must be able to validate without seeing leave or contract details;
    only the human-readable reasons are returned.
    """
    _name = 'healthcare.shift.validator'
    _description = 'Shift Validation Engine'

    @api.model
    def _validate(self, assignments, employee_override=None, exclude_ids=()):
        """Return {assignment_id: [messages]} for assignments with at least one issue.

        :param employee_override: {assignment_id: hr.employee} to validate a hypothetical
                                  assignee (shift swaps)
        :param exclude_ids: assignment ids ignored as "other shifts" (the swapped shifts)
        """
        _ = self.env._
        employee_override = employee_override or {}
        assignments = assignments.sudo()
        if not assignments:
            return {}

        def employee_of(rec):
            return employee_override.get(rec.id, rec.employee_id)

        employees = assignments.mapped('employee_id')
        for employee in employee_override.values():
            employees |= employee.sudo()
        min_start = min(assignments.mapped('datetime_start'))
        max_end = max(assignments.mapped('datetime_end'))
        horizon_start = min_start - timedelta(days=8)
        horizon_end = max_end + timedelta(days=8)
        own_ids = set(assignments.ids) | set(exclude_ids)
        batch_ids = set(assignments.ids)

        # Other shifts of the same employees around the period (1 query)
        others = self.env['healthcare.shift.assignment'].sudo().search([
            ('employee_id', 'in', employees.ids), ('id', 'not in', list(own_ids)),
            ('state', 'in', ACTIVE_STATES),
            ('datetime_start', '<', horizon_end), ('datetime_end', '>', horizon_start),
        ])
        # Batch members also constrain each other
        by_employee = defaultdict(list)
        for other in others:
            by_employee[other.employee_id.id].append(other)
        for rec in assignments:
            by_employee[employee_of(rec).id].append(rec)

        # Approved leaves (1 query)
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', employees.ids), ('state', '=', 'validate'),
            ('date_from', '<', max_end), ('date_to', '>', min_start),
        ])
        leaves_by_employee = defaultdict(list)
        for leave in leaves:
            leaves_by_employee[leave.employee_id.id].append(leave)

        # Blocking credentials, per shift date (1 query per distinct date)
        blockers = {}
        for day in set(assignments.mapped('date')):
            blockers[day] = employees._hc_credential_blockers(day)

        issues = defaultdict(list)
        for rec in assignments:
            employee = employee_of(rec)
            template = rec.shift_template_id
            company = rec.company_id
            start, end = rec.datetime_start, rec.datetime_end
            msg = issues[rec.id]

            if not employee.active:
                msg.append(_('%s is archived.', employee.name))
            # Contract
            if not employee._hc_is_under_contract(rec.date):
                msg.append(_('%(name)s has no active contract on %(date)s (inactive or expired).',
                             name=employee.name, date=rec.date))
            # Leave
            for leave in leaves_by_employee.get(employee.id, []):
                if leave.date_from < end and leave.date_to > start:
                    msg.append(_('%(name)s is on approved leave (%(type)s) from %(from)s to %(to)s.',
                                 name=employee.name, type=leave.holiday_status_id.name,
                                 **{'from': leave.date_from, 'to': leave.date_to}))
            # Credentials
            blocked = blockers.get(rec.date, {}).get(employee.id)
            if blocked:
                msg.append(_('%(name)s has no valid %(types)s on %(date)s.',
                             name=employee.name, types=', '.join(blocked), date=rec.date))
            # Pattern / qualification
            if template.job_ids and employee.job_id not in template.job_ids:
                msg.append(_('%(name)s (%(job)s) is not qualified for the "%(shift)s" shift.',
                             name=employee.name, job=employee.job_id.name or '-', shift=template.name))
            if template.branch_id and rec.branch_id and not rec.branch_id.parent_path.startswith(
                    template.branch_id.parent_path):
                msg.append(_('The "%(shift)s" shift belongs to branch %(branch)s.',
                             shift=template.name, branch=template.branch_id.name))
            # Weekend / 24h authorisation
            if rec.date.weekday() in company._hc_weekend_days() and not employee.weekend_work_allowed:
                msg.append(_('%s is not authorised to work on weekends.', employee.name))
            duration = (end - start).total_seconds() / 3600.0
            if (template.shift_type == 'twenty_four_hour' or duration >= 24) and not employee.allow_24h_shift:
                msg.append(_('%s is not authorised for 24-hour shifts.', employee.name))
            if company.hc_max_shift_hours and duration > company.hc_max_shift_hours:
                msg.append(_('The shift lasts %(hours).1f h, above the %(max).1f h limit.',
                             hours=duration, max=company.hc_max_shift_hours))

            # Overlaps, duplicates, other branch, rest, weekly hours
            week_start = rec.date - timedelta(days=rec.date.weekday())
            week_end = week_start + timedelta(days=7)
            week_hours = 0.0
            for other in by_employee[employee.id]:
                if other.id == rec.id:
                    continue
                if week_start <= other.date < week_end:
                    week_hours += other.planned_hours
                # inside a batch, the earlier record wins: only the later one reports the clash
                if other.id in batch_ids and other.id > rec.id:
                    continue
                if other.shift_template_id == template and other.date == rec.date:
                    msg.append(_('Duplicate assignment: %(name)s already has the "%(shift)s" shift on %(date)s.',
                                 name=employee.name, shift=template.name, date=rec.date))
                    continue
                if other.datetime_start < end and other.datetime_end > start:
                    if other.branch_id and rec.branch_id and other.branch_id != rec.branch_id:
                        msg.append(_('%(name)s is assigned to branch %(branch)s at the same time (%(shift)s).',
                                     name=employee.name, branch=other.branch_id.name, shift=other.name))
                    else:
                        msg.append(_('Overlaps with %s.', other.name))
                    continue
                # Rest between consecutive shifts
                if other.datetime_end <= start:
                    gap = (start - other.datetime_end).total_seconds() / 3600.0
                    required = other.shift_template_id.minimum_rest_hours or company.hc_default_rest_hours
                    if gap < required:
                        msg.append(_('Only %(gap).1f h rest after %(other)s (minimum %(req).1f h).',
                                     gap=gap, other=other.name, req=required))
                elif other.datetime_start >= end:
                    gap = (other.datetime_start - end).total_seconds() / 3600.0
                    required = template.minimum_rest_hours or company.hc_default_rest_hours
                    if gap < required:
                        msg.append(_('Only %(gap).1f h rest before %(other)s (minimum %(req).1f h).',
                                     gap=gap, other=other.name, req=required))
            max_hours = employee.max_weekly_hours or company.hc_max_weekly_hours
            if max_hours and week_hours + rec.planned_hours > max_hours:
                msg.append(_('%(name)s would work %(hours).1f h in the week of %(week)s (limit %(max).1f h).',
                             name=employee.name, hours=week_hours + rec.planned_hours, week=week_start, max=max_hours))
        return {key: value for key, value in issues.items() if value}
