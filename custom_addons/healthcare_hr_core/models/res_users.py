from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    healthcare_branch_ids = fields.Many2many(
        'healthcare.hr.branch', 'healthcare_branch_res_users_rel', 'user_id', 'branch_id',
        string='Allowed Healthcare Branches',
        help="Branch-level record rules restrict Healthcare HR officers and schedulers to these "
             "branches (and their sub-branches). Leave empty to allow every branch.")

    def write(self, vals):
        res = super().write(vals)
        if 'healthcare_branch_ids' in vals:
            # Record rules are cached per user: branch changes must invalidate them.
            self.env.registry.clear_cache()
        return res
