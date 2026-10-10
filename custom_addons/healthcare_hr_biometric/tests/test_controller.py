import json
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from odoo.addons.healthcare_hr_biometric.controllers.main import MAX_EVENTS
from odoo.addons.healthcare_hr_biometric.models.biometric_device import hash_token

URL = '/healthcare/biometric/push'
TOKEN = 'test-token-0123456789'


@tagged('post_install', '-at_install', 'healthcare')
class TestBiometricPush(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = cls.env['healthcare.biometric.device'].create({
            'name': 'Push device', 'code': 'TPUSH', 'timezone': 'UTC', 'connection_type': 'api_push',
            'push_token_hash': hash_token(TOKEN)})
        cls.employee = cls.env['hr.employee'].create({'name': 'Push Employee', 'tz': 'UTC'})
        cls.env['healthcare.biometric.employee.mapping'].create({
            'device_id': cls.device.id, 'device_employee_code': 'P1', 'employee_id': cls.employee.id})
        cls.when = (fields.Datetime.now() - timedelta(hours=2)).replace(microsecond=0)

    def _post(self, body, code='TPUSH', token=TOKEN):
        headers = {'Content-Type': 'application/json'}
        if code is not None:
            headers['X-Device-Code'] = code
        if token is not None:
            headers['X-Device-Token'] = token
        data = body if isinstance(body, str) else json.dumps(body)
        return self.url_open(URL, data=data, headers=headers)

    def _events(self, count=1):
        return {'events': [{'employee_code': 'P1', 'event_type': 'check_in',
                            'timestamp': fields.Datetime.to_string(self.when - timedelta(minutes=i))}
                           for i in range(count)]}

    def _logs(self):
        return self.env['healthcare.biometric.log'].search([('device_id', '=', self.device.id)])

    def test_rejects_missing_headers(self):
        self.assertEqual(self._post(self._events(), code=None).status_code, 401)
        self.assertEqual(self._post(self._events(), token=None).status_code, 401)
        self.assertFalse(self._logs())

    def test_rejects_bad_token_or_device(self):
        self.assertEqual(self._post(self._events(), token='wrong').status_code, 403)
        self.assertEqual(self._post(self._events(), code='UNKNOWN').status_code, 403)
        # a device not configured for push cannot be used even with a valid token hash
        self.device.connection_type = 'file_import'
        self.assertEqual(self._post(self._events()).status_code, 403)
        self.device.connection_type = 'api_push'
        self.device.active = False
        self.assertEqual(self._post(self._events()).status_code, 403)
        self.assertFalse(self._logs())

    def test_rejects_bad_payloads(self):
        self.assertEqual(self._post('not json').status_code, 400)
        self.assertEqual(self._post({'foo': 'bar'}).status_code, 400)
        self.assertEqual(self._post(self._events(MAX_EVENTS + 1)).status_code, 413)
        self.assertFalse(self._logs())

    def test_push_creates_logs_idempotently(self):
        response = self._post(self._events(2))
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data['status'], data['received'], data['created'], data['duplicates']), ('ok', 2, 2, 0))
        again = self._post(self._events(2)).json()
        self.assertEqual((again['created'], again['duplicates']), (0, 2))
        logs = self._logs()
        self.assertEqual(len(logs), 2)
        self.assertEqual(set(logs.mapped('source')), {'push'})
        self.assertEqual(set(logs.mapped('processing_status')), {'pending'})
