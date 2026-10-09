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
        with engine.connect() as conn:
            # 1. Colunas na tabela customers
            cust_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(customers);")).fetchall()]
            if 'birth_date' not in cust_cols:
                conn.execute(text("ALTER TABLE customers ADD COLUMN birth_date DATE;"))
            if 'preferred_size' not in cust_cols:
                conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_size VARCHAR(20);"))
            if 'preferred_style' not in cust_cols:
                conn.execute(text("ALTER TABLE customers ADD COLUMN preferred_style VARCHAR(50);"))

            # 2. Colunas na tabela products
            prod_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(products);")).fetchall()]
            if 'size' not in prod_cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN size VARCHAR(20);"))
            if 'color' not in prod_cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN color VARCHAR(50);"))
            if 'style' not in prod_cols:
                conn.execute(text("ALTER TABLE products ADD COLUMN style VARCHAR(50);"))

            # 3. Colunas na tabela orders
            order_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(orders);")).fetchall()]
            if 'seller_name' not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN seller_name VARCHAR(100);"))
            if 'payment_method' not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(100);"))
            if 'notes' not in order_cols:
                conn.execute(text("ALTER TABLE orders ADD COLUMN notes TEXT;"))


            # 4. Colunas na tabela order_items
            item_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(order_items);")).fetchall()]
            if 'size' not in item_cols:
                conn.execute(text("ALTER TABLE order_items ADD COLUMN size VARCHAR(20);"))
            if 'color' not in item_cols:
                conn.execute(text("ALTER TABLE order_items ADD COLUMN color VARCHAR(50);"))
            if 'style' not in item_cols:
                conn.execute(text("ALTER TABLE order_items ADD COLUMN style VARCHAR(50);"))

            # 5. Colunas na tabela conditional_bags
            tables = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()]
            if 'conditional_bags' in tables:
                bag_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(conditional_bags);")).fetchall()]
                if 'notes' not in bag_cols:
                    conn.execute(text("ALTER TABLE conditional_bags ADD COLUMN notes TEXT;"))

            conn.commit()
    except Exception as e:
        logger.warning(f"Aviso de migração de colunas: {e}")
