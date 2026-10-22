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

    # 6. Endpoint de Sincronização de Canais do Bling
    res_sync = client.post('/products/pricing/sync-channels')
    assert res_sync.status_code == 200
    data_sync = res_sync.get_json()
    assert data_sync['success'] is True
    assert len(data_sync['channels']) >= 6

    # 7. Validação de HTML dos novos botões compactos e explicações em 2 linhas
    assert b'mkt-channel-container' in res_pricing.data
    assert b'mkt-channel-btn' in res_pricing.data
    assert b'mkt-channel-logo' in res_pricing.data
    assert b'An\xc3\xbancio Cl\xc3\xa1ssico' in res_pricing.data or b'Cl\xc3\xa1ssico' in res_pricing.data
    assert b'An\xc3\xbancio Premium 12x' in res_pricing.data or b'Premium' in res_pricing.data


def test_marketplace_rule_properties():
    """Valida as propriedades visuais de 2 linhas e chaves de logo do MarketplaceRule."""
    rule_ml = MarketplaceRule(channel='Mercado Livre Clássico', commission_percent=13.0)
    assert rule_ml.base_marketplace_name == 'Mercado Livre'
    assert rule_ml.short_rule_explanation == 'Anúncio Clássico'
    assert rule_ml.logo_key == 'mercadolivre'

    rule_ml_prem = MarketplaceRule(channel='Mercado Livre Premium', commission_percent=18.0)
    assert rule_ml_prem.base_marketplace_name == 'Mercado Livre'
    assert rule_ml_prem.short_rule_explanation == 'Anúncio Premium 12x'
    assert rule_ml_prem.logo_key == 'mercadolivre'

    rule_shopee = MarketplaceRule(channel='Shopee Frete Grátis', commission_percent=20.0)
    assert rule_shopee.base_marketplace_name == 'Shopee'
    assert rule_shopee.short_rule_explanation == 'Frete Grátis Extra'
    assert rule_shopee.logo_key == 'shopee'

    rule_amz = MarketplaceRule(channel='Amazon Brasil', commission_percent=15.0)
    assert rule_amz.base_marketplace_name == 'Amazon Brasil'
    assert rule_amz.logo_key == 'amazon'

    rule_via = MarketplaceRule(channel='Casas Bahia VIA VAREJO', commission_percent=16.0, bling_loja_id=205523454, bling_tipo='ViaVarejo')
    assert rule_via.base_marketplace_name == 'Via Varejo'
    assert rule_via.short_rule_explanation == 'Casas Bahia Marketplace'
    assert rule_via.logo_key == 'viavarejo'

    rule_madeira = MarketplaceRule(channel='Madeira Madeira', commission_percent=16.0, bling_loja_id=205534126, bling_tipo='MadeiraMadeira')
    assert rule_madeira.base_marketplace_name == 'Madeira Madeira'
    assert rule_madeira.short_rule_explanation == 'Móveis & Decoração'
    assert rule_madeira.logo_key == 'madeiramadeira'


def test_marketplace_bling_sync_and_price_reflection(app, client):
    """Testa sincronização de canais, busca de preços e reflexão de preço no Bling."""
    from unittest.mock import patch
    from app.services.pricing_engine import PricingEngine
    from app.models.product import Product, ProductChannelPrice
    from app.models.marketplace_rule import MarketplaceRule

    with app.app_context():
        # Cria produto de teste
        prod = Product.query.first()
        if not prod:
            prod = Product(name='Mesa de Jantar Madeira', sku='MESA-01', bling_id=999888777, cost=200.0, price=450.0)
            db.session.add(prod)
            db.session.commit()
        else:
            prod.bling_id = 999888777
            db.session.commit()

        # Mock de canais do Bling
        fake_channels = [
            {'id': 205523454, 'descricao': 'Casas Bahia VIA VAREJO', 'tipo': 'ViaVarejo', 'situacao': 1},
            {'id': 205534126, 'descricao': 'Madeira Madeira', 'tipo': 'MadeiraMadeira', 'situacao': 1},
            {'id': 205528382, 'descricao': 'Loja Virtual Integracommerce', 'tipo': 'IntegraCommerce', 'situacao': 1}
        ]

        with patch('app.services.bling_api.BlingApiClient.is_configured', return_value=True), \
             patch('app.services.bling_api.BlingApiClient.get_sales_channels', return_value=fake_channels):
            synced_rules = PricingEngine.sync_channels_from_bling()
            assert len(synced_rules) >= 3
            via_rule = next((r for r in synced_rules if r.bling_tipo == 'ViaVarejo'), None)
            assert via_rule is not None
            assert via_rule.bling_loja_id == 205523454
            assert via_rule.is_active is True

        # Mock de produtos da loja (/produtos/lojas)
        fake_store_products = [
            {
                'id': 855445832,
                'codigo': prod.sku,
                'preco': 499.90,
                'produto': {'id': prod.bling_id},
                'loja': {'id': 205523454}
            }
        ]

        with patch('app.services.bling_api.BlingApiClient.is_configured', return_value=True), \
             patch('app.services.bling_api.BlingApiClient.get_store_products', return_value=fake_store_products):
            count = PricingEngine.sync_channel_prices_from_bling(via_rule, max_items=10)
            assert count == 1

            cp = ProductChannelPrice.query.filter_by(product_id=prod.id, channel=via_rule.channel).first()
            assert cp is not None
            assert cp.price == 499.90
            assert cp.bling_produto_loja_id == 855445832
            assert cp.sync_status == 'synced'

        # Testa aplicação de novo preço refletindo no Bling
        with patch('app.services.bling_api.BlingApiClient.is_configured', return_value=True), \
             patch('app.services.bling_api.BlingApiClient.update_product_store_price', return_value=(True, 'Atualizado', {'id': 855445832})) as mock_update:
            applied = PricingEngine.apply_channel_price(
                product_id=prod.id,
                channel=via_rule.channel,
                new_price=549.00,
                margin_pct=25.0
            )
            assert applied is True
            mock_update.assert_called_once_with(
                bling_product_id=prod.bling_id,
                loja_id=via_rule.bling_loja_id,
                price=549.00,
                produto_loja_id=855445832
            )

            # Verifica registro atualizado
            cp_updated = ProductChannelPrice.query.filter_by(product_id=prod.id, channel=via_rule.channel).first()
            assert cp_updated.price == 549.00
            assert cp_updated.sync_status == 'synced'
            assert cp_updated.last_sync_at is not None

        # Testa endpoint POST /products/pricing/sync-store-prices
        with patch('app.services.bling_api.BlingApiClient.is_configured', return_value=True), \
             patch('app.services.bling_api.BlingApiClient.get_store_products', return_value=fake_store_products):
            resp = client.post('/products/pricing/sync-store-prices', json={'channel': via_rule.channel})
            assert resp.status_code == 200
            json_data = resp.get_json()
            assert json_data['success'] is True
            assert json_data['synced_count'] == 1


