import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

from sqlalchemy.pool import NullPool

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'bling-bi-secret-key-local-2026')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f"sqlite:///{os.path.join(DATA_DIR, 'bling_bi.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,
        'connect_args': {
            'timeout': 60,
            'check_same_thread': False
        }
    }
    BLING_API_BASE_URL = "https://api.bling.com.br/Api/v3"
