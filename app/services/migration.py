import logging
from sqlalchemy import text
from app.database import db

logger = logging.getLogger(__name__)

def check_and_apply_migrations():
    """
    Executa migrações não destrutivas (adicionando colunas ausentes) no SQLite
    e em todos os schemas PostgreSQL/Supabase (public e tenant_*).
    Garante compatibilidade retroativa com bancos já existentes em disco e na nuvem.
    """
    try:
        engine = db.engine
        dialect_name = getattr(engine, 'dialect', None) and engine.dialect.name

        # 1. Migrações para SQLite
        if dialect_name == 'sqlite':
            with engine.connect() as conn:
                tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()]

                # Colunas na tabela customers
                if 'customers' in tables:
                    cust_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(customers);")).fetchall()]
                    if 'birth_date' not in cust_cols:
                        conn.execute(text("ALTER TABLE customers ADD COLUMN birth_date DATE;"))
                    if 'preferred_size' not in cust_cols:
                        conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_size VARCHAR(20);"))
                    if 'preferred_style' not in cust_cols:
                        conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_style VARCHAR(50);"))

                # Colunas na tabela products
                if 'products' in tables:
                    prod_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(products);")).fetchall()]
                    if 'size' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN size VARCHAR(20);"))
                    if 'color' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN color VARCHAR(50);"))
                    if 'style' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN style VARCHAR(50);"))
                    if 'purchase_cost' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN purchase_cost FLOAT DEFAULT 0.0;"))
                    if 'min_stock' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN min_stock FLOAT DEFAULT 5.0;"))
                    if 'lead_time_days' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN lead_time_days INTEGER DEFAULT 7;"))
                    if 'weight_kg' not in prod_cols:
                        conn.execute(text("ALTER TABLE products ADD COLUMN weight_kg FLOAT DEFAULT 0.3;"))

                # Colunas na tabela orders
                if 'orders' in tables:
                    order_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(orders);")).fetchall()]
                    if 'seller_name' not in order_cols:
                        conn.execute(text("ALTER TABLE orders ADD COLUMN seller_name VARCHAR(100);"))
                    if 'payment_method' not in order_cols:
                        conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(100);"))
                    if 'notes' not in order_cols:
                        conn.execute(text("ALTER TABLE orders ADD COLUMN notes TEXT;"))

                # Colunas na tabela order_items
                if 'order_items' in tables:
                    item_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(order_items);")).fetchall()]
                    if 'size' not in item_cols:
                        conn.execute(text("ALTER TABLE order_items ADD COLUMN size VARCHAR(20);"))
                    if 'color' not in item_cols:
                        conn.execute(text("ALTER TABLE order_items ADD COLUMN color VARCHAR(50);"))
                    if 'style' not in item_cols:
                        conn.execute(text("ALTER TABLE order_items ADD COLUMN style VARCHAR(50);"))

                # Colunas na tabela conditional_bags
                if 'conditional_bags' in tables:
                    bag_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(conditional_bags);")).fetchall()]
                    if 'notes' not in bag_cols:
                        conn.execute(text("ALTER TABLE conditional_bags ADD COLUMN notes TEXT;"))

                # Colunas em marketplace_rules
                if 'marketplace_rules' in tables:
                    rule_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(marketplace_rules);")).fetchall()]
                    if 'bling_loja_id' not in rule_cols:
                        conn.execute(text("ALTER TABLE marketplace_rules ADD COLUMN bling_loja_id BIGINT;"))
                    if 'bling_tipo' not in rule_cols:
                        conn.execute(text("ALTER TABLE marketplace_rules ADD COLUMN bling_tipo VARCHAR(50);"))

                # Colunas em product_channel_prices
                if 'product_channel_prices' in tables:
                    pcp_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(product_channel_prices);")).fetchall()]
                    if 'bling_produto_loja_id' not in pcp_cols:
                        conn.execute(text("ALTER TABLE product_channel_prices ADD COLUMN bling_produto_loja_id BIGINT;"))
                    if 'bling_loja_id' not in pcp_cols:
                        conn.execute(text("ALTER TABLE product_channel_prices ADD COLUMN bling_loja_id BIGINT;"))
                    if 'sync_status' not in pcp_cols:
                        conn.execute(text("ALTER TABLE product_channel_prices ADD COLUMN sync_status VARCHAR(30) DEFAULT 'synced';"))
                    if 'last_sync_at' not in pcp_cols:
                        conn.execute(text("ALTER TABLE product_channel_prices ADD COLUMN last_sync_at TIMESTAMP;"))

                # Colunas em financial_entries
                if 'financial_entries' in tables:
                    fe_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(financial_entries);")).fetchall()]
                    if 'notes' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN notes TEXT;"))
                    if 'discount' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN discount FLOAT DEFAULT 0.0;"))
                    if 'fine_fee' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN fine_fee FLOAT DEFAULT 0.0;"))
                    if 'bling_contact_id' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN bling_contact_id BIGINT;"))
                    if 'bling_category_id' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN bling_category_id BIGINT;"))
                    if 'bling_payment_method_id' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN bling_payment_method_id BIGINT;"))
                    if 'sync_status' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN sync_status VARCHAR(30) DEFAULT 'synced';"))
                    if 'last_sync_at' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN last_sync_at TIMESTAMP;"))
                    if 'sync_error_msg' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN sync_error_msg TEXT;"))
                    if 'competence_date' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN competence_date DATE;"))
                    if 'bling_bordero_id' not in fe_cols:
                        conn.execute(text("ALTER TABLE financial_entries ADD COLUMN bling_bordero_id BIGINT;"))

                # Tabelas product_channel_prices e marketplace_rules se não existirem
                from app.models.marketplace_rule import MarketplaceRule
                from app.models.product import ProductChannelPrice
                from app.models.financial import FinancialEntry
                db.metadata.create_all(bind=engine, tables=[
                    db.metadata.tables['product_channel_prices'],
                    db.metadata.tables['marketplace_rules'],
                    db.metadata.tables['financial_entries']
                ])

                conn.commit()

        # 2. Migrações para PostgreSQL / Supabase
        from app.config import Config
        if getattr(Config, 'IS_POSTGRES', False) or dialect_name == 'postgresql':
            from app.core.tenant_manager import TenantManager
            base_engine = TenantManager.get_engine(Config.SQLALCHEMY_DATABASE_URI)
            if base_engine:
                with base_engine.connect() as pg_conn:
                    # Descobre todos os schemas do banco
                    schema_rows = pg_conn.execute(text(
                        "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%' OR schema_name = 'public';"
                    )).fetchall()
                    schemas = [r[0] for r in schema_rows]

                    for schema in schemas:
                        # Garante que as tabelas existem no schema
                        for q in [
                            f'''CREATE TABLE IF NOT EXISTS "{schema}".marketplace_rules (
                                id SERIAL PRIMARY KEY,
                                channel VARCHAR(100) NOT NULL,
                                channel_display_name VARCHAR(100),
                                icon VARCHAR(50) DEFAULT '🏪',
                                commission_percent FLOAT DEFAULT 16.0,
                                fixed_fee FLOAT DEFAULT 0.0,
                                fixed_fee_threshold FLOAT DEFAULT 79.0,
                                free_shipping_threshold FLOAT DEFAULT 79.0,
                                default_shipping_cost FLOAT DEFAULT 0.0,
                                tax_percent FLOAT DEFAULT 6.0,
                                operational_cost_percent FLOAT DEFAULT 3.0,
                                target_margin_percent FLOAT DEFAULT 20.0,
                                is_active BOOLEAN DEFAULT TRUE,
                                bling_loja_id BIGINT,
                                bling_tipo VARCHAR(50),
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            );''',
                            f'''CREATE TABLE IF NOT EXISTS "{schema}".product_channel_prices (
                                id SERIAL PRIMARY KEY,
                                product_id INTEGER NOT NULL REFERENCES "{schema}".products(id) ON DELETE CASCADE,
                                rule_id INTEGER NOT NULL REFERENCES "{schema}".marketplace_rules(id) ON DELETE CASCADE,
                                price FLOAT NOT NULL,
                                bling_produto_loja_id BIGINT,
                                bling_loja_id BIGINT,
                                sync_status VARCHAR(30) DEFAULT 'synced',
                                last_sync_at TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                CONSTRAINT uq_{schema.replace('-', '_')}_product_rule UNIQUE (product_id, rule_id)
                            );''',
                            # Adiciona colunas se a tabela já existia antes
                            f'ALTER TABLE "{schema}".marketplace_rules ADD COLUMN IF NOT EXISTS bling_loja_id BIGINT;',
                            f'ALTER TABLE "{schema}".marketplace_rules ADD COLUMN IF NOT EXISTS bling_tipo VARCHAR(50);',
                            f'ALTER TABLE "{schema}".product_channel_prices ADD COLUMN IF NOT EXISTS bling_produto_loja_id BIGINT;',
                            f'ALTER TABLE "{schema}".product_channel_prices ADD COLUMN IF NOT EXISTS bling_loja_id BIGINT;',
                            f'ALTER TABLE "{schema}".product_channel_prices ADD COLUMN IF NOT EXISTS sync_status VARCHAR(30) DEFAULT \'synced\';',
                            f'ALTER TABLE "{schema}".product_channel_prices ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS notes TEXT;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS discount FLOAT DEFAULT 0.0;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS fine_fee FLOAT DEFAULT 0.0;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS bling_contact_id BIGINT;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS bling_category_id BIGINT;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS bling_payment_method_id BIGINT;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS sync_status VARCHAR(30) DEFAULT \'synced\';',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS sync_error_msg TEXT;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS competence_date DATE;',
                            f'ALTER TABLE "{schema}".financial_entries ADD COLUMN IF NOT EXISTS bling_bordero_id BIGINT;'
                        ]:
                            try:
                                pg_conn.execute(text(q))
                            except Exception as q_err:
                                logger.debug(f"[Migration] Aviso ao executar no schema '{schema}': {q_err}")

                    pg_conn.commit()
                    logger.info(f"[Migration] Migrações de marketplace e preços concluídas para schemas: {schemas}")
    except Exception as e:
        logger.warning(f"Aviso de migração de colunas: {e}")

