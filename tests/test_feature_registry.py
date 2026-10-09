import json
import pytest
from app.core.feature_registry import FeatureRegistry, FEATURES_CATALOG
from app.models.setting import Setting


def test_feature_catalog_and_defaults(app):
    """Verifica se o catálogo mestre contém todas as abas, dashboards e gráficos esperados."""
    with app.app_context():
        catalog = FeatureRegistry.get_all_features()
        assert len(catalog) >= 25
        
        sectors = {f['sector'] for f in catalog}
        assert {'dashboard', 'sales', 'products', 'customers', 'finance', 'fashion'}.issubset(sectors)
        
        # Padrão é True para todos os itens cadastrados
        for item in catalog:
            assert FeatureRegistry.is_enabled(item['key']) is True


def test_feature_toggle_and_persistence(app):
    """Testa se a ativação e desativação persiste no banco de dados via Setting."""
    with app.app_context():
        key = 'sales.sellers'
        assert FeatureRegistry.is_enabled(key) is True

        # Desativa
        FeatureRegistry.set_enabled(key, False)
        assert FeatureRegistry.is_enabled(key) is False
        assert Setting.get(f"feature_{key}_enabled") == "0"

        # Toggle inverte para True
        res = FeatureRegistry.toggle(key)
        assert res is True
        assert FeatureRegistry.is_enabled(key) is True
        assert Setting.get(f"feature_{key}_enabled") == "1"

        # Toggle inverte para False
        res = FeatureRegistry.toggle(key)
        assert res is False
        assert FeatureRegistry.is_enabled(key) is False


def test_route_guard_redirects_when_feature_disabled(client, app):
    """Verifica se rotas de abas desativadas são bloqueadas com redirect e mensagem explicativa."""
    with app.app_context():
        # Desativa a aba de Vendedores
        FeatureRegistry.set_enabled('sales.sellers', False)

    response = client.get('/sales/sellers', follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Esta aba ou funcionalidade foi temporariamente desativada" in html

    # Reativa e acessa novamente
    with app.app_context():
        FeatureRegistry.set_enabled('sales.sellers', True)

    response = client.get('/sales/sellers')
    assert response.status_code == 200


def test_route_guard_finance_and_products(client, app):
    """Valida bloqueio em abas de Financeiro e Produtos."""
    with app.app_context():
        FeatureRegistry.set_enabled('finance.dre', False)
        FeatureRegistry.set_enabled('products.returns', False)

    # Acesso a DRE bloqueado
    resp_dre = client.get('/finance/dre')
    assert resp_dre.status_code == 302

    # Acesso a Devoluções bloqueado
    resp_ret = client.get('/products/returns')
    assert resp_ret.status_code == 302

    # Reativa finance.dre
    with app.app_context():
        FeatureRegistry.set_enabled('finance.dre', True)

    resp_dre_ok = client.get('/finance/dre')
    assert resp_dre_ok.status_code == 200


def test_api_toggle_endpoint(client, app):
    """Testa a API REST de toggle de funcionalidades usada no frontend."""
    # Desativa via JSON POST
    res = client.post(
        '/reports/manage/features/toggle',
        data=json.dumps({'key': 'dashboard.channels_pie'}),
        content_type='application/json'
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['key'] == 'dashboard.channels_pie'
    assert data['enabled'] is False

    # Inverte novamente
    res2 = client.post(
        '/reports/manage/features/toggle',
        data=json.dumps({'key': 'dashboard.channels_pie'}),
        content_type='application/json'
    )
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2['enabled'] is True


def test_template_element_conditional_rendering(client, app):
    """Testa se os widgets e abas somem da UI quando desativados."""
    # 1. No dashboard, desativa o gráfico de evolução
    with app.app_context():
        FeatureRegistry.set_enabled('dashboard.sales_timeline', False)

    resp_dash = client.get('/')
    html_dash = resp_dash.data.decode('utf-8')
    assert "Evolução de Vendas no Período" not in html_dash
    assert "salesTimelineChart" not in html_dash

    # Reativa
    with app.app_context():
        FeatureRegistry.set_enabled('dashboard.sales_timeline', True)

    resp_dash_on = client.get('/')
    html_dash_on = resp_dash_on.data.decode('utf-8')
    assert "Evolução de Vendas no Período" in html_dash_on
    assert "salesTimelineChart" in html_dash_on

    # 2. Na barra de abas de vendas, desativa conditional_bags
    with app.app_context():
        FeatureRegistry.set_enabled('sales.conditional_bags', False)

    resp_sales = client.get('/sales/')
    html_sales = resp_sales.data.decode('utf-8')
    assert "Malas Condicionais" not in html_sales

    # Reativa
    with app.app_context():
        FeatureRegistry.set_enabled('sales.conditional_bags', True)

    resp_sales_on = client.get('/sales/')
    html_sales_on = resp_sales_on.data.decode('utf-8')
    assert "Malas Condicionais" in html_sales_on
