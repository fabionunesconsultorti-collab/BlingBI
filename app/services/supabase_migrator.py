import os
import logging
from typing import Dict, Any, Tuple, Optional, List
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from app.database import db
from app.config import Config, DATA_DIR
from app.models.master import MasterUser, MasterSegment, MasterBackupConfig, MasterBackupRecord
from app.core.tenant_manager import TenantManager

logger = logging.getLogger(__name__)

class SupabaseMigrator:
    """
    Serviço de Migração Automatizada de Dados de SQLite para Supabase (PostgreSQL).
    Migra o banco Master para o schema 'public' e cada banco de cliente para um schema dedicado 'tenant_{username}'.
    """

    @classmethod
    def resolve_target_url(cls, target_url: Optional[str] = None) -> str:
        url = target_url or os.environ.get('SUPABASE_DB_URL') or os.environ.get('DATABASE_URL') or ''
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url.strip()

    @classmethod
    def test_connection(cls, target_url: Optional[str] = None) -> Tuple[bool, str]:
        """Testa se a URL de conexão com o Supabase é válida e acessível."""
        url = cls.resolve_target_url(target_url)
        if not url:
            return False, "Nenhuma URL de conexão com o Supabase foi informada ou configurada nas variáveis de ambiente."

        try:
            engine = create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 10})
            with engine.connect() as conn:
                res = conn.execute(text("SELECT version();")).fetchone()
                version = res[0] if res else 'PostgreSQL'
            return True, f"Conexão com o Supabase estabelecida com sucesso! ({version.split()[0]} {version.split()[1]})"
        except Exception as e:
            logger.error(f"[SupabaseMigrator] Erro de conexão com Supabase: {e}")
            return False, f"Falha na conexão: {str(e)}"

    @classmethod
    def migrate_all_to_supabase(cls, target_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Executa a migração integral de dados de SQLite para o Supabase.
        1. Cria tabelas do Master DB no schema 'public' do Supabase.
        2. Migra segmentos, usuários administradores e clientes.
        3. Para cada cliente com base SQLite, cria o schema 'tenant_{username}' no Supabase
           e migra todas as tabelas operacionais (pedidos, clientes, produtos, financeiro).
        4. Atualiza os ponteiros dos clientes para operarem nos novos schemas no Supabase.
        """
        url = cls.resolve_target_url(target_url)
        if not url:
            return {
                'success': False,
                'message': 'URL de conexão do Supabase não fornecida.',
                'stats': {}
            }

        stats = {
            'segments_migrated': 0,
            'users_migrated': 0,
            'tenants_migrated': 0,
            'tables_migrated_count': 0,
            'rows_migrated_count': 0,
            'details': []
        }

        try:
            target_engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)

            # ==================================================================
            # FASE 1: Master Database no schema 'public'
            # ==================================================================
            logger.info("[SupabaseMigrator] Fase 1: Criando tabelas master no Supabase...")
            master_tables = [
                table for name, table in db.metadata.tables.items()
                if name.startswith('master_')
            ]
            db.metadata.create_all(bind=target_engine, tables=master_tables)

            TargetSession = sessionmaker(bind=target_engine)
            target_session = TargetSession()

            # Migra Segmentos
            with TenantManager.master_scope():
                local_segments = MasterSegment.query.all()
                for seg in local_segments:
                    existing_seg = target_session.query(MasterSegment).filter_by(slug=seg.slug).first()
                    if not existing_seg:
                        new_seg = MasterSegment(
                            name=seg.name,
                            slug=seg.slug,
                            icon=seg.icon,
                            description=seg.description,
                            allowed_screens_json=seg.allowed_screens_json,
                            allowed_tabs_json=seg.allowed_tabs_json,
                            allowed_reports_json=seg.allowed_reports_json,
                            is_system_default=seg.is_system_default
                        )
                        target_session.add(new_seg)
                        stats['segments_migrated'] += 1
                target_session.commit()

            # Migra Usuários Master
            with TenantManager.master_scope():
                local_users = MasterUser.query.all()
                for u in local_users:
                    existing_user = target_session.query(MasterUser).filter_by(username=u.username).first()
                    if not existing_user:
                        target_seg_id = None
                        if u.segment:
                            t_seg = target_session.query(MasterSegment).filter_by(slug=u.segment.slug).first()
                            if t_seg:
                                target_seg_id = t_seg.id

                        new_user = MasterUser(
                            username=u.username,
                            email=u.email,
                            password_hash=u.password_hash,
                            company_name=u.company_name,
                            role=u.role,
                            segment_id=target_seg_id,
                            db_type=u.db_type,
                            db_uri=u.db_uri,
                            is_active=u.is_active
                        )
                        target_session.add(new_user)
                        stats['users_migrated'] += 1
                target_session.commit()

            stats['details'].append(f"Master DB migrado: {stats['segments_migrated']} segmentos e {stats['users_migrated']} usuários.")

            # ==================================================================
            # FASE 2: Migração de Tenants para Schemas no Supabase
            # ==================================================================
            with TenantManager.master_scope():
                clients = MasterUser.query.filter_by(role='client').all()

            for client in clients:
                safe_name = "".join(c for c in client.username.lower() if c.isalnum() or c == '_')
                schema_name = f"tenant_{safe_name}"

                logger.info(f"[SupabaseMigrator] Processando tenant '{client.username}' para schema '{schema_name}'...")

                # 1. Cria schema no Supabase
                with target_engine.connect() as conn:
                    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";'))
                    conn.commit()

                # 2. Cria tabelas operacionais dentro do schema
                schema_engine = target_engine.execution_options(schema_translate_map={None: schema_name})
                tenant_tables = [
                    table for name, table in db.metadata.tables.items()
                    if not name.startswith('master_')
                ]
                db.metadata.create_all(bind=schema_engine, tables=tenant_tables)

                # 3. Descobre o arquivo SQLite de origem do tenant
                source_sqlite_path = None
                if client.db_uri and 'sqlite' in client.db_uri:
                    clean_path = client.db_uri.replace('sqlite:///', '')
                    if os.path.isfile(clean_path):
                        source_sqlite_path = clean_path

                if not source_sqlite_path:
                    default_path = os.path.join(TenantManager.get_tenants_dir(), f"{safe_name}.db")
                    if os.path.isfile(default_path):
                        source_sqlite_path = default_path

                # Se houver arquivo SQLite, migra os dados
                migrated_rows_tenant = 0
                if source_sqlite_path and os.path.isfile(source_sqlite_path):
                    source_engine = create_engine(f"sqlite:///{source_sqlite_path}")
                    src_inspector = inspect(source_engine)
                    src_tables = src_inspector.get_table_names()

                    with source_engine.connect() as s_conn, target_engine.connect() as t_conn:
                        for tbl in tenant_tables:
                            if tbl.name in src_tables:
                                rows = s_conn.execute(text(f"SELECT * FROM {tbl.name};")).fetchall()
                                if rows:
                                    # Pega os nomes das colunas
                                    cols = [c.name for c in tbl.columns]
                                    for row in rows:
                                        row_dict = dict(row._mapping)
                                        # Filtra colunas válidas
                                        filtered = {k: v for k, v in row_dict.items() if k in cols}
                                        col_names = ", ".join([f'"{k}"' for k in filtered.keys()])
                                        param_placeholders = ", ".join([f":{k}" for k in filtered.keys()])
                                        insert_sql = text(f'INSERT INTO "{schema_name}"."{tbl.name}" ({col_names}) VALUES ({param_placeholders}) ON CONFLICT DO NOTHING;')
                                        try:
                                            t_conn.execute(insert_sql, filtered)
                                            migrated_rows_tenant += 1
                                        except Exception as err:
                                            logger.debug(f"Aviso ao inserir linha em {schema_name}.{tbl.name}: {err}")
                                    t_conn.commit()

                # 4. Atualiza usuário no Supabase para apontar para o novo schema
                target_user = target_session.query(MasterUser).filter_by(username=client.username).first()
                if target_user:
                    target_user.db_type = 'postgres_schema'
                    target_user.db_uri = f"schema:{schema_name}"
                    target_session.commit()

                # Atualiza também na base local atual
                with TenantManager.master_scope():
                    local_client = MasterUser.query.filter_by(username=client.username).first()
                    if local_client:
                        local_client.db_type = 'postgres_schema'
                        local_client.db_uri = f"schema:{schema_name}"
                        db.session.commit()

                stats['tenants_migrated'] += 1
                stats['rows_migrated_count'] += migrated_rows_tenant
                stats['details'].append(f"Cliente '{client.company_name}' -> Schema '{schema_name}' ({migrated_rows_tenant} registros migrados).")

            target_session.close()

            # Limpa cache do TenantManager para aplicar conexões novas
            TenantManager._engines_cache.clear()

            return {
                'success': True,
                'message': f"🎉 Migração para o Supabase concluída com sucesso! {stats['tenants_migrated']} cliente(s) e {stats['rows_migrated_count']} registros migrados.",
                'stats': stats
            }

        except Exception as e:
            logger.error(f"[SupabaseMigrator] Erro durante a migração: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"Erro durante a migração: {str(e)}",
                'stats': stats
            }
