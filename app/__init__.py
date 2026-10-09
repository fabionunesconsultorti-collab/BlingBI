from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.config import Config
from app.database import db

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Ativa modo WAL e configurações de alta concorrência para o SQLite."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.close()
    except Exception:
        pass

def format_currency(value):
    try:
        val = float(value or 0.0)
        formatted = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return "R$ 0,00"

def format_number(value):
    try:
        val = float(value or 0.0)
        return f"{val:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return "0"

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializa SQLAlchemy
    db.init_app(app)

    # Filtros customizados do Jinja2
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['number'] = format_number

    # Funções globais do Jinja2 para ativação/desativação dinâmica de abas e gráficos
    from app.core.feature_registry import FeatureRegistry
    app.jinja_env.globals['is_feature_enabled'] = FeatureRegistry.is_enabled

    # Registro de Blueprints
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.sales import bp as sales_bp
    from app.routes.products import bp as products_bp
    from app.routes.customers import bp as customers_bp
    from app.routes.finance import bp as finance_bp
    from app.routes.integrations import bp as integrations_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.fashion_bi import bp as fashion_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(fashion_bp)

    # Cria tabelas caso não existam e aplica migrações não-destrutivas de colunas
    with app.app_context():
        db.create_all()
        from app.services.migration import check_and_apply_migrations
        check_and_apply_migrations()
        from app.reports.registry import report_registry
        report_registry.discover_and_register_modules()

    return app
