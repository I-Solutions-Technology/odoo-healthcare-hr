import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_datetime

from .biometric_batch import SOURCES
from .biometric_device import FUTURE_TOLERANCE

_logger = logging.getLogger(__name__)

# An open attendance is considered "current" for this long after its check-in (or until its planned
# shift end + the company's missing-checkout delay, when that is later, e.g. 24h shifts). Past that,
# it is a forgotten check-out: the device never invents a check-out time, the log goes in error.
OPEN_ATTENDANCE_MAX_HOURS = 16
# Two punches of the same employee this close to each other are one physical scan.
REPEAT_SCAN_MINUTES = 5
MAX_RETRIES = 5
PROCESSED_STATES = ('done', 'duplicate', 'ignored')


class ProcessingError(Exception):
    """Business error while converting a log into attendance: stored on the log."""


class HealthcareBiometricLog(models.Model):
    _name = 'healthcare.biometric.log'
    _description = 'Biometric Raw Log'
    _order = 'event_datetime desc, id desc'

    device_id = fields.Many2one('healthcare.biometric.device', required=True, index=True, ondelete='restrict',
                                readonly=True)
    company_id = fields.Many2one(related='device_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='device_id.branch_id', store=True, index=True)
    device_employee_code = fields.Char(string='Employee Code', index=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', index='btree_not_null', readonly=True,
                                  help="Resolved from the employee mapping when the log is processed.")
    event_datetime = fields.Datetime(string='Event Time', index=True, readonly=True, help="Stored in UTC.")
    event_type = fields.Selection([
        ('check_in', 'Check In'), ('check_out', 'Check Out'), ('unknown', 'Unknown / Toggle'),
    ], required=True, default='unknown', readonly=True)
    source = fields.Selection(SOURCES, required=True, default='manual', readonly=True)
    raw_payload = fields.Text(readonly=True)
    processed = fields.Boolean(compute='_compute_processed', store=True, index=True)
    processing_status = fields.Selection([
        ('pending', 'Pending'), ('done', 'Done'), ('duplicate', 'Duplicate'),
        ('error', 'Error'), ('ignored', 'Ignored'),
    ], default='pending', required=True, index=True, readonly=True)
    invalid_payload = fields.Boolean(readonly=True,
                                     help="The row itself is invalid (missing data, bad timestamp or type): "
                                          "retrying cannot fix it, the device must resend it.")
    error_message = fields.Text(readonly=True)
    attendance_id = fields.Many2one('hr.attendance', index='btree_not_null', ondelete='set null', readonly=True)
    batch_id = fields.Many2one('healthcare.biometric.sync.batch', index=True, ondelete='set null', readonly=True)
    retry_count = fields.Integer(readonly=True)

    _event_uniq = models.Constraint(
        'unique (device_id, device_employee_code, event_datetime)',
        'This punch was already received from this device.')

    @api.depends('processing_status')
    def _compute_processed(self):
        for log in self:
            log.processed = log.processing_status in PROCESSED_STATES

    @api.depends('device_id', 'device_employee_code', 'event_datetime')
    def _compute_display_name(self):
        for log in self:
            when = format_datetime(self.env, log.event_datetime) if log.event_datetime else '?'
            log.display_name = f"{log.device_id.code or ''} / {log.device_employee_code or '?'} @ {when}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('processing_status') == 'error' and 'invalid_payload' not in vals:
                vals['invalid_payload'] = True
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------
    def _process(self):
        """Convert pending logs into hr.attendance, in chronological order.

        Already processed / failed logs are skipped (idempotent). Each log runs in its own savepoint:
        one failure never blocks the others. Returns the processed logs.
        """
        logs = self.sudo().filtered(lambda l: l.processing_status == 'pending')
        if not logs:
            return logs
        logs = logs.sorted(lambda l: (l.event_datetime or fields.Datetime.now(), l.id))
        Mapping = self.env['healthcare.biometric.employee.mapping']
        employees = {}
        for device in logs.device_id:
            codes = logs.filtered(lambda l: l.device_id == device).mapped('device_employee_code')
            employees[device.id] = Mapping._resolve(device, codes)
        now = fields.Datetime.now()
        for log in logs:
            try:
                with self.env.cr.savepoint():
                    vals = log._process_one(employees.get(log.device_id.id, {}), now)
                    log.write(vals)
            except Exception as exc:  # noqa: BLE001 - stored on the log, never blocks the batch
                message = exc.args[0] if isinstance(exc, (ProcessingError, UserError)) and exc.args else str(exc)
                _logger.warning('Biometric log %s (device %s, code %s) failed: %s',
                                log.id, log.device_id.code, log.device_employee_code, message)
                log.write({'processing_status': 'error', 'error_message': message})
        logs.batch_id._update_state()
        return logs

    def _process_one(self, employees, now):
        self.ensure_one()
        if not self.device_employee_code or not self.event_datetime:
            raise ProcessingError(self.env._('The log has no employee code or no event time.'))
        if self.event_datetime > now + FUTURE_TOLERANCE:
            raise ProcessingError(self.env._('Event time %s (UTC) is in the future.', self.event_datetime))
        employee = employees.get(self.device_employee_code)
        if not employee:
            raise ProcessingError(self.env._('Unknown employee code %(code)s on device %(device)s',
                                             code=self.device_employee_code, device=self.device_id.code))
        vals = {'employee_id': employee.id, 'error_message': False}
        handler = {'check_in': self._do_check_in, 'check_out': self._do_check_out,
                   'unknown': self._do_toggle}[self.event_type]
        status, attendance, note = handler(employee, self.event_datetime)
        vals.update(processing_status=status, attendance_id=attendance.id if attendance else False,
                    error_message=note or False)
        return vals

    # -- helpers ---------------------------------------------------------
    def _attendance_model(self):
        return self.env['hr.attendance'].sudo().with_context(tracking_disable=True)

    def _open_attendance(self, employee):
        return self._attendance_model().search(
            [('employee_id', '=', employee.id), ('check_out', '=', False)], order='check_in desc', limit=1)

    def _last_attendance_before(self, employee, when):
        return self._attendance_model().search(
            [('employee_id', '=', employee.id), ('check_in', '<=', when)], order='check_in desc', limit=1)

    @staticmethod
    def _open_limit(attendance):
        """Latest time an open attendance can still be closed by the device."""
        limit = attendance.check_in + timedelta(hours=OPEN_ATTENDANCE_MAX_HOURS)
        shift = attendance.planned_shift_id
        if shift and shift.datetime_end:
            delay = timedelta(hours=attendance.employee_id.company_id.hc_missing_checkout_hours or 2.0)
            limit = max(limit, shift.datetime_end + delay)
        return limit

    def _fmt(self, value):
        return format_datetime(self.env, value)

    def _stale_error(self, attendance):
        return ProcessingError(self.env._(
            'Employee %(employee)s has an open attendance since %(since)s with no check-out (older than '
            '%(hours)sh). Complete or correct it, then retry this log.',
            employee=attendance.employee_id.name, since=self._fmt(attendance.check_in),
            hours=OPEN_ATTENDANCE_MAX_HOURS))

    def _covered(self, employee, when):
        """Closed attendance covering ``when`` (punch already accounted for), if any."""
        last = self._last_attendance_before(employee, when)
        if last and last.check_out and last.check_out >= when:
            return last
        return self._attendance_model().browse()

    def _do_check_in(self, employee, when):
        open_att = self._open_attendance(employee)
        if open_att:
            if open_att.check_in <= when <= self._open_limit(open_att):
                return 'duplicate', open_att, self.env._('Already checked in since %s.', self._fmt(open_att.check_in))
            if when > open_att.check_in:
                raise self._stale_error(open_att)
        covered = self._covered(employee, when)
        if covered:
            status = 'duplicate' if covered.check_in == when else 'ignored'
            return status, covered, self.env._('Punch inside the existing attendance %(start)s - %(end)s.',
                                               start=self._fmt(covered.check_in), end=self._fmt(covered.check_out))
        later = self._attendance_model().search(
            [('employee_id', '=', employee.id), ('check_in', '>', when)], order='check_in', limit=1)
        if later:
            raise ProcessingError(self.env._(
                'Out-of-order check-in at %(when)s: a later attendance already starts at %(later)s. '
                'Enter this attendance manually if it is genuine.',
                when=self._fmt(when), later=self._fmt(later.check_in)))
        attendance = self._attendance_model().create({
            'employee_id': employee.id, 'check_in': when, 'in_mode': 'kiosk'})
        return 'done', attendance, None

    def _do_check_out(self, employee, when):
        open_att = self._open_attendance(employee)
        if open_att:
            if when <= open_att.check_in:
                raise ProcessingError(self.env._(
                    'Check-out at %(when)s is not after the open check-in at %(check_in)s.',
                    when=self._fmt(when), check_in=self._fmt(open_att.check_in)))
            if when > self._open_limit(open_att):
                raise self._stale_error(open_att)
            open_att.write({'check_out': when, 'out_mode': 'kiosk'})
            return 'done', open_att, None
        last = self._last_attendance_before(employee, when)
        if last and last.check_out:
            if last.check_out == when or abs(when - last.check_out) <= timedelta(minutes=REPEAT_SCAN_MINUTES):
                return 'duplicate', last, self.env._('Already checked out at %s.', self._fmt(last.check_out))
            if last.check_out > when:
                return 'ignored', last, self.env._('Punch inside the existing attendance %(start)s - %(end)s.',
                                                   start=self._fmt(last.check_in), end=self._fmt(last.check_out))
        raise ProcessingError(self.env._('Check-out at %(when)s but %(employee)s has no open attendance.',
                                         when=self._fmt(when), employee=employee.name))

    def _do_toggle(self, employee, when):
        """Unknown punch type: open attendance -> check-out, none -> check-in."""
        open_att = self._open_attendance(employee)
        if open_att and when >= open_att.check_in:
            if when - open_att.check_in <= timedelta(minutes=REPEAT_SCAN_MINUTES):
                return 'duplicate', open_att, self.env._('Repeated scan right after the check-in.')
            return self._do_check_out(employee, when)
        last = self._last_attendance_before(employee, when)
        if not open_att and last and last.check_out and \
                when <= last.check_out + timedelta(minutes=REPEAT_SCAN_MINUTES):
            status = 'duplicate' if when >= last.check_out else 'ignored'
            return status, last, self.env._('Punch inside or right after the attendance %(start)s - %(end)s.',
                                            start=self._fmt(last.check_in), end=self._fmt(last.check_out))
        return self._do_check_in(employee, when)

    # ------------------------------------------------------------------
    # Actions / cron
    # ------------------------------------------------------------------
    def action_retry(self):
        """Reset failed logs to pending (max 5 retries) and process them again."""
        failed = self.filtered(lambda l: l.processing_status == 'error')
        blocked = failed.filtered(lambda l: l.invalid_payload or l.retry_count >= MAX_RETRIES)
        todo = failed - blocked
        for log in todo:
            log.sudo().write({'processing_status': 'pending', 'error_message': False,
                              'retry_count': log.retry_count + 1})
        todo._process()
        if blocked and not todo:
            raise UserError(self.env._(
                'These logs cannot be retried: invalid payloads must be resent by the device and a log '
                'can be retried at most %s times.', MAX_RETRIES))
        return True

    def action_process(self):
        self._process()
        return True

    def action_open_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'hr.attendance',
            'res_id': self.attendance_id.id, 'view_mode': 'form',
        }

    @api.model
    def _cron_process_pending(self, limit=5000):
        logs = self.search([('processing_status', '=', 'pending')], order='event_datetime, id', limit=limit)
        logs._process()
        if len(logs) == limit:
            self.env.ref('healthcare_hr_biometric.ir_cron_process_logs')._trigger()
        return True
