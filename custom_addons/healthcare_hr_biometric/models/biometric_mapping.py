from odoo import api, fields, models


class HealthcareBiometricEmployeeMapping(models.Model):
    _name = 'healthcare.biometric.employee.mapping'
    _description = 'Biometric Employee Mapping'
    _order = 'device_id, device_employee_code'
    _rec_name = 'device_employee_code'

    device_id = fields.Many2one('healthcare.biometric.device', index=True, ondelete='cascade',
                                domain="[('company_id', '=', company_id)]",
                                help="Leave empty to use this code on every device of the company. "
                                     "A device-specific mapping always wins over a company-wide one.")
    device_employee_code = fields.Char(string='Device Employee Code', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True, ondelete='cascade',
                                  domain="[('company_id', 'in', (company_id, False))]")
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 compute='_compute_company_id', store=True, readonly=False, precompute=True)
    branch_id = fields.Many2one('healthcare.hr.branch', compute='_compute_branch_id', store=True, index=True)
    active = fields.Boolean(default=True)

    _device_code_uniq = models.Constraint(
        'unique (device_id, device_employee_code)', 'This employee code is already mapped on this device.')
    _company_code_uniq = models.UniqueIndex(
        '(company_id, device_employee_code) WHERE device_id IS NULL',
        'This employee code already has a company-wide mapping.')

    @api.depends('device_id', 'employee_id')
    def _compute_company_id(self):
        for mapping in self:
            mapping.company_id = (mapping.device_id.company_id or mapping.employee_id.company_id
                                  or mapping.company_id or self.env.company)

    @api.depends('device_id.branch_id', 'employee_id.healthcare_branch_id')
    def _compute_branch_id(self):
        for mapping in self:
            mapping.branch_id = mapping.device_id.branch_id or mapping.employee_id.healthcare_branch_id

    @api.model
    def _resolve(self, device, codes):
        """Map device employee codes to employees: device-specific mapping first, then company-wide.

        :return: dict {code: hr.employee}
        """
        codes = [c for c in set(codes) if c]
        if not codes:
            return {}
        mappings = self.sudo().search([
            ('device_employee_code', 'in', codes), ('company_id', '=', device.company_id.id),
            '|', ('device_id', '=', device.id), ('device_id', '=', False),
        ])
        result = {}
        # company-wide first, then overwritten by the device-specific mapping
        for mapping in mappings.sorted(lambda m: bool(m.device_id)):
            result[mapping.device_employee_code] = mapping.employee_id
        return result
