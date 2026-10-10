from odoo import api, models

EARNING_SEQUENCE = 60
DEDUCTION_SEQUENCE = 190


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'

    def action_hc_add_healthcare_rules(self):
        """Add one salary rule per healthcare input type (idempotent).

        Earnings go to the ALW category (included in gross), deductions to DED with a negative
        amount. Taxes stay with the country localisation of the structure.
        """
        input_types = self.env['hr.payslip.input.type'].search([('healthcare_source_type', '!=', False)])
        alw = self.env.ref('hr_payroll.ALW')
        ded = self.env.ref('hr_payroll.DED')
        Rule = self.env['hr.salary.rule']
        for struct in self:
            existing = set(struct.rule_ids.mapped('code'))
            vals_list = []
            for index, input_type in enumerate(input_types.sorted('id')):
                if input_type.code in existing:
                    continue
                deduction = input_type.healthcare_is_deduction
                vals_list.append({
                    'struct_id': struct.id,
                    'name': input_type.name,
                    'code': input_type.code,
                    'sequence': (DEDUCTION_SEQUENCE if deduction else EARNING_SEQUENCE) + index,
                    'category_id': (ded if deduction else alw).id,
                    'condition_select': 'input',
                    'condition_other_input_id': input_type.id,
                    'amount_select': 'code',
                    'amount_python_compute': "result = %sinputs['%s'].amount\nresult_name = inputs['%s'].name" % (
                        '-' if deduction else '', input_type.code, input_type.code),
                })
            Rule.create(vals_list)
        return True

    @api.model
    def _hc_install_rules_on_default_structures(self):
        structures = self.env.ref('hr_payroll.structure_002', raise_if_not_found=False)
        if structures:
            structures.action_hc_add_healthcare_rules()
