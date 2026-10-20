import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

from sqlalchemy.pool import NullPool

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'bling-bi-secret-key-local-2026')

    _raw_db_url = os.environ.get('SUPABASE_DB_URL') or os.environ.get(
        'DATABASE_URL', f"sqlite:///{os.path.join(DATA_DIR, 'bling_bi.db')}"
    )
    # Suporte para URLs PostgreSQL do Supabase, Render e Railway que usam postgres://
    if _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _raw_db_url
    IS_POSTGRES = SQLALCHEMY_DATABASE_URI.startswith("postgresql")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuração dinâmica de engine para SQLite vs PostgreSQL (Supabase)
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'poolclass': NullPool,
            'connect_args': {
                'timeout': 60,
                'check_same_thread': False
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 20
        }

    BLING_API_BASE_URL = "https://api.bling.com.br/Api/v3"
