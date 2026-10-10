from odoo import models

from .shift_assignment import ACTIVE_STATES


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def _validate_leave_request(self):
        """Flag published shifts that an approved leave now overlaps (never deletes them)."""
        res = super()._validate_leave_request()
        Assignment = self.env['healthcare.shift.assignment'].sudo()
        for leave in self:
            shifts = Assignment.search([
                ('employee_id', '=', leave.employee_id.id), ('state', 'in', ('published', 'confirmed')),
                ('datetime_start', '<', leave.date_to), ('datetime_end', '>', leave.date_from)])
            for shift in shifts:
                shift.write({'state': 'conflict', 'conflict_reason': self.env._(
                    'Approved leave %(leave)s overlaps this shift.', leave=leave.display_name)})
                shift.planning_slot_id.unlink()
            self.env['healthcare.hr.alert'].schedule(
                shifts, 'leave_conflict', self.env._('Shift uncovered by approved leave'))
        return res
