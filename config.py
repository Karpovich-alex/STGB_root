import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    RABBITMQ = os.environ.get("RABBITMQ") or ''
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI") or "sqlite:///:memory:?check_same_thread=False"
    UPDATER_URL = os.environ.get("UPDATER_URL") or "http://127.0.0.1:8001"
