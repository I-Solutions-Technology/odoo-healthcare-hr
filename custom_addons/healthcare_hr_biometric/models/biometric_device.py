import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta

import pytz
import requests

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.base.models.res_partner import _tz_get

_logger = logging.getLogger(__name__)

EVENT_TYPES = ('check_in', 'check_out', 'unknown')
FUTURE_TOLERANCE = timedelta(minutes=5)
MAX_RAW_PAYLOAD = 2000
PULL_TIMEOUT = 30


def hash_token(token):
    return hashlib.sha256((token or '').encode()).hexdigest()


class HealthcareBiometricDevice(models.Model):
    _name = 'healthcare.biometric.device'
    _description = 'Biometric Device'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'branch_id, name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True, index=True,
                       help="Technical identifier sent by the device / middleware (X-Device-Code header).")
    vendor = fields.Selection([
        ('zkteco', 'ZKTeco'), ('suprema', 'Suprema'), ('hikvision', 'Hikvision'),
        ('anviz', 'Anviz'), ('generic', 'Generic'),
    ], required=True, default='generic', tracking=True)
    model = fields.Char(string='Device Model')
    branch_id = fields.Many2one('healthcare.hr.branch', tracking=True, index=True,
                                domain="[('company_id', '=', company_id)]")
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    connection_type = fields.Selection([
        ('api_push', 'API Push (device / middleware pushes to Odoo)'),
        ('api_pull', 'API Pull (Odoo pulls from the vendor API)'),
        ('file_import', 'File Import (CSV upload)'),
        ('sdk', 'On-premise SDK connector'),
    ], required=True, default='file_import', tracking=True)
    ip_address = fields.Char(string='IP Address')
    port = fields.Integer()
    api_url = fields.Char(string='API URL')
    api_username = fields.Char(string='API Username')
    # secrets: admin only, never tracked, never copied
    api_secret = fields.Char(string='API Secret', groups='healthcare_hr_core.group_hc_admin', copy=False)
    push_token_hash = fields.Char(string='Push Token Hash', groups='healthcare_hr_core.group_hc_admin',
                                  copy=False, readonly=True,
                                  help="SHA-256 of the push token. The clear token is shown only once.")
    has_push_token = fields.Boolean(compute='_compute_has_push_token')
    active = fields.Boolean(default=True, tracking=True)
    last_sync = fields.Datetime(readonly=True, copy=False)
    timezone = fields.Selection(_tz_get, required=True,
                                default=lambda self: self.env.company.partner_id.tz or self.env.user.tz or 'UTC',
                                help="Timezone of the device clock: naive timestamps sent by the device are "
                                     "interpreted in this timezone and stored in UTC.")
    log_ids = fields.One2many('healthcare.biometric.log', 'device_id')
    batch_ids = fields.One2many('healthcare.biometric.sync.batch', 'device_id')
    log_count = fields.Integer(compute='_compute_counts')
    pending_count = fields.Integer(compute='_compute_counts')
    error_count = fields.Integer(compute='_compute_counts')
    batch_count = fields.Integer(compute='_compute_counts')

    _code_company_uniq = models.Constraint('unique (code, company_id)',
                                           'The device code must be unique per company.')

    def _compute_has_push_token(self):
        for device, data in zip(self, self.sudo().read(['push_token_hash'])):
            device.has_push_token = bool(data['push_token_hash'])

    def _compute_counts(self):
        Log = self.env['healthcare.biometric.log']
        counts = {(device.id, status): count for device, status, count in Log._read_group(
            [('device_id', 'in', self.ids)], ['device_id', 'processing_status'], ['__count'])}
        batches = dict(self.env['healthcare.biometric.sync.batch']._read_group(
            [('device_id', 'in', self.ids)], ['device_id'], ['__count']))
        for device in self:
            by_status = {status: counts.get((device.id, status), 0)
                         for status in ('pending', 'done', 'duplicate', 'error', 'ignored')}
            device.log_count = sum(by_status.values())
            device.pending_count = by_status['pending']
            device.error_count = by_status['error']
            device.batch_count = batches.get(device, 0)

    # ------------------------------------------------------------------
    # Push token
    # ------------------------------------------------------------------
    def action_generate_push_token(self):
        """Generate a new push token: only its hash is stored, the clear value is shown once."""
        self.ensure_one()
        if not self.env.user.has_group('healthcare_hr_core.group_hc_admin'):
            raise UserError(self.env._('Only healthcare system administrators can generate push tokens.'))
        token = secrets.token_urlsafe(32)
        self.sudo().push_token_hash = hash_token(token)
        self.message_post(body=self.env._('A new push token was generated; the previous one is revoked.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Push token for %s', self.code),
                'message': self.env._('Copy it now, it will not be shown again: %s', token),
                'type': 'warning',
                'sticky': True,
            },
        }

    @api.model
    def _authenticate_push(self, code, token):
        """Return the active device matching ``code`` whose push token is ``token``, else an empty recordset.

        The hash comparison is constant time and is performed even when the code is unknown."""
        Device = self.sudo().with_context(active_test=True)
        if not code or not token or not isinstance(code, str) or not isinstance(token, str):
            return Device.browse()
        candidates = Device.search([('code', '=', code), ('connection_type', '=', 'api_push')])
        token_hash = hash_token(token)
        found = Device.browse()
        for device in candidates or [None]:
            stored = (device.push_token_hash if device else None) or hash_token(secrets.token_hex(16))
            if hmac.compare_digest(stored, token_hash) and device:
                found = device
        return found

    # ------------------------------------------------------------------
    # Import service
    # ------------------------------------------------------------------
    def _to_utc(self, value):
        """Convert a timestamp (str or datetime, naive = device clock timezone) to a naive UTC datetime."""
        self.ensure_one()
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str) and value.strip():
            text = value.strip()
            if text.endswith('Z'):
                text = text[:-1] + '+00:00'
            dt = datetime.fromisoformat(text)
        else:
            raise ValueError(self.env._('missing or invalid timestamp'))
        if dt.tzinfo is None:
            dt = pytz.timezone(self.timezone or 'UTC').localize(dt, is_dst=False)
        return dt.astimezone(pytz.utc).replace(tzinfo=None, microsecond=0)

    def _validate_event(self, event, now):
        """Return (vals, error): parsed log values and an error message (or None)."""
        self.ensure_one()
        vals = {'device_employee_code': False, 'event_datetime': False, 'event_type': 'unknown'}
        if not isinstance(event, dict):
            return vals, self.env._('Invalid row: expected an object with employee_code, timestamp, event_type.')
        missing = [key for key in ('employee_code', 'timestamp') if event.get(key) in (None, '', False)]
        code = event.get('employee_code')
        if code not in (None, '', False):
            vals['device_employee_code'] = str(code).strip()
        event_type = (event.get('event_type') or 'unknown')
        event_type = str(event_type).strip().lower()
        if event_type in EVENT_TYPES:
            vals['event_type'] = event_type
        if missing:
            return vals, self.env._('Missing required field(s): %s', ', '.join(missing))
        try:
            vals['event_datetime'] = self._to_utc(event['timestamp'])
        except (ValueError, TypeError, OverflowError):
            return vals, self.env._('Unparseable timestamp %r', event.get('timestamp'))
        if vals['event_datetime'] > now + FUTURE_TOLERANCE:
            return vals, self.env._('Timestamp %s (UTC) is in the future; check the device clock.',
                                    vals['event_datetime'])
        if event_type not in EVENT_TYPES:
            return vals, self.env._('Unknown event type %r (expected check_in, check_out or unknown).',
                                    event.get('event_type'))
        return vals, None

    def _import_events(self, events, source):
        """Store raw device events as biometric logs inside one sync batch.

        :param events: list of dicts {employee_code, timestamp (str/datetime in the device timezone), event_type}
        :param source: 'push', 'pull', 'file' or 'manual'
        :return: the healthcare.biometric.sync.batch record

        Invalid rows become error logs (never dropped). Rows whose (code, timestamp) already exist in this
        import or in the database are counted as duplicates and skipped, so re-imports are idempotent.
        """
        self.ensure_one()
        Batch = self.env['healthcare.biometric.sync.batch'].sudo()
        Log = self.env['healthcare.biometric.log'].sudo()
        events = list(events or [])
        batch = Batch.create({'device_id': self.id, 'source': source, 'received_count': len(events)})
        now = fields.Datetime.now()
        rows = []
        for index, event in enumerate(events):
            vals, error = self._validate_event(event, now)
            raw = event if isinstance(event, dict) else {'value': event}
            try:
                raw_payload = json.dumps(raw, default=str, ensure_ascii=False)[:MAX_RAW_PAYLOAD]
            except (TypeError, ValueError):
                raw_payload = repr(raw)[:MAX_RAW_PAYLOAD]
            rows.append((index, vals, error, raw_payload))

        # one query to find the keys already stored for this device
        keys = {(vals['device_employee_code'], vals['event_datetime']) for _i, vals, _e, _r in rows
                if vals['device_employee_code'] and vals['event_datetime']}
        existing = set()
        if keys:
            Log.flush_model(['device_id', 'device_employee_code', 'event_datetime'])
            self.env.cr.execute("""
                SELECT device_employee_code, event_datetime FROM healthcare_biometric_log
                 WHERE device_id = %s AND device_employee_code = ANY(%s) AND event_datetime = ANY(%s)
            """, [self.id, list({k[0] for k in keys}), list({k[1] for k in keys})])
            existing = set(self.env.cr.fetchall())

        seen = set()
        to_create, duplicates, errors = [], 0, []
        for index, vals, error, raw_payload in rows:
            key = (vals['device_employee_code'], vals['event_datetime'])
            if key[0] and key[1]:
                if key in existing or key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
            log_vals = dict(vals, device_id=self.id, batch_id=batch.id, source=source, raw_payload=raw_payload,
                            processing_status='error' if error else 'pending', error_message=error or False)
            if error:
                errors.append(self.env._('Row %(row)s: %(error)s', row=index + 1, error=error))
            to_create.append(log_vals)
        Log.create(to_create)
        batch.write({
            'created_count': len(to_create),
            'duplicate_count': duplicates,
            'error_log': '\n'.join(errors) or False,
            'ended': fields.Datetime.now(),
        })
        batch._update_state()
        self.sudo().last_sync = fields.Datetime.now()
        if errors:
            _logger.warning('Biometric device %s: %s invalid row(s) in batch %s', self.code, len(errors), batch.name)
        return batch

    # ------------------------------------------------------------------
    # Pull (vendor adapters)
    # ------------------------------------------------------------------
    def _pull_events(self):
        """Pull events from each api_pull device through its vendor adapter ``_pull_events_<vendor>``.

        Never raises: any error is stored on a failed sync batch and logged.
        :return: sync batches (one per device)
        """
        batches = self.env['healthcare.biometric.sync.batch'].sudo()
        for device in self:
            adapter = getattr(device, f'_pull_events_{device.vendor}', None)
            try:
                if device.connection_type != 'api_pull':
                    raise UserError(self.env._('Device %s is not configured for API pull.', device.code))
                if not adapter:
                    raise NotImplementedError(self.env._('No pull adapter for vendor %s.', device.vendor))
                with self.env.cr.savepoint():
                    events = adapter()
                    batches |= device._import_events(events, 'pull')
            except Exception as exc:  # noqa: BLE001 - never raise out of a sync / cron
                message = str(exc) or exc.__class__.__name__
                _logger.warning('Biometric pull failed for device %s: %s', device.code, message)
                batches |= batches.create({
                    'device_id': device.id, 'source': 'pull', 'state': 'failed',
                    'ended': fields.Datetime.now(), 'error_log': message,
                })
                device._hc_alert_sync_failure(message)
        return batches

    def _pull_since(self):
        self.ensure_one()
        return self.last_sync or (fields.Datetime.now() - timedelta(days=1))

    def _pull_events_generic(self):
        """Generic JSON adapter: GET ``api_url`` with basic auth.

        Expected response: a list of events, or an object with an ``events`` list. Each event:
        {"employee_code": "1001", "timestamp": "2026-01-01 08:00:00", "event_type": "check_in"}.
        """
        self.ensure_one()
        if not self.api_url:
            raise UserError(self.env._('Set the API URL of device %s.', self.code))
        secret = self.sudo().api_secret
        auth = (self.api_username, secret) if self.api_username else None
        try:
            response = requests.get(self.api_url, auth=auth, timeout=PULL_TIMEOUT,
                                    params={'since': fields.Datetime.to_string(self._pull_since())})
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as exc:
            # never echo the URL credentials / secret in the error
            raise UserError(self.env._('Connection to %(url)s failed: %(error)s',
                                       url=self.api_url, error=exc.__class__.__name__)) from None
        except ValueError:
            raise UserError(self.env._('The device API did not return valid JSON.')) from None
        if isinstance(data, dict):
            data = data.get('events')
        if not isinstance(data, list):
            raise UserError(self.env._('Unexpected API response: expected a list of events.'))
        return data

    def _pull_events_zkteco(self):
        raise NotImplementedError(self.env._(
            'The ZKTeco adapter is not implemented yet: use the generic JSON middleware or the push endpoint.'))

    def _pull_events_suprema(self):
        raise NotImplementedError(self.env._(
            'The Suprema adapter is not implemented yet: use the generic JSON middleware or the push endpoint.'))

    def _pull_events_hikvision(self):
        raise NotImplementedError(self.env._(
            'The Hikvision adapter is not implemented yet: use the generic JSON middleware or the push endpoint.'))

    def _pull_events_anviz(self):
        raise NotImplementedError(self.env._(
            'The Anviz adapter is not implemented yet: use the generic JSON middleware or the push endpoint.'))

    def _hc_alert_sync_failure(self, message):
        self.ensure_one()
        user = self.company_id.hc_alert_user_id or self.env.ref('base.user_admin', raise_if_not_found=False)
        self.env['healthcare.hr.alert'].schedule(
            self, 'biometric_sync_failed', self.env._('Biometric sync failed on %s', self.code),
            note=message, user=user)

    # ------------------------------------------------------------------
    # Actions / crons
    # ------------------------------------------------------------------
    def action_sync_now(self):
        self.ensure_one()
        batch = self._pull_events()
        batch.log_ids.filtered(lambda l: l.processing_status == 'pending')._process()
        return batch.action_open() if len(batch) == 1 else True

    def action_process_pending(self):
        logs = self.env['healthcare.biometric.log'].search(
            [('device_id', 'in', self.ids), ('processing_status', '=', 'pending')], order='event_datetime, id')
        logs._process()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': self.env._('%s pending log(s) processed.', len(logs)),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_view_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('healthcare_hr_biometric.action_biometric_log')
        action['domain'] = [('device_id', '=', self.id)]
        action['context'] = {'default_device_id': self.id}
        return action

    def action_view_batches(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('healthcare_hr_biometric.action_biometric_batch')
        action['domain'] = [('device_id', '=', self.id)]
        return action

    @api.model
    def _cron_pull(self):
        devices = self.search([('connection_type', '=', 'api_pull')])
        devices._pull_events()
        return True

    # ------------------------------------------------------------------
    # Demo
    # ------------------------------------------------------------------
    @api.model
    def _hc_load_demo_biometric(self):
        """Import and process a few of today's punches on the first demo device: a complete visit,
        an open check-in, a duplicate punch and an unknown badge. Employees already having an
        attendance around that time (attendance demo data) are skipped."""
        device = self.env.ref('healthcare_hr_biometric.demo_device_branch_1', raise_if_not_found=False)
        if not device:
            return False
        now = fields.Datetime.now().replace(second=0, microsecond=0)
        start = now - timedelta(hours=3)
        mappings = self.env['healthcare.biometric.employee.mapping'].search(
            [('device_id', '=', device.id), ('employee_id', '!=', False)], order='device_employee_code')
        busy = self.env['hr.attendance'].search([
            ('employee_id', 'in', mappings.employee_id.ids), ('check_in', '<', now),
            '|', ('check_out', '=', False), ('check_out', '>', start - timedelta(hours=1)),
        ]).employee_id
        free = mappings.filtered(lambda m: m.employee_id not in busy)[:2]
        tz = pytz.timezone(device.timezone or 'UTC')

        def local(dt):
            return pytz.utc.localize(dt).astimezone(tz).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')

        events = [{'employee_code': '9999', 'timestamp': local(start), 'event_type': 'check_in'}]
        if free:
            code = free[0].device_employee_code
            events += [
                {'employee_code': code, 'timestamp': local(start), 'event_type': 'check_in'},
                {'employee_code': code, 'timestamp': local(start), 'event_type': 'check_in'},  # duplicate
                {'employee_code': code, 'timestamp': local(now - timedelta(hours=1)), 'event_type': 'check_out'},
            ]
        if len(free) > 1:
            events.append({'employee_code': free[1].device_employee_code,
                           'timestamp': local(start + timedelta(minutes=10)), 'event_type': 'unknown'})
        batch = device._import_events(events, 'manual')
        batch.log_ids._process()
        return batch
