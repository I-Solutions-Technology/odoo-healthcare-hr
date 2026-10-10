from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    probation_status = fields.Selection(related='version_id.probation_status', inherited=True,
                                        readonly=False, groups='hr.group_hr_user')
    probation_start_date = fields.Date(related='version_id.probation_start_date', inherited=True,
                                       readonly=False, groups='hr.group_hr_user')
    renewal_type = fields.Selection(related='version_id.renewal_type', inherited=True,
                                    readonly=False, groups='hr.group_hr_user')
    medical_license_required = fields.Boolean(related='version_id.medical_license_required', inherited=True,
                                              readonly=False, groups='hr.group_hr_user')
    professional_license_required = fields.Boolean(related='version_id.professional_license_required',
                                                   inherited=True, readonly=False, groups='hr.group_hr_user')
    insurance_required = fields.Boolean(related='version_id.insurance_required', inherited=True,
                                        readonly=False, groups='hr.group_hr_user')

    def _hc_is_under_contract(self, on_date):
        """True when the employee has a contract covering ``on_date``.

        Contract dates are restricted to HR managers in Odoo 19, so the check reads them
        with sudo; nothing is written.
        """
        self.ensure_one()
        version = self.sudo()._get_version(on_date)
        if not version or not version.contract_date_start:
            return False
        return version.contract_date_start <= on_date and (
            not version.contract_date_end or version.contract_date_end >= on_date)

    def action_hc_start_probation(self):
        self.ensure_one()
        self.version_id.action_start_probation()

    def action_hc_probation_review(self):
        self.ensure_one()
        return self.version_id.action_create_probation_review()

    def action_hc_renew_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Renew Contract'),
            'res_model': 'healthcare.hr.contract.renew.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'active_model': 'hr.employee'},
        }
