import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'supplier_management.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
REPORT_DIR = os.path.join(BASE_DIR, 'reports')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

for dir_path in [UPLOAD_DIR, REPORT_DIR, EXPORT_DIR, LOG_DIR]:
    os.makedirs(dir_path, exist_ok=True)

SCORING_WEIGHTS = {
    'quality_system': 0.35,
    'environmental': 0.25,
    'financial': 0.40
}

THRESHOLDS = {
    'pass_score': 70,
    'excellent_score': 90,
    'downgrade_trigger': 0.20,
    'reminder_interval_days': 2,
    'abandon_days': 7
}

SUPPLIER_LEVELS = {
    'S': {'min_score': 90, 'max_score': 100, 'description': '战略供应商'},
    'A': {'min_score': 80, 'max_score': 89, 'description': '核心供应商'},
    'B': {'min_score': 70, 'max_score': 79, 'description': '合格供应商'},
    'C': {'min_score': 60, 'max_score': 69, 'description': '观察供应商'}
}

QUALITY_ISSUE_THRESHOLD = 2

EMAIL_CONFIG = {
    'smtp_server': 'smtp.example.com',
    'smtp_port': 587,
    'sender_email': 'system@example.com',
    'sender_password': 'password'
}

SCHEDULE_CONFIG = {
    'daily_check_time': '08:00',
    'monthly_report_day': 5,
    'yearly_review_month': 12
}
