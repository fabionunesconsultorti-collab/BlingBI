import os
import io
import json
import shutil
import zipfile
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

from app.database import db
from app.config import DATA_DIR
from app.models.master import MasterUser, MasterSegment, MasterBackupRecord, MasterBackupConfig
from app.core.tenant_manager import TenantManager

logger = logging.getLogger(__name__)

class BackupService:
    """
    Serviço Central de Contingência, Backup Geral e Restauração do BlingBI.
    Gerencia criação de snapshots compactados, integridade criptográfica,
    agendamento de rotinas e restauração assistida.
    """

    @classmethod
    def get_backups_dir(cls) -> str:
        backup_dir = os.path.join(DATA_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        return backup_dir

    @classmethod
    def calculate_file_sha256(cls, filepath: str) -> str:
        """Calcula o hash SHA-256 de um arquivo."""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def calculate_bytes_sha256(cls, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def calculate_next_run(cls, config: MasterBackupConfig, base_time: Optional[datetime] = None) -> datetime:
        """Calcula a data e hora do próximo backup programado."""
        now = base_time or datetime.utcnow()
        freq = config.frequency or 'daily'
        pref_hour = config.preferred_hour if config.preferred_hour is not None else 3

        if freq == 'interval_hours':
            hours = max(1, config.interval_hours or 24)
            return now + timedelta(hours=hours)

        # Configura horário do dia desejado
        target = now.replace(hour=pref_hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        if freq == 'daily':
            return target
        elif freq == 'weekly':
            # Próximo domingo no mesmo horário
            days_ahead = 6 - target.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return target + timedelta(days=days_ahead)
        elif freq == 'monthly':
            # Dia 1 do próximo mês
            year = target.year + (1 if target.month == 12 else 0)
            month = 1 if target.month == 12 else target.month + 1
            return target.replace(year=year, month=month, day=1)

        return target

    @classmethod
    def create_backup(cls, backup_type: str = 'manual', notes: Optional[str] = None) -> MasterBackupRecord:
        """
        Gera um backup completo e compactado do sistema BlingBI em formato ZIP.
        Empacota:
        1. Master Database (arquivo sqlite e/ou dump estrutural json)
        2. Bases de dados de todos os clientes (data/tenants/*.db)
        3. Configurações gerais e parâmetros operacionais
        4. Manifesto criptográfico de integridade (backup_manifest.json)
        """
        with TenantManager.master_scope():
            config = MasterBackupConfig.get_or_create()

        timestamp_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"BlingBI_Backup_{timestamp_str}.zip"
        zip_filepath = os.path.join(cls.get_backups_dir(), zip_filename)

        manifest: Dict[str, Any] = {
            'version': '2.0',
            'created_at': datetime.utcnow().isoformat(),
            'backup_type': backup_type,
            'notes': notes or '',
            'files': {},
            'stats': {}
        }

        with zipfile.ZipFile(zip_filepath, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Master Database & Tabelas Centrais
            if config.include_master:
                with TenantManager.master_scope():
                    users = [u.to_dict() for u in MasterUser.query.all()]
                    segments = [s.to_dict() for s in MasterSegment.query.all()]
                    
                    master_json_bytes = json.dumps({
                        'users': users,
                        'segments': segments,
                        'exported_at': datetime.utcnow().isoformat()
                    }, indent=2, ensure_ascii=False).encode('utf-8')

                    zf.writestr('master/master_export.json', master_json_bytes)
                    manifest['files']['master/master_export.json'] = {
                        'sha256': cls.calculate_bytes_sha256(master_json_bytes),
                        'size': len(master_json_bytes)
                    }
                    manifest['stats']['master_users_count'] = len(users)
                    manifest['stats']['master_segments_count'] = len(segments)

                # Se o banco Master for SQLite local, copia o arquivo físico
                master_sqlite_path = os.path.join(DATA_DIR, 'bling_bi.db')
                if os.path.isfile(master_sqlite_path):
                    try:
                        zf.write(master_sqlite_path, arcname='master/bling_bi.db')
                        manifest['files']['master/bling_bi.db'] = {
                            'sha256': cls.calculate_file_sha256(master_sqlite_path),
                            'size': os.path.getsize(master_sqlite_path)
                        }
                    except Exception as e:
                        logger.warning(f"Não foi possível incluir master sqlite direto: {e}")

            # 2. Bases Dedicadas de Tenants
            if config.include_tenants:
                tenants_dir = TenantManager.get_tenants_dir()
                tenant_files_count = 0
                if os.path.isdir(tenants_dir):
                    for fname in os.listdir(tenants_dir):
                        if fname.endswith('.db'):
                            fpath = os.path.join(tenants_dir, fname)
                            if os.path.isfile(fpath):
                                arc_name = f"tenants/{fname}"
                                zf.write(fpath, arcname=arc_name)
                                manifest['files'][arc_name] = {
                                    'sha256': cls.calculate_file_sha256(fpath),
                                    'size': os.path.getsize(fpath)
                                }
                                tenant_files_count += 1
                manifest['stats']['tenants_db_count'] = tenant_files_count

            # 3. Configurações do Sistema
            if config.include_settings:
                try:
                    from app.models.setting import Setting
                    settings_dict = {}
                    with TenantManager.master_scope():
                        for item in Setting.query.all():
                            settings_dict[item.key] = item.value

                    settings_bytes = json.dumps(settings_dict, indent=2, ensure_ascii=False).encode('utf-8')
                    zf.writestr('config/settings.json', settings_bytes)
                    manifest['files']['config/settings.json'] = {
                        'sha256': cls.calculate_bytes_sha256(settings_bytes),
                        'size': len(settings_bytes)
                    }
                except Exception as e:
                    logger.debug(f"Configurações operacionais não exportadas: {e}")

            # 4. Grava manifesto no ZIP
            manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode('utf-8')
            zf.writestr('backup_manifest.json', manifest_bytes)

        filesize = os.path.getsize(zip_filepath)
        zip_sha256 = cls.calculate_file_sha256(zip_filepath)

        # Grava registro histórico no banco Master
        with TenantManager.master_scope():
            record = MasterBackupRecord(
                filename=zip_filename,
                filepath=zip_filepath,
                filesize_bytes=filesize,
                backup_type=backup_type,
                status='success',
                sha256=zip_sha256,
                manifest_json=json.dumps(manifest, ensure_ascii=False),
                notes=notes
            )
            db.session.add(record)

            # Atualiza controle de agendamento
            config.last_backup_at = datetime.utcnow()
            config.next_backup_at = cls.calculate_next_run(config)
            db.session.commit()

            # Rotação de backups antigos
            cls.rotate_backups(config.max_backups_to_keep)

        logger.info(f"Backup concluído com sucesso: {zip_filename} ({filesize} bytes, SHA256: {zip_sha256[:8]}...)")
        return record

    @classmethod
    def restore_backup(
        cls, 
        source_zip_path: str, 
        restore_mode: str = 'full'
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Restaura o sistema a partir de um arquivo de backup ZIP.
        restore_mode:
          - 'full': Restaura Master DB, todos os Tenants e Configurações
          - 'tenants_only': Restaura apenas as bases de clientes
          - 'settings_only': Restaura apenas configurações e segmentos
        """
        if not os.path.isfile(source_zip_path):
            return False, f"Arquivo de backup não encontrado: {source_zip_path}", {}

        if not zipfile.is_zipfile(source_zip_path):
            return False, "O arquivo fornecido não é um arquivo ZIP válido.", {}

        # Limpa cache de conexões para permitir sobrescrever arquivos SQLite com segurança
        TenantManager._engines_cache.clear()

        stats = {
            'restored_tenants': 0,
            'restored_users': 0,
            'restored_segments': 0,
            'restored_files': []
        }

        try:
            with zipfile.ZipFile(source_zip_path, 'r') as zf:
                namelist = zf.namelist()

                # 1. Valida manifesto se existir
                manifest_data = {}
                if 'backup_manifest.json' in namelist:
                    manifest_data = json.loads(zf.read('backup_manifest.json').decode('utf-8'))

                # 2. Restauração de Tenants
                if restore_mode in ('full', 'tenants_only'):
                    tenants_dir = TenantManager.get_tenants_dir()
                    os.makedirs(tenants_dir, exist_ok=True)
                    for item in namelist:
                        if item.startswith('tenants/') and item.endswith('.db'):
                            fname = os.path.basename(item)
                            target_path = os.path.join(tenants_dir, fname)
                            with zf.open(item) as src, open(target_path, 'wb') as dst:
                                shutil.copyfileobj(src, dst)
                            stats['restored_tenants'] += 1
                            stats['restored_files'].append(item)

                # 3. Restauração de Configurações e Segmentos
                if restore_mode in ('full', 'settings_only', 'master_only'):
                    # Restaura arquivo SQLite master se aplicável
                    if restore_mode == 'full' and 'master/bling_bi.db' in namelist:
                        master_sqlite_path = os.path.join(DATA_DIR, 'bling_bi.db')
                        try:
                            with zf.open('master/bling_bi.db') as src, open(master_sqlite_path, 'wb') as dst:
                                shutil.copyfileobj(src, dst)
                            stats['restored_files'].append('master/bling_bi.db')
                        except Exception as e:
                            logger.warning(f"Não foi possível sobrescrever master sqlite diretamente: {e}")

                    # Restaura dados a partir do JSON portátil
                    if 'master/master_export.json' in namelist:
                        master_data = json.loads(zf.read('master/master_export.json').decode('utf-8'))
                        with TenantManager.master_scope():
                            # Segmentos
                            for s_data in master_data.get('segments', []):
                                seg = MasterSegment.query.filter_by(slug=s_data['slug']).first()
                                if not seg:
                                    seg = MasterSegment(
                                        name=s_data['name'],
                                        slug=s_data['slug'],
                                        icon=s_data.get('icon', '📊'),
                                        description=s_data.get('description'),
                                        is_system_default=s_data.get('is_system_default', False)
                                    )
                                    db.session.add(seg)
                                seg.allowed_screens = s_data.get('allowed_screens', [])
                                seg.allowed_tabs = s_data.get('allowed_tabs', [])
                                seg.allowed_reports = s_data.get('allowed_reports', [])
                                stats['restored_segments'] += 1

                            db.session.commit()

                            # Usuários Clientes
                            for u_data in master_data.get('users', []):
                                if u_data.get('username') == 'admgeral':
                                    continue  # Preserva credencial atual do admgeral
                                user = MasterUser.query.filter_by(username=u_data['username']).first()
                                if not user:
                                    user = MasterUser(
                                        username=u_data['username'],
                                        email=u_data['email'],
                                        company_name=u_data['company_name'],
                                        role=u_data.get('role', 'client'),
                                        db_type=u_data.get('db_type', 'sqlite'),
                                        db_uri=u_data.get('db_uri'),
                                        is_active=u_data.get('is_active', True),
                                        segment_id=u_data.get('segment_id')
                                    )
                                    user.set_password('Mudar@123456')
                                    db.session.add(user)
                                    stats['restored_users'] += 1
                                else:
                                    user.company_name = u_data.get('company_name', user.company_name)
                                    user.segment_id = u_data.get('segment_id', user.segment_id)
                                    user.db_uri = u_data.get('db_uri', user.db_uri)

                            db.session.commit()

                    # Restaura settings chave-valor
                    if 'config/settings.json' in namelist:
                        try:
                            from app.models.setting import Setting
                            settings_dict = json.loads(zf.read('config/settings.json').decode('utf-8'))
                            with TenantManager.master_scope():
                                for k, v in settings_dict.items():
                                    Setting.set(k, v)
                            stats['restored_files'].append('config/settings.json')
                        except Exception as e:
                            logger.debug(f"Erro ao restaurar settings: {e}")

            # Limpa cache novamente para garantir que próximas queries peguem os dados novos
            TenantManager._engines_cache.clear()
            msg = f"Restauração ({restore_mode}) concluída com sucesso! Bases restauradas: {stats['restored_tenants']}, Usuários: {stats['restored_users']}, Segmentos: {stats['restored_segments']}."
            logger.info(msg)
            return True, msg, stats

        except Exception as e:
            logger.error(f"Erro crítico durante restauração de backup: {e}", exc_info=True)
            return False, f"Falha na restauração: {str(e)}", stats

    @classmethod
    def rotate_backups(cls, max_keep: int = 10):
        """
        Remove backups antigos excedentes do disco e da tabela de registros.
        """
        if max_keep <= 0:
            return

        with TenantManager.master_scope():
            records = MasterBackupRecord.query.order_by(MasterBackupRecord.created_at.desc()).all()
            if len(records) > max_keep:
                to_delete = records[max_keep:]
                for rec in to_delete:
                    try:
                        if rec.filepath and os.path.isfile(rec.filepath):
                            os.remove(rec.filepath)
                        db.session.delete(rec)
                        logger.info(f"Backup rotacionado e removido: {rec.filename}")
                    except Exception as e:
                        logger.warning(f"Erro ao rotacionar backup {rec.filename}: {e}")
                db.session.commit()

    @classmethod
    def check_and_run_scheduled_backup(cls):
        """
        Verifica se há rotina de backup agendada pendente e executa caso o horário tenha chegado.
        """
        try:
            with TenantManager.master_scope():
                config = MasterBackupConfig.get_or_create()
                if not config.auto_backup_enabled:
                    return

                now = datetime.utcnow()
                if config.next_backup_at is None:
                    config.next_backup_at = cls.calculate_next_run(config)
                    db.session.commit()
                    return

                if now >= config.next_backup_at:
                    logger.info("Executando rotina programada de backup automático...")
                    cls.create_backup(backup_type='scheduled', notes='Backup automático programado')
        except Exception as e:
            logger.error(f"Erro ao verificar rotina programada de backup: {e}")
