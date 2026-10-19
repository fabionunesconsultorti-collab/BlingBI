import os
import logging
from contextlib import contextmanager
from threading import local
from flask import session, has_request_context
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# Armazenamento thread-local para overrides de contexto de tenant (ex: tarefas em background, testes)
_context_state = local()

class TenantManager:
    """
    Gerenciador Central de Conexões e Motores de Banco de Dados Multi-Tenant.
    Mantém cache de engines para evitar sobrecarga de conexões e gerencia o ciclo de vida
    de criação, migração e chaveamento dinâmico de bancos de dados por cliente.
    """
    _engines_cache = {}

    @classmethod
    def get_tenants_dir(cls) -> str:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        tenants_dir = os.path.join(base_dir, 'data', 'tenants')
        os.makedirs(tenants_dir, exist_ok=True)
        return tenants_dir

    @classmethod
    def build_sqlite_tenant_uri(cls, username: str) -> str:
        """Gera a URI do banco SQLite dedicado para o cliente especificado."""
        safe_name = "".join(c for c in username.lower() if c.isalnum() or c in ('_', '-'))
        filename = f"{safe_name}.db"
        filepath = os.path.join(cls.get_tenants_dir(), filename)
        return f"sqlite:///{filepath}"

    @classmethod
    def get_engine(cls, db_uri: str):
        """Retorna uma Engine do SQLAlchemy em cache ou cria uma nova com os parâmetros corretos."""
        if not db_uri:
            return None

        # Trata URLs postgres://
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)

        if db_uri in cls._engines_cache:
            return cls._engines_cache[db_uri]

        if db_uri.startswith("sqlite"):
            engine = create_engine(
                db_uri,
                poolclass=NullPool,
                connect_args={'timeout': 60, 'check_same_thread': False}
            )
            # Ativa WAL mode no SQLite
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                try:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA busy_timeout=60000")
                    cursor.close()
                except Exception:
                    pass
        else:
            engine = create_engine(
                db_uri,
                pool_pre_ping=True,
                pool_recycle=300
            )

        cls._engines_cache[db_uri] = engine
        return engine

    @classmethod
    def get_current_tenant_uri(cls) -> str:
        """
        Descobre a URI do banco de dados do tenant ativo no contexto atual:
        1. Contexto explícito (thread-local via with tenant_scope(uri))
        2. Sessão HTTP do Flask:
           - Se for 'impersonate_tenant_uri' (admgeral auditando cliente)
           - Se for 'tenant_db_uri' do usuário cliente autenticado
        3. Se não houver tenant ativo, retorna None (cai no banco padrão/master).
        """
        # 1. Override explícito no thread-local
        if hasattr(_context_state, 'tenant_uri') and _context_state.tenant_uri:
            return _context_state.tenant_uri

        # 2. Contexto de requisição Flask
        if has_request_context():
            # Admgeral auditando cliente
            impersonate_uri = session.get('impersonate_tenant_uri')
            if impersonate_uri:
                return impersonate_uri

            # Usuário cliente logado
            tenant_uri = session.get('tenant_db_uri')
            if tenant_uri:
                return tenant_uri

        return None

    @classmethod
    def test_connection(cls, db_uri: str) -> tuple[bool, str]:
        """Testa se a URI de banco é válida e acessível."""
        try:
            engine = cls.get_engine(db_uri)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
            return True, "Conexão estabelecida com sucesso!"
        except Exception as e:
            logger.error(f"[TenantManager] Falha ao testar conexão com {db_uri}: {e}")
            return False, f"Falha na conexão: {str(e)}"

    @classmethod
    def init_tenant_database(cls, db_uri: str):
        """
        Cria todas as tabelas operacionais do tenant (clientes, pedidos, produtos, financeiro, etc.)
        no banco alvo, garantindo que as tabelas mestres não sejam duplicadas.
        """
        from app.database import db
        engine = cls.get_engine(db_uri)

        # Filtra apenas tabelas operacionais do tenant (não mestres)
        tenant_tables = [
            table for name, table in db.metadata.tables.items()
            if not name.startswith('master_')
        ]

        logger.info(f"[TenantManager] Inicializando {len(tenant_tables)} tabelas operacionais em {db_uri}...")
        db.metadata.create_all(bind=engine, tables=tenant_tables)

        # Aplica migrações não destrutivas de colunas no SQLite
        if db_uri.startswith("sqlite"):
            try:
                with engine.connect() as conn:
                    # Customers
                    cust_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(customers);")).fetchall()]
                    if 'birth_date' not in cust_cols:
                        conn.execute(text("ALTER TABLE customers ADD COLUMN birth_date DATE;"))
                    if 'preferred_size' not in cust_cols:
                        conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_size VARCHAR(20);"))
                    if 'preferred_style' not in cust_cols:
                        conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_style VARCHAR(50);"))

                    # Products
                    prod_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(products);")).fetchall()]
                    if 'size' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN size VARCHAR(20);"))
                    if 'color' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN color VARCHAR(50);"))
                    if 'style' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN style VARCHAR(50);"))

                    # Orders
                    order_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(orders);")).fetchall()]
                    if 'seller_name' not in order_cols:
                        conn.execute(text("ALTER TABLE orders ADD COLUMN seller_name VARCHAR(100);"))
                    if 'payment_method' not in order_cols:
                        conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(100);"))
                    if 'notes' not in order_cols:
                        conn.execute(text("ALTER TABLE orders ADD COLUMN notes TEXT;"))

                    # Order Items
                    item_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(order_items);")).fetchall()]
                    if 'size' not in item_cols:
                        conn.execute(text("ALTER TABLE order_items ADD COLUMN size VARCHAR(20);"))
                    if 'color' not in item_cols:
                        conn.execute(text("ALTER TABLE order_items ADD COLUMN color VARCHAR(50);"))
                    if 'style' not in item_cols:
                        conn.execute(text("ALTER TABLE order_items ADD COLUMN style VARCHAR(50);"))

                    conn.commit()
            except Exception as e:
                logger.warning(f"[TenantManager] Aviso na migração do tenant {db_uri}: {e}")

        logger.info(f"[TenantManager] Banco de dados do tenant {db_uri} inicializado com sucesso!")

    @classmethod
    def seed_tenant_data(cls, db_uri: str, niche: str = 'fashion'):
        """Popula a base do tenant com dados de demonstração do nicho selecionado."""
        with cls.tenant_scope(db_uri):
            from app.services.niche_demo_data import seed_niche_demo_data
            seed_niche_demo_data(niche=niche, clear_first=True)
            logger.info(f"[TenantManager] Base de dados {db_uri} populada com dados demo de '{niche}'")

    @classmethod
    @contextmanager
    def tenant_scope(cls, db_uri: str):
        """Context manager para forçar a execução de queries em um banco de tenant específico."""
        prev = getattr(_context_state, 'tenant_uri', None)
        _context_state.tenant_uri = db_uri
        try:
            yield
        finally:
            _context_state.tenant_uri = prev

    @classmethod
    @contextmanager
    def master_scope(cls):
        """Context manager para forçar a execução de queries no banco Master."""
        prev = getattr(_context_state, 'tenant_uri', None)
        _context_state.tenant_uri = "__MASTER__"
        try:
            yield
        finally:
            _context_state.tenant_uri = prev
