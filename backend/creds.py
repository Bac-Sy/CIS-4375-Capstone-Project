import os
from dotenv import load_dotenv

# APP_ENV picks which env file to load: development | test | production
# Real values live in backend/.env.<APP_ENV>, which is never committed.
APP_ENV = os.getenv("APP_ENV", "development")
load_dotenv(os.path.join(os.path.dirname(__file__), f".env.{APP_ENV}"))


class mycreds:
    hostname = os.getenv("DB_HOST")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
