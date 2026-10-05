import os
from dotenv import load_dotenv

# APP_ENV picks which env file to load: development | test | production
APP_ENV = os.getenv("APP_ENV", "development")
load_dotenv(f".env.{APP_ENV}")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "capstone_dev"),
}
API_PORT = int(os.getenv("API_PORT", "5000"))
DEBUG = APP_ENV == "development"
