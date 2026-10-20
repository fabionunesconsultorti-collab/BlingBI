import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from app import create_app
from app.database import db
from app.config import Config
from app.models.master import MasterUser, MasterSegment
from app.core.tenant_manager import TenantManager
from app.services.supabase_migrator import SupabaseMigrator


@pytest.fixture
def test_app():
    test_db = tempfile.mktemp(suffix='_master_supabase_test.db')

    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{test_db}'
        WTF_CSRF_ENABLED = False
        SECRET_KEY = 'test-secret'

    app = create_app(TestConfig)

    with app.app_context():
        with TenantManager.master_scope():
            db.create_all()

    yield app

    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass


def test_resolve_target_url():
    # Test postgres:// -> postgresql+psycopg2:// conversion
    url = "postgres://user:pass@host:5432/dbname"
    resolved = SupabaseMigrator.resolve_target_url(url)
    assert resolved == "postgresql+psycopg2://user:pass@host:5432/dbname"

    # Test postgresql:// -> postgresql+psycopg2://
    url2 = "postgresql://user:pass@host:5432/dbname"
    assert SupabaseMigrator.resolve_target_url(url2) == "postgresql+psycopg2://user:pass@host:5432/dbname"

    # Test stripping whitespace
    assert SupabaseMigrator.resolve_target_url("  postgresql://host/db  ") == "postgresql+psycopg2://host/db"

    # Test fallback to env
    with patch.dict(os.environ, {'SUPABASE_DB_URL': 'postgresql://envuser:envpass@ep-host:6543/postgres'}):
        assert SupabaseMigrator.resolve_target_url(None) == 'postgresql+psycopg2://envuser:envpass@ep-host:6543/postgres'


def test_tenant_manager_postgres_schema_helpers():
    # Helper to build schema URI
    uri = TenantManager.build_postgres_schema_uri("Loja_Test-123!")
    assert uri == "schema:tenant_loja_test123"

    # When no postgres is configured
    with patch('app.config.Config.IS_POSTGRES', False):
        assert TenantManager.is_postgres_active() is False

    # When postgres is configured
    with patch('app.config.Config.IS_POSTGRES', True):
        assert TenantManager.is_postgres_active() is True


def test_test_connection_empty():
    with patch.dict(os.environ, {}, clear=True):
        success, msg = SupabaseMigrator.test_connection("")
        assert success is False
        assert "Nenhuma URL" in msg


def test_test_connection_mock_success():
    with patch('app.services.supabase_migrator.create_engine') as mock_engine:
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ["PostgreSQL 15.4 on x86_64"]
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        success, msg = SupabaseMigrator.test_connection("postgresql://test:test@host:5432/db")
        assert success is True
        assert "Conexão com o Supabase estabelecida com sucesso" in msg


def test_test_connection_mock_failure():
    with patch('app.services.supabase_migrator.create_engine', side_effect=Exception("Host unreachable")):
        success, msg = SupabaseMigrator.test_connection("postgresql://invalid:invalid@localhost:9999/db")
        assert success is False
        assert "Host unreachable" in msg


def test_migrate_all_to_supabase_no_url():
    with patch.dict(os.environ, {}, clear=True):
        res = SupabaseMigrator.migrate_all_to_supabase(target_url=None)
        assert res['success'] is False
        assert "URL de conexão do Supabase não fornecida" in res['message']


def test_admin_supabase_migration_routes(test_app):
    client = test_app.test_client()

    with test_app.app_context():
        with TenantManager.master_scope():
            # Seed admgeral and a segment
            seg = MasterSegment.query.filter_by(slug='varejo').first()
            if not seg:
                seg = MasterSegment(name='Varejo Geral', slug='varejo', icon='🛒', is_system_default=True)
                db.session.add(seg)
                db.session.commit()

            admin = MasterUser.query.filter_by(username='admgeral').first()
            if not admin:
                admin = MasterUser(username='admgeral', role='admin', is_active=True)
                admin.set_password('123456')
                db.session.add(admin)
                db.session.commit()
            admin_id = admin.id

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['is_admin'] = True
        sess['role'] = 'admin'

    # 1. GET /admin/migrate-supabase
    resp = client.get('/admin/migrate-supabase')
    assert resp.status_code == 200
    assert 'Assistente de Migração para PostgreSQL / Supabase' in resp.get_data(as_text=True)

    # 2. POST /admin/migrate-supabase/test with mock
    with patch.object(SupabaseMigrator, 'test_connection', return_value=(True, 'Conexão OK')):
        resp_test = client.post('/admin/migrate-supabase/test', json={'supabase_url': 'postgresql://test@host/db'})
        assert resp_test.status_code == 200
        data = resp_test.get_json()
        assert data['success'] is True
        assert data['message'] == 'Conexão OK'

    # 3. POST /admin/migrate-supabase/run with mock
    with patch.object(SupabaseMigrator, 'migrate_all_to_supabase', return_value={
        'success': True,
        'message': 'Migração simulada com sucesso!',
        'stats': {'tenants_migrated': 1, 'rows_migrated_count': 10, 'details': ['OK']}
    }):
        resp_run = client.post('/admin/migrate-supabase/run', json={'supabase_url': 'postgresql://test@host/db'})
        assert resp_run.status_code == 200
        data = resp_run.get_json()
        assert data['success'] is True
        assert 'Migração simulada' in data['message']
