import os
from flask import Flask, request, redirect, url_for, session, flash
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.config import Config
from app.database import db

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Ativa modo WAL e configurações de alta concorrência apenas para o SQLite."""
    if getattr(dbapi_connection, '__class__', None) and 'sqlite' in dbapi_connection.__class__.__module__.lower():
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

    # Inicializa SQLAlchemy com suporte a multi-tenancy dinâmico
    db.init_app(app)

    # Filtros customizados do Jinja2
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['number'] = format_number

    # Funções globais do Jinja2 para ativação/desativação dinâmica de abas e gráficos
    from app.core.feature_registry import FeatureRegistry
    app.jinja_env.globals['is_feature_enabled'] = FeatureRegistry.is_enabled

    # Função global do Jinja2 para checar se a tela é permitida para o segmento ativo
    def is_screen_allowed(screen_key):
        # Administrador geral operando normalmente enxerga tudo
        if session.get('is_admin') and not session.get('impersonate_user_id'):
            return True
        allowed = session.get('allowed_screens', [])
        return screen_key in allowed

    app.jinja_env.globals['is_screen_allowed'] = is_screen_allowed

    # Registro de Blueprints de Negócio & BI
    from app.routes.auth import bp as auth_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.sales import bp as sales_bp
    from app.routes.products import bp as products_bp
    from app.routes.customers import bp as customers_bp
    from app.routes.finance import bp as finance_bp
    from app.routes.integrations import bp as integrations_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.fashion_bi import bp as fashion_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(fashion_bp)

    # Mapeamento de Blueprints para telas do segmento
    BLUEPRINT_SCREEN_MAP = {
        'sales': 'sales',
        'products': 'products',
        'customers': 'customers',
        'finance': 'finance',
        'fashion': 'fashion',
        'integrations': 'integrations',
        'reports': 'reports'
    }

    # Interceptador global de autenticação e proteção por segmento
    @app.before_request
    def check_auth_and_segment_access():
        endpoint = request.endpoint or ''
        path = request.path or ''

        # 1. Rotas públicas isentas de login
        if (
            endpoint.startswith('auth.') or 
            endpoint == 'static' or 
            path.startswith('/static/') or 
            path == '/favicon.ico' or
            path == '/integrations/webhook'
        ):
            return None

        # 2. Exige login para todas as outras rotas
        if 'user_id' not in session:
            # Se for requisição de API
            if request.is_json or path.startswith('/api/'):
                from flask import jsonify
                return jsonify({'success': False, 'message': 'Autenticação necessária.'}), 401
            return redirect(url_for('auth.login', next=request.url))

        # 3. Administrador Geral (fora do modo impersonate) tem livre trânsito
        if session.get('is_admin') and not session.get('impersonate_user_id'):
            return None

        # 4. Verificação de tela do segmento para o blueprint acessado
        bp_name = request.blueprint
        if bp_name in BLUEPRINT_SCREEN_MAP:
            required_screen = BLUEPRINT_SCREEN_MAP[bp_name]
            allowed_screens = session.get('allowed_screens', [])
            if required_screen not in allowed_screens:
                flash(
                    f"A tela correspondente não está habilitada para o segmento cadastrado da sua empresa.",
                    'warning'
                )
                return redirect(url_for('dashboard.index'))

        return None

    # Inicializa Master DB e tabelas do sistema
    with app.app_context():
        from app.services.master_init import init_master_database
        init_master_database()
        
        # Garante migrações e descoberta de relatórios
        from app.services.migration import check_and_apply_migrations
        check_and_apply_migrations()
        from app.reports.registry import report_registry
        report_registry.discover_and_register_modules()

    return app
