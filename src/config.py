import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database and Data paths
DB_PATH = os.getenv("DB_PATH", "data/lms/lms.db")
STUDENTS_JSON = os.getenv("STUDENTS_JSON", "data/lms/students.json")
SCHEDULE_JSON = os.getenv("SCHEDULE_JSON", "data/lms/schedule.json")
LOG_FILE = os.getenv("LOG_FILE", "data/analytics/query_logs.csv")
HOMEWORKS_DIR = os.getenv("HOMEWORKS_DIR", "data/lms/homeworks")
KB_DIR = os.getenv("KB_DIR", "data/kb")

# Credentials
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

# LLM Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
