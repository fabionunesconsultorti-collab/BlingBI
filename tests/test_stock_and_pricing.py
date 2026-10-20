import pytest
from app.database import db
from app.models.product import Product, ProductChannelPrice
from app.models.marketplace_rule import MarketplaceRule
from app.services.pricing_engine import PricingEngine
from app.services.stock_analysis_service import StockAnalysisService


def test_pricing_engine_calculation():
    """Testa cálculo de markup reverso com regras de marketplace abaixo e acima de R$ 79."""
    # 1. Produto com custo baixo (R$ 20.00) no Mercado Livre Clássico -> Preço esperado < 79 (com taxa fixa de R$ 6.50)
    calc_low = PricingEngine.calculate_price_for_cost(
        cost=20.0,
        commission_percent=13.0,
        tax_percent=6.0,
        operational_percent=3.0,
        target_margin_percent=20.0,
        fixed_fee=6.50,
        fixed_fee_threshold=79.0,
        free_shipping_threshold=79.0,
        shipping_cost=22.50
    )
    assert calc_low['suggested_price'] > 20.0
    assert calc_low['suggested_price'] < 79.0
    assert calc_low['fixed_fee_rs'] == 6.50
    assert calc_low['shipping_rs'] == 0.0
    assert calc_low['net_profit_rs'] > 0
    assert abs(calc_low['margin_percent'] - 20.0) < 0.5

    # 2. Produto com custo alto (R$ 60.00) no Mercado Livre Clássico -> Preço esperado >= 79 (com frete seller de R$ 22.50)
    calc_high = PricingEngine.calculate_price_for_cost(
        cost=60.0,
        commission_percent=13.0,
        tax_percent=6.0,
        operational_percent=3.0,
        target_margin_percent=20.0,
        fixed_fee=6.50,
        fixed_fee_threshold=79.0,
        free_shipping_threshold=79.0,
        shipping_cost=22.50
    )
    assert calc_high['suggested_price'] >= 79.0
    assert calc_high['fixed_fee_rs'] == 0.0
    assert calc_high['shipping_rs'] == 22.50
    assert calc_high['net_profit_rs'] > 0
    assert abs(calc_high['margin_percent'] - 20.0) < 0.5


def test_stock_analysis_service_filtering(app):
    """Testa a agregação analítica e filtros avançados de estoque."""
    with app.app_context():
        # Cria produto de teste com ruptura e outro com estoque normal
        p1 = Product(
            bling_id=888001,
            sku='TEST-RUPTURA-01',
            name='Produto Teste Ruptura Total',
            cost=25.0,
            purchase_cost=22.0,
            price=60.0,
            stock=0.0,
            min_stock=10.0,
            category='Teste Especial'
        )
        p2 = Product(
            bling_id=888002,
            sku='TEST-NORMAL-02',
            name='Produto Teste Estoque Alto',
            cost=50.0,
            purchase_cost=45.0,
            price=120.0,
            stock=40.0,
            min_stock=5.0,
            category='Teste Especial'
        )
        db.session.add_all([p1, p2])
        db.session.commit()

        # 1. Filtro geral
        res_all = StockAnalysisService.get_stock_analysis({'category': 'Teste Especial'})
        assert res_all['summary']['filtered_count'] == 2

        # 2. Filtro por status de ruptura
        res_ruptura = StockAnalysisService.get_stock_analysis({'category': 'Teste Especial', 'stock_status': 'out_of_stock'})
        assert res_ruptura['summary']['filtered_count'] == 1
        assert res_ruptura['products'][0]['sku'] == 'TEST-RUPTURA-01'

        # 3. Filtro por busca textual
        res_search = StockAnalysisService.get_stock_analysis({'q': 'RUPTURA-01'})
        assert res_search['summary']['filtered_count'] == 1
        assert res_search['products'][0]['name'] == 'Produto Teste Ruptura Total'


def test_inline_update_product_and_channel_price(app):
    """Testa a atualização direta inline de custos e preços por canal."""
    with app.app_context():
        prod = Product(
            bling_id=888003,
            sku='TEST-INLINE-01',
            name='Produto Teste Inline',
            cost=30.0,
            purchase_cost=28.0,
            price=80.0,
            stock=15.0,
            category='Teste'
        )
        db.session.add(prod)
        db.session.commit()

        # 1. Atualiza custo
        r1 = StockAnalysisService.update_product_inline(prod.id, 'cost', 35.50)
        assert r1['success'] is True
        assert prod.cost == 35.50

        # 2. Atualiza valor pago
        r2 = StockAnalysisService.update_product_inline(prod.id, 'purchase_cost', 32.80)
        assert r2['success'] is True
        assert prod.purchase_cost == 32.80

        # 3. Atualiza preço no canal Mercado Livre
        r3 = StockAnalysisService.update_product_inline(prod.id, 'channel_price', 99.90, channel='Mercado Livre')
        assert r3['success'] is True

        cp = ProductChannelPrice.query.filter_by(product_id=prod.id, channel='Mercado Livre').first()
        assert cp is not None
        assert cp.price == 99.90


def test_routes_stock_analysis_and_pricing(client):
    """Testa os endpoints HTTP das novas telas no cliente Flask autenticado."""
    # 1. Tela de Análise de Estoque
    res_stock = client.get('/products/stock-analysis')
    assert res_stock.status_code == 200
    assert b'An\xc3\xa1lise de Estoque' in res_stock.data or b'Estoque' in res_stock.data

    # 2. Exportação Excel
    res_excel = client.get('/products/stock-analysis/export-excel')
    assert res_excel.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res_excel.content_type

    # 3. Tela de Precificação de Marketplaces
    res_pricing = client.get('/products/pricing')
    assert res_pricing.status_code == 200
    assert b'Mercado Livre' in res_pricing.data

    # 4. Simulação de Preço via API
    res_sim = client.post('/products/pricing/simulate', json={
        'cost': 40.0,
        'commission_percent': 14.0,
        'target_margin_percent': 22.0
    })
    assert res_sim.status_code == 200
    data_sim = res_sim.get_json()
    assert data_sim['success'] is True
    assert data_sim['calculation']['suggested_price'] > 40.0

    # 5. Aplicação de Preço em Lote
    prod = Product.query.first()
    assert prod is not None
    res_apply = client.post('/products/pricing/apply', json={
        'product_ids': [prod.id],
        'channel': 'Mercado Livre Clássico',
        'custom_target_margin': 25.0
    })
    assert res_apply.status_code == 200
    data_apply = res_apply.get_json()
    assert data_apply['success'] is True
    assert data_apply['applied_count'] == 1
