import base64
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.healthcare_hr_biometric.models.biometric_device import hash_token
from odoo.addons.healthcare_hr_shift.tests.common import ShiftCommon

REQUESTS_GET = 'odoo.addons.healthcare_hr_biometric.models.biometric_device.requests.get'


@tagged('post_install', '-at_install', 'healthcare')
class TestBiometric(ShiftCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # past day (events in the future are rejected), covered by contract and credentials
        cls.day = cls.monday - timedelta(days=21)
        Device = cls.env['healthcare.biometric.device']
        cls.device = Device.create({'name': 'T Device 1', 'code': 'TDEV1', 'timezone': 'UTC',
                                    'connection_type': 'api_push', 'branch_id': cls.branch_1.id})
        cls.device_2 = Device.create({'name': 'T Device 2', 'code': 'TDEV2', 'timezone': 'UTC',
                                      'connection_type': 'file_import', 'branch_id': cls.branch_2.id})
        cls.Mapping = cls.env['healthcare.biometric.employee.mapping']
        cls.Mapping.create([
            {'device_id': cls.device.id, 'device_employee_code': 'N1', 'employee_id': cls.nurse.id},
            {'device_employee_code': 'D1', 'employee_id': cls.doctor.id},  # company-wide
        ])
        cls.Log = cls.env['healthcare.biometric.log']
        cls.Attendance = cls.env['hr.attendance']

    def _ts(self, hour, minute=0, day=None):
        return (self._dt(day or self.day, hour, minute)).strftime('%Y-%m-%d %H:%M:%S')

    def _ev(self, code, hour, minute=0, event_type='check_in', day=None):
        return {'employee_code': code, 'timestamp': self._ts(hour, minute, day), 'event_type': event_type}

    def _attendances(self, employee):
        return self.Attendance.search([('employee_id', '=', employee.id)])

    # ------------------------------------------------------------------
    def test_duplicate_event_in_batch_and_across_imports(self):
        event = self._ev('N1', 8)
        batch = self.device._import_events([event, dict(event)], 'push')
        self.assertEqual((batch.received_count, batch.created_count, batch.duplicate_count), (2, 1, 1))
        batch_2 = self.device._import_events([dict(event)], 'push')
        self.assertEqual((batch_2.received_count, batch_2.created_count, batch_2.duplicate_count), (1, 0, 1))
        self.assertEqual(batch_2.state, 'done')
        logs = self.Log.search([('device_id', '=', self.device.id)])
        self.assertEqual(len(logs), 1)
        logs._process()
        logs._process()
        self.assertEqual(len(self._attendances(self.nurse)), 1)
        self.assertEqual(logs.processing_status, 'done')
        self.assertTrue(logs.processed)

    def test_same_timestamp_on_other_device_is_not_a_duplicate(self):
        self.device._import_events([self._ev('D1', 8)], 'push')
        batch = self.device_2._import_events([self._ev('D1', 8)], 'file')
        self.assertEqual(batch.created_count, 1)
        (self.Log.search([('employee_id', '=', False), ('device_employee_code', '=', 'D1')]))._process()
        self.assertEqual(len(self._attendances(self.doctor)), 1, "the second punch is a duplicate check-in")

    def test_unknown_employee(self):
        batch = self.device._import_events([self._ev('X9', 8)], 'push')
        batch.log_ids._process()
        log = batch.log_ids
        self.assertEqual(log.processing_status, 'error')
        self.assertEqual(log.error_message, 'Unknown employee code X9 on device TDEV1')
        self.assertFalse(log.employee_id)
        self.assertFalse(log.attendance_id)
        self.assertFalse(self.Attendance.search([('check_in', '=', self._dt(self.day, 8))]))
        self.assertEqual((batch.failed_count, batch.state), (1, 'failed'))

    def test_valid_mapping_creates_attendance_matched_to_shift(self):
        shift = self._shift(self.nurse, self.t_morning, self.day, publish=True)
        batch = self.device._import_events(
            [self._ev('N1', 8, 5), self._ev('N1', 16, 0, 'check_out')], 'push')
        batch.log_ids._process()
        self.assertEqual(set(batch.log_ids.mapped('processing_status')), {'done'})
        attendance = self._attendances(self.nurse)
        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance.check_in, self._dt(self.day, 8, 5))
        self.assertEqual(attendance.check_out, self._dt(self.day, 16))
        self.assertEqual((attendance.in_mode, attendance.out_mode), ('kiosk', 'kiosk'))
        self.assertEqual(attendance.planned_shift_id, shift)
        self.assertEqual(batch.log_ids.attendance_id, attendance)
        self.assertEqual(batch.log_ids.employee_id, self.nurse)
        self.assertEqual((batch.success_count, batch.failed_count, batch.state), (2, 0, 'done'))

    def test_idempotent_import_and_process(self):
        events = [self._ev('N1', 8), self._ev('N1', 16, 0, 'check_out'),
                  self._ev('D1', 9), self._ev('D1', 17, 0, 'check_out'), self._ev('X9', 9)]

        def run():
            batch = self.device._import_events(events, 'push')
            self.Log.search([('device_id', '=', self.device.id)])._process()
            logs = self.Log.search([('device_id', '=', self.device.id)])
            return batch, (len(logs), sorted(logs.mapped('processing_status')),
                           len(self._attendances(self.nurse)), len(self._attendances(self.doctor)))

        batch_1, state_1 = run()
        batch_2, state_2 = run()
        self.assertEqual(state_1, state_2)
        self.assertEqual(state_1[0], 5)
        self.assertEqual((state_1[2], state_1[3]), (1, 1))
        self.assertEqual(batch_1.created_count, 5)
        self.assertEqual((batch_2.created_count, batch_2.duplicate_count), (0, 5))

    def test_failed_processing_then_retry(self):
        # check-out without check-in
        batch = self.device._import_events([self._ev('N1', 16, 0, 'check_out')], 'push')
        log = batch.log_ids
        log._process()
        self.assertEqual(log.processing_status, 'error')
        self.assertIn('no open attendance', log.error_message)
        self.assertFalse(self._attendances(self.nurse))
        # the missing check-in arrives later, then the failed check-out is retried
        self.device._import_events([self._ev('N1', 8)], 'push').log_ids._process()
        log.action_retry()
        self.assertEqual((log.processing_status, log.retry_count), ('done', 1))
        attendance = self._attendances(self.nurse)
        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance.check_out, self._dt(self.day, 16))
        self.assertEqual(batch.state, 'done')

    def test_retry_after_fixing_mapping(self):
        log = self.device._import_events([self._ev('NEW', 8)], 'push').log_ids
        log._process()
        self.assertEqual(log.processing_status, 'error')
        self.Mapping.create({'device_id': self.device.id, 'device_employee_code': 'NEW', 'employee_id': self.nurse.id})
        log.action_retry()
        self.assertEqual(log.processing_status, 'done')
        self.assertEqual(log.employee_id, self.nurse)

    def test_retry_limit_and_invalid_payload(self):
        log = self.device._import_events([self._ev('X9', 8)], 'push').log_ids
        log._process()
        for _i in range(5):
            log.action_retry()
        self.assertEqual((log.processing_status, log.retry_count), ('error', 5))
        with self.assertRaises(UserError):
            log.action_retry()
        invalid = self.device._import_events([{'employee_code': 'N1', 'timestamp': 'garbage'}], 'push').log_ids
        self.assertTrue(invalid.invalid_payload)
        with self.assertRaises(UserError):
            invalid.action_retry()

    def test_device_specific_mapping_precedence(self):
        self.Mapping.create([
            {'device_employee_code': 'SHARED', 'employee_id': self.doctor.id},
            {'device_id': self.device.id, 'device_employee_code': 'SHARED', 'employee_id': self.nurse.id},
        ])
        log_1 = self.device._import_events([self._ev('SHARED', 8)], 'push').log_ids
        log_2 = self.device_2._import_events([self._ev('SHARED', 8)], 'file').log_ids
        (log_1 | log_2)._process()
        self.assertEqual(log_1.employee_id, self.nurse, "device-specific mapping wins")
        self.assertEqual(log_2.employee_id, self.doctor, "company-wide mapping on other devices")

    @mute_logger('odoo.sql_db')
    def test_mapping_uniqueness(self):
        with self.assertRaises(Exception), self.cr.savepoint():
            self.Mapping.create({'device_id': self.device.id, 'device_employee_code': 'N1',
                                 'employee_id': self.doctor.id})
        with self.assertRaises(Exception), self.cr.savepoint():
            self.Mapping.create({'device_employee_code': 'D1', 'employee_id': self.nurse.id})

    def test_timezone_conversion(self):
        self.device.timezone = 'Asia/Riyadh'  # UTC+3, no DST
        batch = self.device._import_events([
            {'employee_code': 'N1', 'timestamp': self._ts(11, 5), 'event_type': 'check_in'},
            {'employee_code': 'N1', 'timestamp': self._dt(self.day, 19), 'event_type': 'check_out'},
            {'employee_code': 'D1', 'timestamp': self._dt(self.day, 9).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'event_type': 'check_in'},
            {'employee_code': 'D1', 'timestamp': self._dt(self.day, 20).strftime('%Y-%m-%dT%H:%M:%S+03:00'),
             'event_type': 'check_out'},
        ], 'push')
        times = {(log.device_employee_code, log.event_type): log.event_datetime for log in batch.log_ids}
        self.assertEqual(times[('N1', 'check_in')], self._dt(self.day, 8, 5))
        self.assertEqual(times[('N1', 'check_out')], self._dt(self.day, 16))
        self.assertEqual(times[('D1', 'check_in')], self._dt(self.day, 9), "explicit UTC is kept")
        self.assertEqual(times[('D1', 'check_out')], self._dt(self.day, 17), "explicit offset is honoured")

    def test_invalid_rows_become_error_logs(self):
        future = (fields.Datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        batch = self.device._import_events([
            {'timestamp': self._ts(8), 'event_type': 'check_in'},
            {'employee_code': 'N1', 'timestamp': 'not a date', 'event_type': 'check_in'},
            {'employee_code': 'N1', 'timestamp': future, 'event_type': 'check_in'},
            {'employee_code': 'N1', 'timestamp': self._ts(9), 'event_type': 'lunch'},
            'not a dict',
            self._ev('N1', 8),
        ], 'push')
        self.assertEqual((batch.received_count, batch.created_count, batch.duplicate_count), (6, 6, 0))
        errors = batch.log_ids.filtered(lambda l: l.processing_status == 'error')
        self.assertEqual(len(errors), 5)
        self.assertTrue(all(errors.mapped('invalid_payload')))
        self.assertTrue(all(errors.mapped('error_message')))
        self.assertIn('employee_code', errors.filtered(lambda l: not l.device_employee_code
                                                       and l.raw_payload != '{"value": "not a dict"}')[:1].error_message)
        self.assertIn('future', errors.filtered(lambda l: l.event_datetime and l.event_datetime > fields.Datetime.now())
                      .error_message)
        self.assertEqual(batch.state, 'partial')
        self.assertIn('Row 2', batch.error_log)
        # re-import: every row with a (code, timestamp) key is now a duplicate, keyless rows come back as errors
        batch_2 = self.device._import_events([
            {'employee_code': 'N1', 'timestamp': self._ts(9), 'event_type': 'lunch'}, self._ev('N1', 8)], 'push')
        self.assertEqual((batch_2.created_count, batch_2.duplicate_count), (0, 2))

    def test_batch_counts(self):
        batch = self.device._import_events([
            self._ev('N1', 8), self._ev('N1', 8), self._ev('N1', 8, 2),  # duplicate row + repeated scan
            self._ev('N1', 16, 0, 'check_out'),
            self._ev('X9', 8),  # unknown employee
            {'employee_code': 'N1', 'timestamp': 'bad'},  # invalid
        ], 'push')
        self.assertEqual((batch.received_count, batch.created_count, batch.duplicate_count), (6, 5, 1))
        self.assertEqual((batch.pending_count, batch.failed_count, batch.success_count), (4, 1, 0))
        self.assertEqual(batch.state, 'partial')
        batch.action_process()
        self.assertEqual((batch.pending_count, batch.failed_count, batch.success_count), (0, 2, 3))
        statuses = {log.event_datetime and (log.device_employee_code, log.event_datetime.minute, log.event_type):
                    log.processing_status for log in batch.log_ids}
        self.assertEqual(statuses[('N1', 2, 'check_in')], 'duplicate')
        self.assertEqual(batch.state, 'partial')
        self.assertEqual(len(self._attendances(self.nurse)), 1)

    def test_chronological_processing(self):
        # received out of order in two batches: the check-out is processed after the check-in
        out_log = self.device._import_events([self._ev('N1', 16, 0, 'check_out')], 'push').log_ids
        in_log = self.device._import_events([self._ev('N1', 8)], 'push').log_ids
        (out_log | in_log)._process()
        self.assertEqual((in_log.processing_status, out_log.processing_status), ('done', 'done'))
        self.assertEqual(self._attendances(self.nurse).check_out, self._dt(self.day, 16))

    def test_open_attendance_rules(self):
        # check-in while an attendance is open for less than 16h: duplicate
        logs = self.device._import_events([self._ev('N1', 8), self._ev('N1', 12)], 'push').log_ids
        logs._process()
        self.assertEqual(sorted(logs.mapped('processing_status')), ['done', 'duplicate'])
        # check-in 26h later while still open (forgotten check-out): error, nothing invented
        next_day = self.day + timedelta(days=1)
        stale = self.device._import_events([self._ev('N1', 10, day=next_day)], 'push').log_ids
        stale._process()
        self.assertEqual(stale.processing_status, 'error')
        self.assertIn('open attendance', stale.error_message)
        attendance = self._attendances(self.nurse)
        self.assertEqual(len(attendance), 1)
        self.assertFalse(attendance.check_out)
        # the officer closes it, the retry then succeeds
        attendance.check_out = self._dt(self.day, 16)
        stale.action_retry()
        self.assertEqual(stale.processing_status, 'done')
        self.assertEqual(len(self._attendances(self.nurse)), 2)

    def test_check_out_before_check_in_is_error(self):
        logs = self.device._import_events([self._ev('N1', 8)], 'push').log_ids
        logs._process()
        out = self.device._import_events([self._ev('N1', 7, 0, 'check_out')], 'push').log_ids
        out._process()
        self.assertEqual(out.processing_status, 'error')
        self.assertIn('not after', out.error_message)

    def test_unknown_event_type_toggles(self):
        logs = self.device._import_events([
            self._ev('N1', 8, 0, 'unknown'), self._ev('N1', 8, 1, 'unknown'),  # repeated scan
            self._ev('N1', 16, 0, 'unknown'), self._ev('N1', 16, 3, 'unknown'),  # repeated scan
            self._ev('N1', 20, 0, 'unknown'),
        ], 'push').log_ids
        logs._process()
        by_minute = {(l.event_datetime.hour, l.event_datetime.minute): l.processing_status for l in logs}
        self.assertEqual(by_minute, {(8, 0): 'done', (8, 1): 'duplicate', (16, 0): 'done', (16, 3): 'duplicate',
                                     (20, 0): 'done'})
        attendances = self._attendances(self.nurse).sorted('check_in')
        self.assertEqual(len(attendances), 2)
        self.assertEqual(attendances[0].check_out, self._dt(self.day, 16))
        self.assertFalse(attendances[1].check_out)

    def test_cron_process_pending(self):
        self.device._import_events([self._ev('N1', 8), self._ev('N1', 16, 0, 'check_out')], 'push')
        self.Log._cron_process_pending(limit=5000)
        self.assertFalse(self.Log.search([('device_id', '=', self.device.id), ('processing_status', '=', 'pending')]))
        self.assertEqual(self._attendances(self.nurse).check_out, self._dt(self.day, 16))

    def test_csv_import_wizard(self):
        content = 'employee_code,timestamp,event_type\nN1,%s,check_in\nN1,%s,check_out\n\nX9,%s,check_in\n' % (
            self._ts(8), self._ts(16), self._ts(8))
        wizard = self.env['healthcare.biometric.import.wizard'].create({
            'device_id': self.device_2.id, 'file': base64.b64encode(content.encode()), 'process_now': True})
        # N1 is only mapped on device 1: on device 2 it is unknown
        wizard.action_import()
        batch = self.env['healthcare.biometric.sync.batch'].search([('device_id', '=', self.device_2.id)])
        self.assertEqual((batch.source, batch.received_count, batch.created_count, batch.failed_count), ('file', 3, 3, 3))
        bad = self.env['healthcare.biometric.import.wizard'].create({
            'device_id': self.device_2.id, 'file': base64.b64encode(b'foo,bar\n1,2\n')})
        with self.assertRaises(UserError):
            bad.action_import()

    # ------------------------------------------------------------------
    # push token / pull adapters
    # ------------------------------------------------------------------
    def test_push_token(self):
        action = self.device.action_generate_push_token()
        token = action['params']['message'].rsplit(' ', 1)[-1]
        self.assertEqual(self.device.push_token_hash, hash_token(token))
        self.assertNotIn(token, self.device.push_token_hash)
        self.assertTrue(self.device.has_push_token)
        Device = self.env['healthcare.biometric.device']
        self.assertEqual(Device._authenticate_push('TDEV1', token), self.device)
        self.assertFalse(Device._authenticate_push('TDEV1', token + 'x'))
        self.assertFalse(Device._authenticate_push('TDEV2', token))
        self.assertFalse(Device._authenticate_push('NOPE', token))
        self.assertFalse(Device._authenticate_push('TDEV1', ''))
        self.assertFalse(Device._authenticate_push(None, token))
        # the token never appears in the chatter
        self.assertFalse(self.device.message_ids.filtered(lambda m: token in (m.body or '')))
        # a new token revokes the old one; archived devices are rejected
        self.device.action_generate_push_token()
        self.assertFalse(Device._authenticate_push('TDEV1', token))
        # officers cannot read nor generate secrets
        officer = self._user('bio_officer', 'healthcare_hr_core.group_hc_attendance_officer')
        with self.assertRaises(UserError):
            self.device.with_user(officer).action_generate_push_token()
        self.assertNotIn('push_token_hash', self.device.with_user(officer).fields_get())
        self.assertNotIn('api_secret', self.device.with_user(officer).fields_get())

    def test_pull_generic(self):
        self.device_2.write({'connection_type': 'api_pull', 'api_url': 'https://device.example/api/events',
                             'api_username': 'u', 'api_secret': 's3cret'})
        response = MagicMock()
        response.json.return_value = {'events': [self._ev('D1', 8), self._ev('D1', 17, 0, 'check_out')]}
        with patch(REQUESTS_GET, return_value=response) as get:
            batch = self.device_2._pull_events()
        self.assertEqual(get.call_args.kwargs['auth'], ('u', 's3cret'))
        self.assertTrue(get.call_args.kwargs['timeout'])
        self.assertEqual((batch.source, batch.created_count, batch.state), ('pull', 2, 'done'))
        self.assertTrue(self.device_2.last_sync)
        with patch(REQUESTS_GET, side_effect=requests.exceptions.ConnectionError('refused s3cret')):
            failed = self.device_2._pull_events()
        self.assertEqual(failed.state, 'failed')
        self.assertIn('ConnectionError', failed.error_log)
        self.assertNotIn('s3cret', failed.error_log)
        self.assertTrue(self.device_2.activity_ids, "the failure is alerted on the device")

    def test_pull_not_implemented_vendor_never_raises(self):
        self.device_2.write({'connection_type': 'api_pull', 'vendor': 'zkteco'})
        batch = self.device_2._pull_events()
        self.assertEqual(batch.state, 'failed')
        self.assertIn('not implemented', batch.error_log)
        self.env['healthcare.biometric.device']._cron_pull()  # must not raise

    def test_access_rights(self):
        officer = self._user('bio_officer2', 'healthcare_hr_core.group_hc_attendance_officer')
        officer.healthcare_branch_ids = self.branch_1
        self.device._import_events([self._ev('N1', 8)], 'push')
        self.device_2._import_events([self._ev('D1', 8)], 'file')
        logs = self.Log.with_user(officer).search([])
        self.assertIn(self.device, logs.device_id)
        self.assertNotIn(self.device_2, logs.device_id, "branch rule hides other branches")
        with self.assertRaises(Exception):
            self.device.with_user(officer).write({'name': 'hacked'})
        logs.with_user(officer).action_process()
        self.assertEqual(logs.processing_status, 'done')

    def test_datetime_object_input(self):
        batch = self.device._import_events([{'employee_code': 'N1', 'timestamp': datetime.combine(
            self.day, datetime.min.time()) + timedelta(hours=8), 'event_type': 'check_in'}], 'manual')
        self.assertEqual(batch.log_ids.event_datetime, self._dt(self.day, 8))
