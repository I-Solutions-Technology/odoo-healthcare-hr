import json
import logging

from odoo import SUPERUSER_ID
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

MAX_EVENTS = 5000
MAX_BODY_BYTES = 5 * 1024 * 1024


class BiometricPushController(Controller):
    """Inbound endpoint for devices / middleware (connection type "API Push").

    POST /healthcare/biometric/push
    Headers: X-Device-Code, X-Device-Token, Content-Type: application/json
    Body: {"events": [{"employee_code": "1001", "timestamp": "2026-01-01 08:00:00", "event_type": "check_in"}]}
    (a bare JSON list of events is accepted too). Timestamps without offset are in the device timezone.

    The events are only stored as raw logs of the authenticated device; the processing cron turns them
    into attendances. Nothing else can be written through this route.
    """

    def _error(self, status, message):
        return request.make_json_response({'status': 'error', 'error': message}, status=status)

    @route('/healthcare/biometric/push', type='http', auth='none', methods=['POST'], csrf=False,
           save_session=False, readonly=False)
    def push(self, **kwargs):
        if not request.db:
            return self._error(400, 'No database selected.')
        headers = request.httprequest.headers
        code, token = headers.get('X-Device-Code'), headers.get('X-Device-Token')
        if not code or not token:
            return self._error(401, 'Missing X-Device-Code / X-Device-Token headers.')
        env = request.env(user=SUPERUSER_ID)
        device = env['healthcare.biometric.device']._authenticate_push(code, token)
        if not device:
            _logger.warning('Biometric push rejected for device code %r from %s', code,
                            request.httprequest.remote_addr)
            return self._error(403, 'Invalid device code or token.')
        length = request.httprequest.content_length or 0
        if length > MAX_BODY_BYTES:
            return self._error(413, 'Payload too large.')
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or 'null')
        except ValueError:
            return self._error(400, 'Body is not valid JSON.')
        events = payload.get('events') if isinstance(payload, dict) else payload
        if not isinstance(events, list):
            return self._error(400, 'Expected a list of events.')
        if len(events) > MAX_EVENTS:
            return self._error(413, f'Too many events: at most {MAX_EVENTS} per request.')
        batch = device.with_company(device.company_id)._import_events(events, 'push')
        return request.make_json_response({
            'status': 'ok',
            'batch': batch.name,
            'received': batch.received_count,
            'created': batch.created_count,
            'duplicates': batch.duplicate_count,
            'invalid': batch.failed_count,
        })
