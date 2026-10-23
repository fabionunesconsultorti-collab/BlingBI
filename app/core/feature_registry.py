import logging
from typing import Dict, Any, List, Optional
from functools import wraps
from flask import flash, redirect, url_for, request, jsonify
from app.models.setting import Setting

logger = logging.getLogger(__name__)

# Catálogo mestre com todas as abas, dashboards, relatórios e blocos de gráficos
FEATURES_CATALOG: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 1. DASHBOARD 360° (GRÁFICOS E WIDGETS)
    # -------------------------------------------------------------------------
    {
        'key': 'dashboard.kpis',
        'sector': 'dashboard',
        'sector_name': 'Dashboard 360°',
        'name': 'Cards de KPIs Principais',
        'type': 'widget',
        'description': 'Métricas do topo: Faturamento Total, Pedidos Atendidos, Ticket Médio e Previsões A Receber/Pagar.',
        'default': True
    },
    {
        'key': 'dashboard.sales_timeline',
        'sector': 'dashboard',
        'sector_name': 'Dashboard 360°',
        'name': 'Gráfico de Evolução de Vendas',
        'type': 'chart',
        'description': 'Gráfico diário de evolução temporal do faturamento e contagem de pedidos.',
        'default': True
    },
    {
        'key': 'dashboard.channels_pie',
        'sector': 'dashboard',
        'sector_name': 'Dashboard 360°',
        'name': 'Gráfico de Vendas por Canal',
        'type': 'chart',
        'description': 'Gráfico de rosca distribuindo vendas entre Mercado Livre, Shopee, Loja Física e Site.',
        'default': True
    },
    {
        'key': 'dashboard.top_products',
        'sector': 'dashboard',
        'sector_name': 'Dashboard 360°',
        'name': 'Tabela Top 5 Produtos Faturados',
        'type': 'widget',
        'description': 'Ranking dos produtos com maior receita acumulada na janela selecionada.',
        'default': True
    },
    {
        'key': 'dashboard.recent_orders',
        'sector': 'dashboard',
        'sector_name': 'Dashboard 360°',
        'name': 'Tabela de Últimos Pedidos',
        'type': 'widget',
        'description': 'Lista dos últimos pedidos de venda recebidos em tempo real.',
        'default': True
    },

    # -------------------------------------------------------------------------
    # 2. VENDAS E PEDIDOS (SETOR COMERCIAL)
    # -------------------------------------------------------------------------
    {
        'key': 'sales.overview',
        'sector': 'sales',
        'sector_name': 'Vendas & Comercial',
        'name': 'Aba Visão Geral & Pedidos',
        'type': 'tab',
        'description': 'Tabela analítica de pedidos, buscas por CPF/nº e impressão térmica 78mm.',
        'url': '/sales/',
        'default': True
    },
    {
        'key': 'sales.multichannel',
        'sector': 'sales',
        'sector_name': 'Vendas & Comercial',
        'name': 'Aba Performance Multicanal & Margem',
        'type': 'tab',
        'description': 'Margem de contribuição limpa por canal deduzindo CMV e fretes.',
        'url': '/sales/multichannel',
        'default': True
    },
    {
        'key': 'sales.sellers',
        'sector': 'sales',
        'sector_name': 'Vendas & Comercial',
        'name': 'Aba Produtividade & Vendedores',
        'type': 'tab',
        'description': 'Ranking de vendedores, ticket médio e comissões estimadas.',
        'url': '/sales/sellers',
        'default': True
    },
    {
        'key': 'sales.conditional_bags',
        'sector': 'sales',
        'sector_name': 'Vendas & Comercial',
        'name': 'Aba Malas Condicionais (Bags)',
        'type': 'tab',
        'description': 'Gestão de envio e conversão de malas de roupas para prova em casa.',
        'url': '/sales/conditional-bags',
        'default': True
    },

    # -------------------------------------------------------------------------
    # 3. PRODUTOS E ESTOQUE
    # -------------------------------------------------------------------------
    {
        'key': 'products.overview',
        'sector': 'products',
        'sector_name': 'Produtos & Estoque',
        'name': 'Aba Catálogo Geral de Produtos',
        'type': 'tab',
        'description': 'Lista completa de produtos com saldos de estoque e preço de venda.',
        'url': '/products/',
        'default': True
    },
    {
        'key': 'products.abc',
        'sector': 'products',
        'sector_name': 'Produtos & Estoque',
        'name': 'Aba Curva ABC de Produtos',
        'type': 'tab',
        'description': 'Classificação 80/15/5 dos produtos mais relevantes por receita.',
        'url': '/products/abc',
        'default': True
    },
    {
        'key': 'products.stock_coverage',
        'sector': 'products',
        'sector_name': 'Produtos & Estoque',
        'name': 'Aba Cobertura de Estoque & Ruptura',
        'type': 'tab',
        'description': 'Dias de cobertura e alertas antecipados de ruptura ou excesso.',
        'url': '/products/stock-coverage',
        'default': True
    },
    {
        'key': 'products.stock_analysis',
        'sector': 'products',
        'sector_name': 'Produtos & Estoque',
        'name': 'Aba Análise de Estoque & Preços por Canal',
        'type': 'tab',
        'description': 'Visão aprofundada de estoque com múltiplos filtros, valores por canal e edição de custos.',
        'url': '/products/stock-analysis',
        'default': True
    },
    {
        'key': 'products.pricing',
        'sector': 'products',
        'sector_name': 'Produtos & Estoque',
        'name': 'Aba Precificação Automática Marketplaces',
        'type': 'tab',
        'description': 'Formação inteligente de preço de venda e margens com regras de comissão e frete por canal.',
        'url': '/products/pricing',
        'default': True
    },
    {
        'key': 'products.returns',
        'sector': 'products',
        'sector_name': 'Produtos & Estoque',
        'name': 'Aba Trocas e Devoluções por SKU',
        'type': 'tab',
        'description': 'Análise de devoluções por defeito, tamanho ou modelagem.',
        'url': '/products/returns',
        'default': True
    },

    # -------------------------------------------------------------------------
    # 4. CLIENTES E CRM
    # -------------------------------------------------------------------------
    {
        'key': 'customers.overview',
        'sector': 'customers',
        'sector_name': 'Clientes & CRM',
        'name': 'Aba Base Geral de Clientes',
        'type': 'tab',
        'description': 'Listagem de clientes com histórico de compras e valor total gasto.',
        'url': '/customers/',
        'default': True
    },
    {
        'key': 'customers.rfm',
        'sector': 'customers',
        'sector_name': 'Clientes & CRM',
        'name': 'Aba Segmentação RFM de Clientes',
        'type': 'tab',
        'description': 'Clusters da base: Campeões, Fiéis, Em Risco e Hibernando.',
        'url': '/customers/rfm',
        'default': True
    },
    {
        'key': 'customers.abc',
        'sector': 'customers',
        'sector_name': 'Clientes & CRM',
        'name': 'Aba Curva ABC de Clientes',
        'type': 'tab',
        'description': 'Concentração de receita pelos melhores clientes da carteira.',
        'url': '/customers/abc',
        'default': True
    },
    {
        'key': 'customers.profiles',
        'sector': 'customers',
        'sector_name': 'Clientes & CRM',
        'name': 'Aba Perfis de Compra',
        'type': 'tab',
        'description': 'Categorias favoritas e ticket médio por perfil de cliente.',
        'url': '/customers/profiles',
        'default': True
    },
    {
        'key': 'customers.birthdays',
        'sector': 'customers',
        'sector_name': 'Clientes & CRM',
        'name': 'Aba Aniversariantes do Mês',
        'type': 'tab',
        'description': 'Ações de marketing para aniversariantes com envio de cupons.',
        'url': '/customers/birthdays',
        'default': True
    },
    {
        'key': 'customers.nps',
        'sector': 'customers',
        'sector_name': 'Clientes & CRM',
        'name': 'Aba Pesquisas NPS e CSAT',
        'type': 'tab',
        'description': 'Índice de recomendação pós-venda e satisfação dos clientes.',
        'url': '/customers/nps',
        'default': True
    },

    # -------------------------------------------------------------------------
    # 5. FINANCEIRO E DRE
    # -------------------------------------------------------------------------
    {
        'key': 'finance.overview',
        'sector': 'finance',
        'sector_name': 'Financeiro & Controladoria',
        'name': 'Aba Visão Geral Financeira',
        'type': 'tab',
        'description': 'Resumo financeiro, fluxo realizado e DRE sintético.',
        'url': '/finance/',
        'default': True
    },
    {
        'key': 'finance.accounts',
        'sector': 'finance',
        'sector_name': 'Financeiro & Controladoria',
        'name': 'Aba Contas a Pagar & Receber',
        'type': 'tab',
        'description': 'Lançamentos detalhados de contas a pagar e receber, baixas no BI e calendário de vencimentos.',
        'url': '/finance/accounts',
        'default': True
    },
    {
        'key': 'finance.dre',
        'sector': 'finance',
        'sector_name': 'Financeiro & Controladoria',
        'name': 'Aba DRE Gerencial por Competência',
        'type': 'tab',
        'description': 'Demonstrativo do resultado com dedução de CMV, despesas e lucro.',
        'url': '/finance/dre',
        'default': True
    },
    {
        'key': 'finance.cash_flow',
        'sector': 'finance',
        'sector_name': 'Financeiro & Controladoria',
        'name': 'Aba Projeção de Fluxo de Caixa',
        'type': 'tab',
        'description': 'Previsão diária por regime de caixa para os próximos 30 dias.',
        'url': '/finance/cash-flow',
        'default': True
    },
    {
        'key': 'finance.aging',
        'sector': 'finance',
        'sector_name': 'Financeiro & Controladoria',
        'name': 'Aba Aging List / Inadimplência',
        'type': 'tab',
        'description': 'Faixas de atraso de títulos a receber para cobrança.',
        'url': '/finance/aging',
        'default': True
    },
    {
        'key': 'finance.cash_statement',
        'sector': 'finance',
        'sector_name': 'Financeiro & Controladoria',
        'name': 'Aba Fechamento de Caixa Diário',
        'type': 'tab',
        'description': 'Extrato diário e conferência de caixa da loja física.',
        'url': '/finance/cash-statement',
        'default': True
    },

    # -------------------------------------------------------------------------
    # 6. VAREJO DE MODA & VESTUÁRIO
    # -------------------------------------------------------------------------
    {
        'key': 'fashion.block1',
        'sector': 'fashion',
        'sector_name': 'Moda & Vestuário',
        'name': 'Aba Perfil de Compra & Curva ABC',
        'type': 'tab',
        'description': 'Comportamento de compra e classificação dos clientes de moda.',
        'url': '/fashion/?tab=block1',
        'default': True
    },
    {
        'key': 'fashion.block2',
        'sector': 'fashion',
        'sector_name': 'Moda & Vestuário',
        'name': 'Aba Malas Condicionais & Trocas',
        'type': 'tab',
        'description': 'Conversão de malas consignadas e trocas por modelagem.',
        'url': '/fashion/?tab=block2',
        'default': True
    },
    {
        'key': 'fashion.block3',
        'sector': 'fashion',
        'sector_name': 'Moda & Vestuário',
        'name': 'Aba Desempenho do Atendimento',
        'type': 'tab',
        'description': 'Conversão de prospecções de clientes e vendedores.',
        'url': '/fashion/?tab=block3',
        'default': True
    },
    {
        'key': 'fashion.block4',
        'sector': 'fashion',
        'sector_name': 'Moda & Vestuário',
        'name': 'Aba Fidelização, Inativos & NPS',
        'type': 'tab',
        'description': 'Clientes inativos por faixas de dias e pesquisas de pós-venda.',
        'url': '/fashion/?tab=block4',
        'default': True
    }
]

class FeatureRegistry:
    """
    Gerenciador Central de Ativação/Desativação de Abas, Dashboards e Gráficos.
    Garante que qualquer elemento da interface possa ser ligado/desligado individualmente.
    """

    @classmethod
    def is_enabled(cls, feature_key: str) -> bool:
        """Verifica se a funcionalidade/aba/gráfico está ativa no banco."""
        # Se for um relatório, sincroniza com a chave report_<id>_enabled
        if feature_key.startswith('report.'):
            rep_id = feature_key.split('.', 1)[1]
            return Setting.get(f"report_{rep_id}_enabled", "1") == "1"

        val = Setting.get(f"feature_{feature_key}_enabled", "1")
        return val == "1"

    @classmethod
    def set_enabled(cls, feature_key: str, enabled: bool) -> None:
        """Ativa ou desativa a funcionalidade/aba/gráfico."""
        if feature_key.startswith('report.'):
            rep_id = feature_key.split('.', 1)[1]
            Setting.set(f"report_{rep_id}_enabled", "1" if enabled else "0")
            return

        Setting.set(f"feature_{feature_key}_enabled", "1" if enabled else "0")
        logger.info(f"[FeatureRegistry] Feature '{feature_key}' alterada para enabled={enabled}")

    @classmethod
    def toggle(cls, feature_key: str) -> Optional[bool]:
        """Inverte o estado atual da funcionalidade/aba/gráfico."""
        found = any(f['key'] == feature_key for f in FEATURES_CATALOG) or feature_key.startswith('report.')
        if not found:
            return None
        new_state = not cls.is_enabled(feature_key)
        cls.set_enabled(feature_key, new_state)
        return new_state

    @classmethod
    def get_catalog_grouped(cls) -> Dict[str, Dict[str, Any]]:
        """Retorna o catálogo completo agrupado por setor com status de ativação."""
        grouped: Dict[str, Dict[str, Any]] = {}
        for item in FEATURES_CATALOG:
            sec = item['sector']
            if sec not in grouped:
                grouped[sec] = {
                    'sector_id': sec,
                    'sector_name': item['sector_name'],
                    'features': []
                }
            item_copy = dict(item)
            item_copy['is_enabled'] = cls.is_enabled(item['key'])
            grouped[sec]['features'].append(item_copy)

        return grouped

    @classmethod
    def get_all_features(cls) -> List[Dict[str, Any]]:
        """Retorna lista plana de todas as features com seus estados atuais."""
        res = []
        for item in FEATURES_CATALOG:
            item_copy = dict(item)
            item_copy['is_enabled'] = cls.is_enabled(item['key'])
            res.append(item_copy)
        return res

def requires_feature(feature_key: str, fallback_endpoint: str = 'dashboard.index'):
    """
    Decorador para proteger rotas HTTP.
    Se a aba/funcionalidade estiver desativada, bloqueia o acesso graciosamente.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not FeatureRegistry.is_enabled(feature_key):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'success': False,
                        'message': 'Esta funcionalidade está desativada pelo operador.'
                    }), 403
                flash('Esta aba ou funcionalidade foi temporariamente desativada pelo administrador.', 'warning')
                return redirect(url_for(fallback_endpoint))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
