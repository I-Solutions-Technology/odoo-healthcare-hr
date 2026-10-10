import base64
import csv
import io

from odoo import fields, models
from odoo.exceptions import UserError

REQUIRED_COLUMNS = ('employee_code', 'timestamp')
MAX_ROWS = 100000


class HealthcareBiometricImportWizard(models.TransientModel):
    _name = 'healthcare.biometric.import.wizard'
    _description = 'Import Biometric Punches (CSV)'

    device_id = fields.Many2one('healthcare.biometric.device', required=True,
                                default=lambda self: self.env.context.get('default_device_id'))
    file = fields.Binary(string='CSV File', required=True)
    filename = fields.Char()
    delimiter = fields.Selection([(',', 'Comma'), (';', 'Semicolon'), ('\t', 'Tab')], default=',', required=True)
    process_now = fields.Boolean(default=True, help="Convert the imported punches into attendances right away.")

    def _read_rows(self):
        self.ensure_one()
        try:
            content = base64.b64decode(self.file or b'').decode('utf-8-sig')
        except (ValueError, UnicodeDecodeError):
            raise UserError(self.env._('The file must be a UTF-8 encoded CSV file.')) from None
        reader = csv.DictReader(io.StringIO(content), delimiter=self.delimiter)
        columns = [(c or '').strip().lower() for c in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in columns]
        if missing:
            raise UserError(self.env._(
                'Missing column(s): %s. Expected header: employee_code,timestamp,event_type', ', '.join(missing)))
        rows = []
        for row in reader:
            clean = {(k or '').strip().lower(): (v or '').strip() for k, v in row.items() if k}
            if not any(clean.values()):
                continue
            rows.append({'employee_code': clean.get('employee_code'), 'timestamp': clean.get('timestamp'),
                         'event_type': clean.get('event_type') or 'unknown'})
            if len(rows) > MAX_ROWS:
                raise UserError(self.env._('Too many rows: import at most %s punches per file.', MAX_ROWS))
        if not rows:
            raise UserError(self.env._('The file contains no punch.'))
        return rows

    def action_import(self):
        self.ensure_one()
        batch = self.device_id._import_events(self._read_rows(), 'file')
        if self.process_now:
            batch.action_process()
        return batch.action_open()
