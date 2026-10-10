from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.healthcare_hr_payroll.tests.common import PayrollCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestLoan(PayrollCommon):

    def _loan(self, amount=3000, count=3, loan_type='loan'):
        loan = self.env['healthcare.hr.loan'].create({
            'employee_id': self.nurse.id, 'requested_amount': amount, 'installment_count': count,
            'first_deduction_date': self.date_to, 'loan_type': loan_type})
        loan.action_submit()
        loan.action_approve()
        loan.action_mark_paid()
        return loan

    def test_schedule(self):
        loan = self._loan(1000, 3)
        self.assertEqual(loan.installment_ids.mapped('amount'), [333.33, 333.33, 333.34])
        self.assertEqual(loan.installment_ids[0].due_date, self.date_to)
        self.assertEqual(loan.state, 'active')
        self.assertEqual(loan.remaining_amount, 1000)

    def test_installment_through_payroll(self):
        loan = self._loan(3000, 3)
        first = loan.installment_ids[0]
        inputs = self.Input._generate_for_period(self.date_from, self.date_to)
        self.Input._generate_for_period(self.date_from, self.date_to)
        loan_inputs = inputs.filtered(lambda i: i.source_type == 'loan_installment')
        self.assertEqual(len(loan_inputs), 1, "only the installment due in the period, once")
        self.assertEqual((loan_inputs.amount, loan_inputs.source_res_id), (1000.0, first.id))
        slip = self._payslip(self.nurse)
        self.assertEqual({l.code: l.total for l in slip.line_ids}.get('HC_LOAN'), -1000.0)
        self.assertEqual(first.state, 'included')
        slip.action_payslip_done()
        self.assertEqual(first.state, 'paid')
        self.assertEqual(loan.remaining_amount, 2000.0)
        slip.action_payslip_cancel()
        self.assertEqual(first.state, 'pending')
        self.assertEqual(loan.remaining_amount, 3000.0)

    def test_completion_and_settlement(self):
        loan = self._loan(1000, 2)
        loan.action_settle()
        self.assertEqual(loan.state, 'completed')
        self.assertEqual(loan.remaining_amount, 0.0)

    def test_postpone(self):
        loan = self._loan(1000, 2)
        first = loan.installment_ids[0]
        first.action_postpone()
        self.assertGreater(first.due_date, loan.installment_ids[1].due_date)
        self.assertFalse(self.Input._generate_for_period(self.date_from, self.date_to).filtered(
            lambda i: i.source_type == 'loan_installment'))

    def test_advance_limit(self):
        with self.assertRaises(ValidationError):
            self._loan(1000, 6, 'advance')

    def test_self_service_access(self):
        user = self._user('nurse_loan_user', 'base.group_user')
        self.nurse.user_id = user
        loan = self.env['healthcare.hr.loan'].with_user(user).create({
            'employee_id': self.nurse.id, 'requested_amount': 500, 'installment_count': 1,
            'first_deduction_date': self.date_to})
        loan.with_user(user).action_submit()
        self.assertEqual(loan.state, 'submitted')
        other = self.env['healthcare.hr.loan'].create({
            'employee_id': self.doctor.id, 'requested_amount': 500, 'installment_count': 1,
            'first_deduction_date': self.date_to})
        self.assertFalse(self.env['healthcare.hr.loan'].with_user(user).search([('id', '=', other.id)]))
