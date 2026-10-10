from odoo import api, fields, models
from odoo.exceptions import UserError


class ShiftSwap(models.Model):
    """Swap (or hand over) a shift between two employees.

    Draft -> Requested -> Accepted by colleague -> Manager approved -> Applied
    (the last step is the HR / scheduling approval, which applies the swap).
    Every step re-runs the validation engine on the hypothetical result.
    """
    _name = 'healthcare.shift.swap'
    _description = 'Shift Swap'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _check_company_auto = True

    name = fields.Char(default=lambda self: self.env._('New'), readonly=True, copy=False)
    requester_assignment_id = fields.Many2one(
        'healthcare.shift.assignment', string='Shift to Give', required=True, check_company=True, tracking=True,
        domain="[('state', 'in', ('published', 'confirmed'))]")
    requester_employee_id = fields.Many2one(related='requester_assignment_id.employee_id', store=True,
                                            string='Requester')
    target_employee_id = fields.Many2one('hr.employee', string='Colleague', required=True, check_company=True,
                                         tracking=True)
    target_assignment_id = fields.Many2one(
        'healthcare.shift.assignment', string='Shift to Take', check_company=True, tracking=True,
        domain="[('employee_id', '=', target_employee_id), ('state', 'in', ('published', 'confirmed'))]",
        help="Leave empty for a one-way hand-over.")
    company_id = fields.Many2one(related='requester_assignment_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='requester_assignment_id.branch_id', store=True)
    department_id = fields.Many2one(related='requester_assignment_id.department_id', store=True)
    reason = fields.Text(required=True)
    validation_message = fields.Text(readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('accepted', 'Colleague Accepted'),
        ('manager_approved', 'Manager Approved'),
        ('applied', 'Applied'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)
    refuse_reason = fields.Char(tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._('New')) == self.env._('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('healthcare.shift.swap') or '/'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def _check_swap(self):
        """Validate the hypothetical swapped roster; raise with the reasons if invalid."""
        self.ensure_one()
        _ = self.env._
        messages = []
        give, take = self.requester_assignment_id, self.target_assignment_id
        requester, target = self.requester_employee_id, self.target_employee_id
        if requester == target:
            raise UserError(_('Choose a different colleague.'))
        # Qualification and department eligibility
        if requester.employee_category and target.employee_category != requester.employee_category:
            messages.append(_('%(target)s is not in the same healthcare category as %(req)s.',
                              target=target.name, req=requester.name))
        departments = target.department_id | target.medical_department_id
        if give.department_id and give.department_id not in departments:
            messages.append(_('%(target)s does not belong to %(dept)s.', target=target.name, dept=give.department_id.name))
        override = {give.id: target}
        records = give
        if take:
            override[take.id] = requester
            records |= take
        issues = self.env['healthcare.shift.validator']._validate(
            records, employee_override=override, exclude_ids=records.ids)
        for rec in records:
            messages += issues.get(rec.id, [])
        self.validation_message = '\n'.join(messages) or False
        if messages:
            raise UserError(_('The swap is not possible:\n%s', '\n'.join(messages)))

    def action_request(self):
        for swap in self:
            swap._check_swap()
            swap.state = 'requested'
            if swap.target_employee_id.user_id:
                swap.activity_schedule('mail.mail_activity_data_todo', user_id=swap.target_employee_id.user_id.id,
                                       summary=self.env._('Shift swap request from %s', swap.requester_employee_id.name))

    def action_accept(self):
        for swap in self.filtered(lambda s: s.state == 'requested'):
            if self.env.user != swap.target_employee_id.user_id and not self.env.user.has_group(
                    'healthcare_hr_core.group_hc_scheduling_officer'):
                raise UserError(self.env._('Only %s can accept this swap.', swap.target_employee_id.name))
            swap._check_swap()
            swap.state = 'accepted'
            swap.activity_feedback(['mail.mail_activity_data_todo'])

    def action_manager_approve(self):
        for swap in self.filtered(lambda s: s.state == 'accepted'):
            if not swap._is_manager() and not self.env.user.has_group('healthcare_hr_core.group_hc_scheduling_manager'):
                raise UserError(self.env._('Only the department manager can approve this swap.'))
            swap._check_swap()
            swap.state = 'manager_approved'

    def action_apply(self):
        """HR / scheduling approval: re-validate and swap the assignees."""
        if not self.env.user.has_group('healthcare_hr_core.group_hc_scheduling_officer'):
            raise UserError(self.env._('Only scheduling officers can apply swaps.'))
        for swap in self.filtered(lambda s: s.state == 'manager_approved'):
            swap._check_swap()
            give, take = swap.requester_assignment_id.sudo(), swap.target_assignment_id.sudo()
            requester, target = swap.requester_employee_id, swap.target_employee_id
            give.write({'employee_id': target.id})
            give.message_post(body=self.env._('Swapped from %(a)s to %(b)s (%(swap)s).',
                                              a=requester.name, b=target.name, swap=swap.name))
            if take:
                take.write({'employee_id': requester.id})
                take.message_post(body=self.env._('Swapped from %(a)s to %(b)s (%(swap)s).',
                                                  a=target.name, b=requester.name, swap=swap.name))
            swap.state = 'applied'

    def action_refuse(self):
        self.write({'state': 'refused'})

    def action_cancel(self):
        self.filtered(lambda s: s.state != 'applied').write({'state': 'cancelled'})

    def _is_manager(self):
        self.ensure_one()
        user = self.env.user
        return user in (self.department_id.manager_id.user_id | self.requester_employee_id.parent_id.user_id)

    @api.model
    def _cron_pending_swap_alerts(self):
        pending = self.sudo().search([('state', 'in', ('accepted', 'manager_approved'))])
        Alert = self.env['healthcare.hr.alert']
        for swap in pending:
            user = (swap.department_id.manager_id.user_id if swap.state == 'accepted' else None)
            Alert.schedule(swap, f'swap_{swap.id}_{swap.state}',
                           self.env._('Pending shift swap %s awaiting approval', swap.name),
                           user=user or None, employee_field='requester_employee_id')
        return True
