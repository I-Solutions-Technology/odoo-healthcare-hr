from odoo import fields, models, tools

from odoo.addons.healthcare_hr_core.models.hr_employee import EMPLOYEE_CATEGORIES

COMPLIANCE_STATUS = [
    ('compliant', 'Compliant'),
    ('expiring', 'Expiring'),
    ('in_training', 'In Training'),
    ('missing', 'Missing'),
    ('waived', 'Waived'),
]


class TrainingComplianceReport(models.Model):
    """Employee x requirement compliance matrix (SQL view, always up to date).

    One row per active employee and matrix requirement in scope, whether a training was
    assigned or not: employees already holding a valid credential count as compliant, so the
    compliance rate is not biased by the fact that compliant employees get no assignment.
    Aggregation (rate by department, branch, requirement ...) is done by the database.
    """
    _name = 'healthcare.training.compliance.report'
    _description = 'Training Compliance Analysis'
    _auto = False
    _order = 'employee_id, requirement_id'

    employee_id = fields.Many2one('hr.employee', readonly=True)
    requirement_id = fields.Many2one('healthcare.training.requirement', string='Training Requirement', readonly=True)
    credential_type_id = fields.Many2one('healthcare.hr.credential.type', string='Certification', readonly=True)
    mandatory = fields.Boolean(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    branch_id = fields.Many2one('healthcare.hr.branch', string='Branch', readonly=True)
    department_id = fields.Many2one('hr.department', readonly=True)
    job_id = fields.Many2one('hr.job', readonly=True)
    employee_category = fields.Selection(EMPLOYEE_CATEGORIES, string='Healthcare Category', readonly=True)
    status = fields.Selection(COMPLIANCE_STATUS, readonly=True)
    compliant = fields.Boolean(readonly=True)
    compliance_rate = fields.Float(string='Compliance %', aggregator='avg', readonly=True)
    covered_until = fields.Date(readonly=True, help="Expiry of the best valid credential or completed training.")
    due_date = fields.Date(string='Training Due Date', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(tools.SQL("""
            CREATE OR REPLACE VIEW %s AS (
            WITH scope AS (
                SELECT r.id AS requirement_id, e.id AS employee_id, r.credential_type_id, r.mandatory,
                       e.company_id, e.healthcare_branch_id AS branch_id, v.department_id, v.job_id,
                       e.employee_category, COALESCE(c.hc_training_alert_days, 0) AS alert_days
                  FROM healthcare_training_requirement r
                  JOIN hr_employee e ON e.company_id = r.company_id AND e.active
                  JOIN res_company c ON c.id = e.company_id
             LEFT JOIN hr_version v ON v.id = e.current_version_id
                 WHERE r.active
                   AND (r.job_id IS NULL OR r.job_id = v.job_id)
                   AND (r.employee_category IS NULL OR r.employee_category = e.employee_category)
                   AND (r.department_id IS NULL OR r.department_id = v.department_id
                        OR r.department_id = e.medical_department_id)
            ), evidence AS (
                SELECT s.*,
                       (SELECT MAX(COALESCE(x.expiry_date, 'infinity'::date)) FROM (
                            SELECT cr.expiry_date
                              FROM healthcare_hr_credential cr
                             WHERE cr.employee_id = s.employee_id
                               AND cr.credential_type_id = s.credential_type_id
                               AND cr.active AND cr.verified
                               AND (cr.expiry_date IS NULL OR cr.expiry_date >= CURRENT_DATE)
                            UNION ALL
                            SELECT a.expiry_date
                              FROM healthcare_training_assignment a
                             WHERE a.employee_id = s.employee_id
                               AND a.credential_type_id = s.credential_type_id
                               AND a.state = 'completed'
                               AND (a.expiry_date IS NULL OR a.expiry_date >= CURRENT_DATE)
                       ) x) AS covered,
                       EXISTS (SELECT 1 FROM healthcare_training_assignment a
                                WHERE a.employee_id = s.employee_id AND a.requirement_id = s.requirement_id
                                  AND a.state = 'waived') AS waived,
                       (SELECT MIN(a.due_date) FROM healthcare_training_assignment a
                         WHERE a.employee_id = s.employee_id AND a.requirement_id = s.requirement_id
                           AND a.state IN ('assigned', 'in_progress')) AS open_due,
                       EXISTS (SELECT 1 FROM healthcare_training_assignment a
                                WHERE a.employee_id = s.employee_id AND a.requirement_id = s.requirement_id
                                  AND a.state IN ('assigned', 'in_progress')) AS in_training
                  FROM scope s
            )
            SELECT ROW_NUMBER() OVER (ORDER BY employee_id, requirement_id) AS id,
                   employee_id, requirement_id, credential_type_id, mandatory, company_id, branch_id,
                   department_id, job_id, employee_category,
                   CASE WHEN covered = 'infinity'::date THEN NULL ELSE covered END AS covered_until,
                   open_due AS due_date,
                   (waived OR covered IS NOT NULL) AS compliant,
                   CASE WHEN waived OR covered IS NOT NULL THEN 100.0 ELSE 0.0 END AS compliance_rate,
                   CASE WHEN waived THEN 'waived'
                        WHEN covered IS NOT NULL AND covered > CURRENT_DATE + alert_days THEN 'compliant'
                        WHEN covered IS NOT NULL THEN 'expiring'
                        WHEN in_training THEN 'in_training'
                        ELSE 'missing' END AS status
              FROM evidence
            )""", tools.SQL.identifier(self._table)))
