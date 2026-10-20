import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Carrega arquivo .env se presente localmente
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as _env_file:
            for _line in _env_file:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

from sqlalchemy.pool import NullPool

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'bling-bi-secret-key-local-2026')

    _raw_db_url = os.environ.get('SUPABASE_DB_URL') or os.environ.get(
        'DATABASE_URL', f"sqlite:///{os.path.join(DATA_DIR, 'bling_bi.db')}"
    )
    import re
    # Conversão de URLs diretas do Supabase (IPv6-only) para o Connection Pooler IPv4
    _m = re.search(r'@db\.([a-z0-9]+)\.supabase\.co(?::5432)?/', _raw_db_url)
    if _m:
        _ref = _m.group(1)
        _raw_db_url = re.sub(r'://postgres:', f'://postgres.{_ref}:', _raw_db_url)
        _raw_db_url = re.sub(r'db\.[a-z0-9]+\.supabase\.co(?::5432)?', 'aws-0-us-east-1.pooler.supabase.com:6543', _raw_db_url)
        if 'sslmode' not in _raw_db_url:
            _sep = '&' if '?' in _raw_db_url else '?'
            _raw_db_url = f"{_raw_db_url}{_sep}sslmode=require"

    # Suporte para URLs PostgreSQL do Supabase, Render e Railway que usam postgres:// ou postgresql://
    if _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif _raw_db_url.startswith("postgresql://") and not _raw_db_url.startswith("postgresql+"):
        _raw_db_url = _raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

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
