from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

from odoo.addons.healthcare_hr_core.models.hr_employee import EMPLOYEE_CATEGORIES

KPI_MEASUREMENTS = [
    ('manual', 'Manual'),
    ('attendance_rate', 'Attendance Rate (%)'),
    ('late_rate', 'Late Arrival Rate (%)'),
    ('training_compliance', 'Training Compliance (%)'),
]


class KpiTemplate(models.Model):
    _name = 'healthcare.appraisal.kpi.template'
    _description = 'Healthcare Appraisal KPI Template'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    employee_category = fields.Selection(EMPLOYEE_CATEGORIES, string='Healthcare Category', index=True)
    job_ids = fields.Many2many('hr.job', string='Job Positions',
                               help="A template listing the employee's job wins over a category-only template.")
    line_ids = fields.One2many('healthcare.appraisal.kpi.template.line', 'template_id', string='KPIs', copy=True)
    total_weight = fields.Float(compute='_compute_total_weight')
    company_id = fields.Many2one('res.company', index=True, help="Empty = every company.")
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.depends('line_ids.weight')
    def _compute_total_weight(self):
        for template in self:
            template.total_weight = sum(template.line_ids.mapped('weight'))

    @api.constrains('line_ids')
    def _check_total_weight(self):
        for template in self:
            if template.line_ids and float_compare(sum(template.line_ids.mapped('weight')), 100.0,
                                                   precision_digits=2):
                raise ValidationError(self.env._('The KPI weights of "%s" must sum to 100.', template.name))

    @api.model
    def _find_for_employee(self, employee):
        """Best template for ``employee``: job match first, then healthcare category."""
        if not employee:
            return self.browse()
        templates = self.search([('company_id', 'in', (employee.company_id.id, False))])
        best, best_rank = self.browse(), 0
        for template in templates:
            if template.job_ids:
                if employee.job_id not in template.job_ids:
                    continue
                rank = 3 if template.employee_category in (False, employee.employee_category) else 0
            elif template.employee_category:
                rank = 2 if template.employee_category == employee.employee_category else 0
            else:
                rank = 1  # generic template
            if rank > best_rank:
                best, best_rank = template, rank
        return best


class KpiTemplateLine(models.Model):
    _name = 'healthcare.appraisal.kpi.template.line'
    _description = 'Healthcare Appraisal KPI Template Line'
    _order = 'sequence, id'

    template_id = fields.Many2one('healthcare.appraisal.kpi.template', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='KPI', required=True, translate=True)
    weight = fields.Float(required=True, default=10.0, help="Weights of a template sum to 100.")
    target = fields.Float(help="Expected value. Percentages for the automatic measurements.")
    measurement = fields.Selection(KPI_MEASUREMENTS, required=True, default='manual')
    higher_is_better = fields.Boolean(default=True,
                                      help="Unset for rates that must stay low (late arrivals, incidents).")
    description = fields.Text(translate=True)

    _weight_positive = models.Constraint('CHECK (weight >= 0)', 'A KPI weight cannot be negative.')

    @api.onchange('measurement')
    def _onchange_measurement(self):
        if self.measurement == 'late_rate':
            self.higher_is_better = False
        elif self.measurement in ('attendance_rate', 'training_compliance'):
            self.higher_is_better = True
