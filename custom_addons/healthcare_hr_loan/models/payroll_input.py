from odoo import api, models


class PayrollInput(models.Model):
    _inherit = 'healthcare.payroll.input'

    @api.model
    def _hc_collect_sources(self, date_from, date_to, company, employees=None):
        vals_list = super()._hc_collect_sources(date_from, date_to, company, employees)
        domain = [('company_id', '=', company.id), ('loan_id.state', '=', 'active'), ('state', '=', 'pending'),
                  ('due_date', '>=', date_from), ('due_date', '<=', date_to)]
        if employees:
            domain.append(('employee_id', 'in', employees.ids))
        for inst in self.env['healthcare.hr.loan.installment'].sudo().search(domain):
            source_type = 'advance' if inst.loan_id.loan_type == 'advance' else 'loan_installment'
            vals_list.append({
                'name': self.env._('%(loan)s installment %(seq)s', loan=inst.loan_id.name, seq=inst.sequence),
                'employee_id': inst.employee_id.id, 'company_id': company.id,
                'date_from': date_from, 'date_to': date_to, 'source_type': source_type,
                'input_type_id': self._input_type_for(source_type).id, 'quantity': 1, 'amount': inst.amount,
                'source_model': inst._name, 'source_res_id': inst.id,
                'processing_key': f'loan_installment:{inst.id}',
            })
        return vals_list

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda r: r.source_model == 'healthcare.hr.loan.installment'):
            self.env['healthcare.hr.loan.installment'].sudo().browse(record.source_res_id).payroll_input_id = record
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            installments = self.env['healthcare.hr.loan.installment'].sudo().browse(
                self.filtered(lambda r: r.source_model == 'healthcare.hr.loan.installment').mapped('source_res_id'))
            if vals['state'] == 'included':
                installments.filtered(lambda i: i.state in ('pending', 'paid') and not i.settled).write(
                    {'state': 'included'})
            elif vals['state'] == 'confirmed':
                installments.filtered(lambda i: i.state in ('included', 'paid') and not i.settled).write(
                    {'state': 'pending'})
                installments.loan_id.filtered(lambda l: l.state == 'completed').write({'state': 'active'})
        return res

    def _hc_mark_sources_processed(self):
        res = super()._hc_mark_sources_processed()
        installments = self.env['healthcare.hr.loan.installment'].sudo().browse(
            self.filtered(lambda r: r.source_model == 'healthcare.hr.loan.installment').mapped('source_res_id'))
        installments.write({'state': 'paid'})
        installments.loan_id._check_completion()
        return res
