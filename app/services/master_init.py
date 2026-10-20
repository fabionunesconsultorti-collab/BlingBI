import os
import logging
from app.database import db
from app.models.master import MasterUser, MasterSegment

logger = logging.getLogger(__name__)

DEFAULT_SEGMENTS = [
    {
        'slug': 'fashion',
        'name': 'Moda & Vestuário',
        'icon': '👗',
        'description': 'Lojas de roupas, calçados, bolsas, malas condicionais e consultoria de estilo.',
        'allowed_screens': ['dashboard', 'sales', 'products', 'customers', 'finance', 'fashion', 'reports', 'integrations'],
        'allowed_reports': ['fashion_bi', 'dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel'],
        'allowed_tabs': ['dashboard.kpis', 'dashboard.sales_timeline', 'dashboard.channels_pie', 'dashboard.top_products', 'dashboard.recent_orders', 'sales.overview', 'sales.multichannel', 'sales.sellers', 'sales.conditional_bags', 'products.overview', 'products.stock_analysis', 'products.pricing', 'products.abc', 'products.stock_coverage', 'products.returns', 'customers.overview', 'customers.rfm', 'customers.abc', 'customers.profiles', 'customers.birthdays', 'customers.nps', 'finance.overview', 'finance.dre', 'finance.cash_flow', 'finance.aging', 'finance.cash_statement', 'fashion.block1', 'fashion.block2', 'fashion.block3', 'fashion.block4']
    },
    {
        'slug': 'furniture_appliances',
        'name': 'Movelaria & Eletrodomésticos',
        'icon': '🛋️',
        'description': 'Móveis planejados, sofás, salas de jantar, eletrodomésticos e eletrônicos.',
        'allowed_screens': ['dashboard', 'sales', 'products', 'customers', 'finance', 'reports', 'integrations'],
        'allowed_reports': ['dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel'],
        'allowed_tabs': ['dashboard.kpis', 'dashboard.sales_timeline', 'dashboard.channels_pie', 'dashboard.top_products', 'dashboard.recent_orders', 'sales.overview', 'sales.multichannel', 'sales.sellers', 'products.overview', 'products.stock_analysis', 'products.pricing', 'products.abc', 'products.stock_coverage', 'customers.overview', 'customers.rfm', 'customers.abc', 'finance.overview', 'finance.dre', 'finance.cash_flow', 'finance.aging']
    },
    {
        'slug': 'food_restaurant',
        'name': 'Lanchonete, Bar & Restaurante',
        'icon': '🍔',
        'description': 'Restaurantes, hamburguerias, pizzarias, bares e serviços de alimentação.',
        'allowed_screens': ['dashboard', 'sales', 'customers', 'finance', 'reports', 'integrations'],
        'allowed_reports': ['dre', 'cash_flow', 'multichannel'],
        'allowed_tabs': ['dashboard.kpis', 'dashboard.sales_timeline', 'dashboard.channels_pie', 'dashboard.recent_orders', 'sales.overview', 'sales.sellers', 'customers.overview', 'customers.nps', 'finance.overview', 'finance.dre', 'finance.cash_flow', 'finance.cash_statement']
    },
    {
        'slug': 'home_varieties',
        'name': 'Utilidades Domésticas & Variedades',
        'icon': '🏠',
        'description': 'Artigos para o lar, presentes, bazar, decoração e organização.',
        'allowed_screens': ['dashboard', 'sales', 'products', 'customers', 'finance', 'reports', 'integrations'],
        'allowed_reports': ['dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel'],
        'allowed_tabs': ['dashboard.kpis', 'dashboard.sales_timeline', 'dashboard.channels_pie', 'dashboard.top_products', 'dashboard.recent_orders', 'sales.overview', 'sales.multichannel', 'products.overview', 'products.stock_analysis', 'products.pricing', 'products.abc', 'products.stock_coverage', 'customers.overview', 'customers.rfm', 'finance.overview', 'finance.dre', 'finance.cash_flow']
    },
    {
        'slug': 'toys',
        'name': 'Loja de Brinquedos & Lazer',
        'icon': '🧸',
        'description': 'Jogos, colecionáveis, brinquedos educativos e recreação infantil.',
        'allowed_screens': ['dashboard', 'sales', 'products', 'customers', 'finance', 'reports', 'integrations'],
        'allowed_reports': ['dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel'],
        'allowed_tabs': ['dashboard.kpis', 'dashboard.sales_timeline', 'dashboard.channels_pie', 'dashboard.top_products', 'dashboard.recent_orders', 'sales.overview', 'products.overview', 'products.stock_analysis', 'products.pricing', 'products.abc', 'customers.overview', 'customers.birthdays', 'finance.overview', 'finance.dre']
    },
    {
        'slug': 'retail_general',
        'name': 'Varejo Geral Comercial',
        'icon': '🏬',
        'description': 'Comércio varejista e atacadista multicanal (E-commerce + Loja Física).',
        'allowed_screens': ['dashboard', 'sales', 'products', 'customers', 'finance', 'reports', 'integrations'],
        'allowed_reports': ['dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel'],
        'allowed_tabs': ['dashboard.kpis', 'dashboard.sales_timeline', 'dashboard.channels_pie', 'dashboard.top_products', 'dashboard.recent_orders', 'sales.overview', 'sales.multichannel', 'sales.sellers', 'products.overview', 'products.stock_analysis', 'products.pricing', 'products.abc', 'products.stock_coverage', 'customers.overview', 'customers.rfm', 'customers.abc', 'customers.profiles', 'finance.overview', 'finance.dre', 'finance.cash_flow', 'finance.aging']
    },
    {
        'slug': 'services',
        'name': 'Prestação de Serviços & B2B',
        'icon': '💼',
        'description': 'Empresas de serviços, agências, consultorias e contratos recorrentes.',
        'allowed_screens': ['dashboard', 'sales', 'customers', 'finance', 'reports', 'integrations'],
        'allowed_reports': ['dre', 'cash_flow', 'rfm'],
        'allowed_tabs': ['dashboard.kpis', 'dashboard.sales_timeline', 'sales.overview', 'sales.sellers', 'customers.overview', 'customers.rfm', 'finance.overview', 'finance.dre', 'finance.cash_flow']
    }
]

def init_master_database():
    """
    Inicializa o banco Master:
    1. Cria as tabelas master se não existirem.
    2. Cadastra os segmentos padrão do sistema.
    3. Cria o usuário Super Administrador Geral ('admgeral') caso não exista.
    """
    try:
        from app.core.tenant_manager import TenantManager
        with TenantManager.master_scope():
            # 1. Garante que as tabelas master e operacionais padrão existam
            db.create_all()

            # 2. Inicializa os segmentos padrão
            for seg_data in DEFAULT_SEGMENTS:
                seg = MasterSegment.query.filter_by(slug=seg_data['slug']).first()
                if not seg:
                    seg = MasterSegment(
                        name=seg_data['name'],
                        slug=seg_data['slug'],
                        icon=seg_data['icon'],
                        description=seg_data['description'],
                        is_system_default=True
                    )
                    seg.allowed_screens = seg_data['allowed_screens']
                    seg.allowed_reports = seg_data['allowed_reports']
                    seg.allowed_tabs = seg_data['allowed_tabs']
                    db.session.add(seg)
                    logger.info(f"[MasterInit] Segmento padrão criado: {seg.name}")

            db.session.commit()

            # 3. Garante a existência do usuário 'admgeral'
            admin_user = MasterUser.query.filter_by(username='admgeral').first()
            default_password = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'admgeral2026')

            if not admin_user:
                admin_user = MasterUser(
                    username='admgeral',
                    email='admgeral@blingbi.com.br',
                    company_name='Administração Central BlingBI',
                    role='admin',
                    is_active=True
                )
                admin_user.set_password(default_password)
                db.session.add(admin_user)
                db.session.commit()
                logger.info(f"[MasterInit] Usuário Super Administrador 'admgeral' criado com sucesso!")
            else:
                # Garante que seja admin e esteja ativo
                if admin_user.role != 'admin' or not admin_user.is_active:
                    admin_user.role = 'admin'
                    admin_user.is_active = True
                    db.session.commit()

    except Exception as e:
        logger.error(f"[MasterInit] Erro ao inicializar Master Database: {e}", exc_info=True)
        db.session.rollback()
