import base64

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.healthcare_hr_payroll.tests.common import PayrollCommon


@tagged('post_install', '-at_install', 'healthcare')
class TestBank(PayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bank = cls.env['res.bank'].create({'name': 'Test Bank', 'bic': 'TESTEGCX'})
        account = cls.env['res.partner.bank'].create({
            'acc_number': 'EG380019000500000000263180002', 'partner_id': cls.nurse.work_contact_id.id,
            'bank_id': bank.id, 'allow_out_payment': True})
        cls.nurse.bank_account_ids = account
        cls.slips = cls._payslip(cls, cls.nurse) | cls._payslip(cls, cls.doctor)
        cls.slips.action_payslip_done()

    def _batch(self, layout_xmlid='healthcare_hr_bank.layout_generic_csv'):
        batch = self.env['healthcare.payroll.bank.batch'].create({
            'layout_id': self.env.ref(layout_xmlid).id, 'date_from': self.date_from, 'date_to': self.date_to})
        batch.action_generate_lines()
        return batch

    def test_missing_bank_account_blocks_export(self):
        batch = self._batch()
        self.assertEqual(batch.error_count, 1, "the doctor has no bank account")
        with self.assertRaises(UserError):
            batch.action_export()
        batch.line_ids.filtered(lambda l: l.state == 'error').unlink()
        batch.action_export()
        self.assertEqual(batch.state, 'exported')

    def test_csv_content(self):
        batch = self._batch()
        batch.line_ids.filtered(lambda l: l.state == 'error').unlink()
        batch.action_export()
        content = base64.b64decode(batch.export_file).decode('utf-8-sig')
        self.assertIn('EG380019000500000000263180002', content)
        self.assertIn(f'{self.slips.filtered(lambda s: s.employee_id == self.nurse).net_wage:.2f}', content)
        self.assertTrue(batch.export_filename.endswith('.csv'))

    def test_fixed_width_and_xlsx(self):
        batch = self._batch('healthcare_hr_bank.layout_fixed_txt')
        batch.line_ids.filtered(lambda l: l.state == 'error').unlink()
        batch.action_export()
        line = base64.b64decode(batch.export_file).decode().splitlines()[0]
        self.assertEqual(len(line), 1 + 34 + 15 + 35 + 8 + 20)
        batch_x = self._batch('healthcare_hr_bank.layout_generic_xlsx')
        self.assertNotIn(self.nurse, batch_x.line_ids.employee_id,
                         "payslips already in an active batch are not exported twice")
        batch.action_cancel()
        batch_x.action_generate_lines()
        batch_x.line_ids.filtered(lambda l: l.state == 'error').unlink()
        batch_x.action_export()
        self.assertEqual(base64.b64decode(batch_x.export_file)[:2], b'PK')

    def test_done_marks_payslips_paid(self):
        batch = self._batch()
        batch.line_ids.filtered(lambda l: l.state == 'error').unlink()
        batch.action_export()
        with self.assertRaises(UserError):
            batch.action_send_to_bank()
        batch.action_mark_sent()
        batch.action_done()
        self.assertEqual(batch.line_ids.payslip_id.state, 'paid')

    def test_bank_data_restricted(self):
        manager = self._user('dept_mgr_bank', 'healthcare_hr_core.group_hc_department_manager')
        self.assertFalse(self.env['healthcare.payroll.bank.batch'].with_user(manager).has_access('read'))
