from odoo import api, fields, models

SOURCES = [('push', 'Push'), ('pull', 'Pull'), ('file', 'File Import'), ('manual', 'Manual')]


class HealthcareBiometricSyncBatch(models.Model):
    _name = 'healthcare.biometric.sync.batch'
    _description = 'Biometric Sync Batch'
    _order = 'started desc, id desc'

    name = fields.Char(required=True, readonly=True, copy=False, default='/')
    device_id = fields.Many2one('healthcare.biometric.device', required=True, index=True, ondelete='cascade',
                                readonly=True)
    company_id = fields.Many2one(related='device_id.company_id', store=True, index=True)
    branch_id = fields.Many2one(related='device_id.branch_id', store=True, index=True)
    source = fields.Selection(SOURCES, required=True, readonly=True)
    started = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    ended = fields.Datetime(readonly=True)
    received_count = fields.Integer(string='Received', readonly=True, help="Rows received from the device.")
    created_count = fields.Integer(string='Created', readonly=True, help="Raw logs created (valid or invalid).")
    duplicate_count = fields.Integer(string='Duplicates', readonly=True,
                                     help="Rows skipped because the same punch was already received.")
    success_count = fields.Integer(string='Processed', compute='_compute_log_counts', store=True,
                                   help="Logs processed into attendance (done, duplicate or ignored).")
    pending_count = fields.Integer(string='Pending', compute='_compute_log_counts', store=True)
    failed_count = fields.Integer(string='Failed', compute='_compute_log_counts', store=True)
    state = fields.Selection([
        ('running', 'Running'), ('done', 'Done'), ('partial', 'Partial'), ('failed', 'Failed'),
    ], default='running', required=True, readonly=True, index=True)
    error_log = fields.Text(readonly=True)
    log_ids = fields.One2many('healthcare.biometric.log', 'batch_id', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('healthcare.biometric.sync.batch') or '/'
        return super().create(vals_list)

    @api.depends('log_ids.processing_status')
    def _compute_log_counts(self):
        data = {(batch.id, status): count for batch, status, count in self.env['healthcare.biometric.log'].sudo()
                ._read_group([('batch_id', 'in', self.ids)], ['batch_id', 'processing_status'], ['__count'])}
        for batch in self:
            count = lambda *states: sum(data.get((batch.id, s), 0) for s in states)  # noqa: E731
            batch.success_count = count('done', 'duplicate', 'ignored')
            batch.pending_count = count('pending')
            batch.failed_count = count('error')

    def _update_state(self):
        """Import / processing outcome: done (no error), partial (some errors), failed (only errors)."""
        self.flush_recordset()
        for batch in self:
            if batch.state == 'failed' and not batch.log_ids:
                continue
            if not batch.failed_count:
                state = 'done'
            elif batch.success_count or batch.pending_count or batch.duplicate_count:
                state = 'partial'
            else:
                state = 'failed'
            batch.state = state

    def action_process(self):
        self.log_ids.filtered(lambda l: l.processing_status == 'pending')._process()
        return True

    def action_retry_failed(self):
        return self.log_ids.filtered(lambda l: l.processing_status == 'error').action_retry()

    def action_open(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('healthcare_hr_biometric.action_biometric_log')
        action['domain'] = [('batch_id', '=', self.id)]
        action['context'] = {}
        return action
