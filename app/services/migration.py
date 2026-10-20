import logging
from sqlalchemy import text
from app.database import db

logger = logging.getLogger(__name__)

def check_and_apply_migrations():
    """
    Executa migrações não destrutivas (adicionando colunas ausentes) no SQLite.
    Garante compatibilidade retroativa com bancos já existentes em disco.
    """
    try:
        engine = db.engine
        if getattr(engine, 'dialect', None) and engine.dialect.name != 'sqlite':
            logger.info("[Migration] Base PostgreSQL/Supabase detectada. Migrações PRAGMA de SQLite ignoradas.")
            return

        with engine.connect() as conn:
            tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()]

            # 1. Colunas na tabela customers
            if 'customers' in tables:
                cust_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(customers);")).fetchall()]
                if 'birth_date' not in cust_cols:
                    conn.execute(text("ALTER TABLE customers ADD COLUMN birth_date DATE;"))
                if 'preferred_size' not in cust_cols:
                    conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_size VARCHAR(20);"))
                if 'preferred_style' not in cust_cols:
                    conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_style VARCHAR(50);"))

            # 2. Colunas na tabela products
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

            # 3. Colunas na tabela orders
            if 'orders' in tables:
                order_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(orders);")).fetchall()]
                if 'seller_name' not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN seller_name VARCHAR(100);"))
                if 'payment_method' not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(100);"))
                if 'notes' not in order_cols:
                    conn.execute(text("ALTER TABLE orders ADD COLUMN notes TEXT;"))

            # 4. Colunas na tabela order_items
            if 'order_items' in tables:
                item_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(order_items);")).fetchall()]
                if 'size' not in item_cols:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN size VARCHAR(20);"))
                if 'color' not in item_cols:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN color VARCHAR(50);"))
                if 'style' not in item_cols:
                    conn.execute(text("ALTER TABLE order_items ADD COLUMN style VARCHAR(50);"))

            # 5. Colunas na tabela conditional_bags
            if 'conditional_bags' in tables:
                bag_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(conditional_bags);")).fetchall()]
                if 'notes' not in bag_cols:
                    conn.execute(text("ALTER TABLE conditional_bags ADD COLUMN notes TEXT;"))

            # 6. Tabelas product_channel_prices e marketplace_rules se não existirem
            from app.models.marketplace_rule import MarketplaceRule
            from app.models.product import ProductChannelPrice
            db.metadata.create_all(bind=engine, tables=[
                db.metadata.tables['product_channel_prices'],
                db.metadata.tables['marketplace_rules']
            ])

            conn.commit()
    except Exception as e:
        logger.warning(f"Aviso de migração de colunas: {e}")
