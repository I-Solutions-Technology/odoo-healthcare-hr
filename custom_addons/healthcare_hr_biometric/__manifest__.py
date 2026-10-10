{
    'name': 'Healthcare HR Biometric Devices',
    'summary': 'Fingerprint / RFID / face device integration: raw punch logs, idempotent sync batches '
               'and safe conversion into standard attendances',
    'description': """
Healthcare Biometric Integration
================================
Connects time clocks (ZKTeco, Suprema, Hikvision, Anviz or any generic middleware) to the
Healthcare attendance flow without ever touching payroll directly:

* Devices with push (HTTP endpoint + hashed token), pull (vendor adapters), CSV import or on-prem SDK.
* Raw punch logs stored as received, deduplicated per (device, employee code, timestamp):
  re-imports are idempotent.
* Every import is a sync batch with received / created / duplicate / success / failed counters.
* Device employee codes are mapped to employees (device-specific mapping first, then company-wide).
* Logs are processed in chronological order into hr.attendance records (never duplicated);
  the Healthcare Attendance module then matches them to planned shifts and reconciles them.
* Failed logs keep a clear error message and can be retried.
""",
    'version': '19.0.1.0.0',
    'author': 'iSolutions Technology',
    'website': 'https://isolutions-technology.com',
    'license': 'LGPL-3',
    'category': 'Human Resources/Healthcare',
    'depends': ['healthcare_hr_attendance'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'security/biometric_rules.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'wizard/biometric_import_wizard_views.xml',
        'views/biometric_device_views.xml',
        'views/biometric_mapping_views.xml',
        'views/biometric_log_views.xml',
        'views/biometric_batch_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/biometric_demo.xml',
    ],
    'installable': True,
}
