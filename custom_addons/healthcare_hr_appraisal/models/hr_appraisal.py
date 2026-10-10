from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .kpi_template import KPI_MEASUREMENTS

AUTO_MEASUREMENTS = ('attendance_rate', 'late_rate', 'training_compliance')
NO_CONTRACT_ACTION_HELP = (
    "Decision support only: the KPI score never terminates, renews or extends a contract or a "
    "probation automatically. Those decisions are taken explicitly by HR.")


class HrAppraisal(models.Model):
    _inherit = 'hr.appraisal'

    hc_kpi_template_id = fields.Many2one('healthcare.appraisal.kpi.template', string='KPI Template',
                                         check_company=True)
    hc_kpi_line_ids = fields.One2many('healthcare.appraisal.kpi.line', 'appraisal_id', string='Healthcare KPIs',
                                      copy=True)
    hc_period_start = fields.Date(string='KPI Period Start', compute='_compute_hc_period', store=True,
                                  readonly=False, precompute=True)
    hc_period_end = fields.Date(string='KPI Period End', compute='_compute_hc_period', store=True,
                                readonly=False, precompute=True)
    hc_kpi_score = fields.Float(string='KPI Score', compute='_compute_hc_kpi_score', store=True, aggregator='avg',
                                help="Weighted average (0-100) of the evaluated KPIs. " + NO_CONTRACT_ACTION_HELP)

    @api.depends('date_close')
    def _compute_hc_period(self):
        for appraisal in self:
            end = appraisal.date_close or fields.Date.context_today(appraisal)
            appraisal.hc_period_end = end
            appraisal.hc_period_start = end - relativedelta(years=1)

    @api.depends('hc_kpi_line_ids.score', 'hc_kpi_line_ids.weight', 'hc_kpi_line_ids.evaluated')
    def _compute_hc_kpi_score(self):
        for appraisal in self:
            lines = appraisal.hc_kpi_line_ids.filtered('evaluated')
            weight = sum(lines.mapped('weight'))
            appraisal.hc_kpi_score = sum(l.score * l.weight for l in lines) / weight if weight else 0.0

    @api.constrains('hc_period_start', 'hc_period_end')
    def _check_hc_period(self):
        for appraisal in self:
            if appraisal.hc_period_start and appraisal.hc_period_end \
                    and appraisal.hc_period_start > appraisal.hc_period_end:
                raise UserError(self.env._('The KPI period start must be before its end.'))

    @api.model_create_multi
    def create(self, vals_list):
        appraisals = super().create(vals_list)
        appraisals.filtered(lambda a: not a.hc_kpi_line_ids)._hc_load_kpis(raise_if_none=False)
        return appraisals

    # ------------------------------------------------------------------
    # KPI loading / computation
    # ------------------------------------------------------------------
    def _hc_load_kpis(self, raise_if_none=True):
        """(Re)load the KPI lines from the best template, then compute the automatic actuals.

        Done with sudo: the template and the attendance data are read on behalf of the appraiser,
        only aggregated rates are stored on the appraisal.
        """
        Template = self.env['healthcare.appraisal.kpi.template'].sudo()
        loaded = self.browse()
        for appraisal in self.sudo():
            if appraisal.state == '3_done':
                raise UserError(self.env._('The appraisal of %s is done: its KPIs cannot be reloaded.',
                                           appraisal.employee_id.name))
            template = appraisal.hc_kpi_template_id or Template._find_for_employee(appraisal.employee_id)
            if not template:
                if raise_if_none:
                    raise UserError(self.env._('No KPI template matches the category or job of %s.',
                                               appraisal.employee_id.name))
                continue
            appraisal.hc_kpi_line_ids.unlink()
            appraisal.write({
                'hc_kpi_template_id': template.id,
                'hc_kpi_line_ids': [fields.Command.create({
                    'sequence': line.sequence, 'name': line.name, 'weight': line.weight, 'target': line.target,
                    'source': line.measurement, 'higher_is_better': line.higher_is_better,
                    'description': line.description,
                }) for line in template.line_ids],
            })
            loaded |= appraisal
        loaded._hc_refresh_kpi_actuals()
        return loaded

    def action_hc_load_kpis(self):
        self._hc_load_kpis()
        return True

    def action_hc_refresh_kpis(self):
        if any(a.state == '3_done' for a in self):
            raise UserError(self.env._('Done appraisals are frozen.'))
        self._hc_refresh_kpi_actuals()
        return True

    def _hc_refresh_kpi_actuals(self):
        appraisals = self.sudo().filtered(lambda a: a.state != '3_done' and a.hc_kpi_line_ids)
        if not appraisals:
            return
        attendance = appraisals._hc_attendance_stats()
        training = appraisals._hc_training_compliance()
        for appraisal in appraisals:
            stats = attendance.get(appraisal.id, {})
            values = {
                'attendance_rate': stats.get('attendance_rate'),
                'late_rate': stats.get('late_rate'),
                'training_compliance': training.get(appraisal.id),
            }
            for line in appraisal.hc_kpi_line_ids.filtered(lambda l: l.source in AUTO_MEASUREMENTS):
                value = values[line.source]
                line.write({'actual': value or 0.0, 'evaluated': value is not None,
                            'score': line._hc_score(value or 0.0) if value is not None else 0.0})

    def _hc_attendance_stats(self):
        """{appraisal_id: {'attendance_rate': %, 'late_rate': %}} from the shift assignments.

        Planned shifts = completed / approved / payroll-posted assignments of the period, except
        leave days. Attended = not absent; late = attendance status 'late'. One grouped query.
        """
        date_from, date_to = min(self.mapped('hc_period_start')), max(self.mapped('hc_period_end'))
        rows = self.env['healthcare.shift.assignment'].sudo()._read_group(
            [('employee_id', 'in', self.employee_id.ids), ('date', '>=', date_from), ('date', '<=', date_to),
             ('state', 'in', ('completed', 'approved', 'payroll_posted')),
             ('attendance_status', 'not in', (False, 'on_leave'))],
            ['employee_id', 'date:day', 'attendance_status'], ['__count'])
        result = {}
        for appraisal in self:
            planned = attended = late = 0
            for employee, day, status, count in rows:
                day = fields.Date.to_date(day)
                if employee != appraisal.employee_id or not (appraisal.hc_period_start <= day <= appraisal.hc_period_end):
                    continue
                planned += count
                if status != 'absent':
                    attended += count
                if status == 'late':
                    late += count
            result[appraisal.id] = {
                'attendance_rate': round(100.0 * attended / planned, 2) if planned else None,
                'late_rate': round(100.0 * late / attended, 2) if attended else None,
            }
        return result

    def _hc_training_compliance(self):
        """{appraisal_id: % or None} at the end of the period.

        Uses the training requirement matrix when the Healthcare Training module is installed
        (soft dependency), the mandatory credential types otherwise.
        """
        result = {}
        by_date = {}
        for appraisal in self:
            by_date.setdefault(appraisal.hc_period_end, self.browse())
            by_date[appraisal.hc_period_end] |= appraisal
        for on_date, appraisals in by_date.items():
            employees = appraisals.employee_id.sudo()
            matrix = {}
            if hasattr(employees, '_hc_training_matrix_compliance'):
                matrix = employees._hc_training_matrix_compliance(on_date)
            credentials = employees._hc_credential_compliance(on_date)
            for appraisal in appraisals:
                rate = matrix.get(appraisal.employee_id.id)
                result[appraisal.id] = rate if rate is not None else credentials.get(appraisal.employee_id.id)
        return result


class AppraisalKpiLine(models.Model):
    _name = 'healthcare.appraisal.kpi.line'
    _description = 'Appraisal Healthcare KPI'
    _order = 'sequence, id'

    appraisal_id = fields.Many2one('hr.appraisal', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='appraisal_id.company_id', store=True, index=True)
    employee_id = fields.Many2one(related='appraisal_id.employee_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='KPI', required=True)
    description = fields.Text()
    weight = fields.Float(required=True, default=10.0)
    target = fields.Float()
    actual = fields.Float()
    higher_is_better = fields.Boolean(default=True)
    source = fields.Selection(KPI_MEASUREMENTS, required=True, default='manual')
    score = fields.Float(string='Score (0-100)', help="Computed from the actual and the target; can be adjusted "
                                                      "by the appraiser for manual KPIs.")
    weighted_score = fields.Float(compute='_compute_weighted_score', store=True,
                                  help="Score x weight / 100.")
    evaluated = fields.Boolean(help="Included in the total: an actual was entered (manual KPI) or data exists "
                                    "for the period (automatic KPI).")

    _score_range = models.Constraint('CHECK (score >= 0 AND score <= 100)', 'A KPI score must be between 0 and 100.')

    @api.depends('score', 'weight')
    def _compute_weighted_score(self):
        for line in self:
            line.weighted_score = line.score * line.weight / 100.0

    def _hc_score(self, actual):
        """Score 0-100 of ``actual`` against the target of the line."""
        self.ensure_one()
        target = self.target
        if self.higher_is_better:
            score = 100.0 * actual / target if target > 0 else actual
        elif target > 0:
            score = 100.0 if actual <= target else 100.0 * target / actual
        else:
            score = 100.0 - actual
        return round(max(0.0, min(100.0, score)), 2)

    @api.onchange('actual')
    def _onchange_actual(self):
        if self.source == 'manual':
            self.score = self._hc_score(self.actual)
            self.evaluated = True

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._hc_check_editable()
        return lines

    def write(self, vals):
        if 'actual' in vals and 'score' not in vals:
            # manual KPI entered from a script or the list: derive the score like the onchange
            manual = self.filtered(lambda l: l.source == 'manual')
            for line in manual:
                super(AppraisalKpiLine, line).write({'score': line._hc_score(vals['actual']), 'evaluated': True})
        res = super().write(vals)
        self._hc_check_editable()
        return res

    def _hc_check_editable(self):
        """The appraised employee reads his KPIs but cannot rate himself."""
        if self.env.su or self.env.user.has_group('hr_appraisal.group_hr_appraisal_user'):
            return
        if any(line.appraisal_id.employee_id.user_id == self.env.user for line in self):
            raise UserError(self.env._('You cannot edit the KPIs of your own appraisal.'))
        if any(line.appraisal_id.state == '3_done' for line in self):
            raise UserError(self.env._('Done appraisals are frozen.'))
