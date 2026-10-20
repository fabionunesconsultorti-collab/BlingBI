import os
import io
import json
import zipfile
import tempfile
import pytest
from datetime import datetime, timedelta

from app import create_app
from app.database import db
from app.config import Config, DATA_DIR
from app.models.master import MasterUser, MasterSegment, MasterBackupRecord, MasterBackupConfig
from app.core.tenant_manager import TenantManager
from app.services.backup_service import BackupService

@pytest.fixture
def test_app():
    test_db = tempfile.mktemp(suffix='_master_test.db')
    
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


def test_backup_create_and_zip_integrity(test_app):
    """Testa a geração de backup completo em ZIP, cálculo de SHA-256 e gravação do registro."""
    with test_app.app_context():
        with TenantManager.master_scope():
            # Cria dados fictícios no Master
            seg = MasterSegment.query.filter_by(slug='fashion').first()
            if not seg:
                seg = MasterSegment(name='Moda & Teste', slug='fashion', icon='👗')
                db.session.add(seg)
                db.session.commit()

        # Dispara criação do backup
        record = BackupService.create_backup(backup_type='manual', notes='Teste unitário de backup')

        assert record is not None
        assert record.filename.startswith('BlingBI_Backup_')
        assert record.filename.endswith('.zip')
        assert os.path.isfile(record.filepath)
        assert record.filesize_bytes > 0
        assert len(record.sha256) == 64

        # Inspeciona o arquivo ZIP gerado
        with zipfile.ZipFile(record.filepath, 'r') as zf:
            namelist = zf.namelist()
            assert 'backup_manifest.json' in namelist
            assert 'master/master_export.json' in namelist

            manifest = json.loads(zf.read('backup_manifest.json').decode('utf-8'))
            assert manifest['version'] == '2.0'
            assert manifest['backup_type'] == 'manual'
            assert 'files' in manifest

        # Limpa arquivo gerado
        if os.path.exists(record.filepath):
            os.remove(record.filepath)


def test_backup_scheduling_calculation():
    """Valida o cálculo do próximo agendamento para diferentes frequências."""
    cfg = MasterBackupConfig(
        auto_backup_enabled=True,
        frequency='daily',
        preferred_hour=3
    )
    base = datetime(2026, 10, 20, 2, 0, 0)
    next_run = BackupService.calculate_next_run(cfg, base_time=base)
    assert next_run == datetime(2026, 10, 20, 3, 0, 0)

    # Se já passou das 3h, agenda para o dia seguinte
    base_after = datetime(2026, 10, 20, 4, 0, 0)
    next_run_after = BackupService.calculate_next_run(cfg, base_time=base_after)
    assert next_run_after == datetime(2026, 10, 21, 3, 0, 0)

    # Frequência interval_hours
    cfg.frequency = 'interval_hours'
    cfg.interval_hours = 12
    next_interval = BackupService.calculate_next_run(cfg, base_time=base)
    assert next_interval == datetime(2026, 10, 20, 14, 0, 0)


def test_backup_rotation(test_app):
    """Testa a rotação automática mantendo apenas a quantidade configurada de arquivos."""
    with test_app.app_context():
        with TenantManager.master_scope():
            records = []
            for i in range(5):
                fake_path = tempfile.mktemp(suffix=f'_fake_{i}.zip')
                with open(fake_path, 'w') as f:
                    f.write("fake zip content")
                rec = MasterBackupRecord(
                    filename=f"fake_backup_{i}.zip",
                    filepath=fake_path,
                    filesize_bytes=16,
                    created_at=datetime.utcnow() - timedelta(minutes=10 - i)
                )
                db.session.add(rec)
                records.append(rec)
            db.session.commit()

            # Executa rotação para manter apenas 2
            BackupService.rotate_backups(max_keep=2)

            remaining = MasterBackupRecord.query.all()
            assert len(remaining) == 2

            # Limpa arquivos
            for r in records:
                if os.path.exists(r.filepath):
                    os.remove(r.filepath)


def test_admin_backup_routes_and_restore(test_app):
    """Testa as rotas HTTP de backup no painel admin e fluxo de restauração."""
    client = test_app.test_client()

    with test_app.app_context():
        with TenantManager.master_scope():
            admin = MasterUser.query.filter_by(role='admin').first()
            admin_id = admin.id

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['is_admin'] = True
        sess['role'] = 'admin'

    # 1. Acesso ao painel de backups
    res = client.get('/admin/backups')
    assert res.status_code == 200
    assert 'Central de Contingência & Backup Geral' in res.get_data(as_text=True)

    # 2. Salvar configurações de rotina
    res_cfg = client.post('/admin/backups/config', data={
        'auto_backup_enabled': '1',
        'frequency': 'daily',
        'preferred_hour': '4',
        'max_backups_to_keep': '15',
        'include_master': '1',
        'include_tenants': '1',
        'include_settings': '1'
    }, follow_redirects=True)
    assert res_cfg.status_code == 200
    assert 'Configurações de rotina de backup salvas' in res_cfg.get_data(as_text=True)

    # 3. Disparar criação de backup manual via rota
    res_create = client.post('/admin/backups/create', data={
        'notes': 'Backup disparado via teste de rotas'
    }, follow_redirects=True)
    assert res_create.status_code == 200
    assert 'gerado com sucesso' in res_create.get_data(as_text=True)

    # Obtém o arquivo gerado
    with test_app.app_context():
        with TenantManager.master_scope():
            latest = MasterBackupRecord.query.order_by(MasterBackupRecord.created_at.desc()).first()
            assert latest is not None
            backup_fname = latest.filename

    # 4. Download do backup
    res_dl = client.get(f'/admin/backups/download/{backup_fname}')
    assert res_dl.status_code == 200
    assert res_dl.headers.get('Content-Type') == 'application/zip'

    # 5. Restauração sem confirmação -> Bloqueado
    res_rest_fail = client.post(f'/admin/backups/restore/{backup_fname}', data={
        'confirmation': 'ERRADO',
        'restore_mode': 'full'
    }, follow_redirects=True)
    assert 'campo de verificação' in res_rest_fail.get_data(as_text=True)
    assert 'RESTAURAR' in res_rest_fail.get_data(as_text=True)

    # 6. Restauração com confirmação 'RESTAURAR' -> Sucesso
    res_rest_ok = client.post(f'/admin/backups/restore/{backup_fname}', data={
        'confirmation': 'RESTAURAR',
        'restore_mode': 'full'
    }, follow_redirects=True)
    assert res_rest_ok.status_code == 200
    assert 'Restauração (full) concluída com sucesso' in res_rest_ok.get_data(as_text=True)

    # 7. Exclusão do backup
    res_del = client.post(f'/admin/backups/delete/{backup_fname}', follow_redirects=True)
    assert res_del.status_code == 200
    assert 'excluído com sucesso' in res_del.get_data(as_text=True)
