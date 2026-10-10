from odoo import api, fields, models
from odoo.fields import Command


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    healthcare_branch_id = fields.Many2one(related='employee_id.healthcare_branch_id', store=True, string='Branch')
    healthcare_input_ids = fields.One2many('healthcare.payroll.input', 'payslip_id', string='Healthcare Inputs',
                                           readonly=True)

    def _hc_available_inputs(self):
        """Confirmed inputs of the employee whose period ends inside the payslip period."""
        self.ensure_one()
        if not self.employee_id or not self.date_from or not self.date_to:
            return self.env['healthcare.payroll.input']
        own_id = self._origin.id or False
        return self.env['healthcare.payroll.input'].sudo().search([
            ('employee_id', '=', self.employee_id.id), ('company_id', '=', self.company_id.id),
            ('date_to', '>=', self.date_from), ('date_to', '<=', self.date_to),
            '|', ('state', '=', 'confirmed'), '&', ('state', '=', 'included'), ('payslip_id', '=', own_id),
        ])

    @api.depends('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to')
    def _compute_input_line_ids(self):
        super()._compute_input_line_ids()
        healthcare_types = self.env['hr.payslip.input.type'].search([('healthcare_source_type', '!=', False)])
        for slip in self:
            # drop the lines this method added previously, then rebuild them
            commands = [Command.unlink(line.id) for line in slip.input_line_ids
                        if line.input_type_id in healthcare_types]
            inputs = slip._hc_available_inputs()
            for input_type, records in inputs.grouped('input_type_id').items():
                if input_type.struct_ids and slip.struct_id not in input_type.struct_ids:
                    continue
                amount = sum(records.mapped('amount'))
                if slip.credit_note:
                    amount = -amount
                commands.append(Command.create({
                    'name': ', '.join(sorted(set(records.mapped('name'))))[:250],
                    'input_type_id': input_type.id,
                    'amount': amount,
                }))
            if commands:
                slip.update({'input_line_ids': commands})

    def compute_sheet(self):
        # link inputs before computing so they cannot be taken by another payslip
        for slip in self.filtered(lambda s: s.state == 'draft'):
            inputs = slip._hc_available_inputs()
            (slip.healthcare_input_ids - inputs).sudo().write({'state': 'confirmed', 'payslip_id': False})
            inputs.write({'state': 'included', 'payslip_id': slip.id})
        return super().compute_sheet()

    def action_payslip_done(self):
        res = super().action_payslip_done()
        inputs = self.healthcare_input_ids.sudo()
        inputs.write({'state': 'done'})
        inputs._hc_mark_sources_processed()
        self.env['healthcare.shift.assignment'].sudo().search([
            ('employee_id', 'in', self.employee_id.ids), ('state', '=', 'approved'),
            ('payroll_processed', '=', True)]).with_context(hc_allow_locked_write=True).write(
            {'state': 'payroll_posted'})
        return res

    def action_payslip_cancel(self):
        inputs = self.healthcare_input_ids.sudo()
        res = super().action_payslip_cancel()
        inputs._hc_release_sources()
        inputs.write({'state': 'confirmed', 'payslip_id': False})
        shifts = self.env['healthcare.shift.assignment'].sudo().search([
            ('employee_id', 'in', self.employee_id.ids), ('state', '=', 'payroll_posted'),
            ('payroll_processed', '=', False)])
        shifts.with_context(hc_allow_locked_write=True).write({'state': 'approved'})
        return res

    def action_payslip_draft(self):
        res = super().action_payslip_draft()
        inputs = self.healthcare_input_ids.sudo()
        inputs._hc_release_sources()
        inputs.write({'state': 'included'})
        return res
