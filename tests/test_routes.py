def test_dashboard_route(client):
    res = client.get('/')
    assert res.status_code == 200
    assert b'BlingBI' in res.data
    assert b'Dashboard 360' in res.data

def test_sales_route(client):
    res = client.get('/sales/')
    assert res.status_code == 200
    assert any(term in res.data for term in [b'Vendas e Pedidos', b'Vendas &amp; Pedidos', b'Vendas & Pedidos'])

def test_products_route(client):
    res = client.get('/products/')
    assert res.status_code == 200
    assert b'Curva ABC' in res.data

def test_customers_route(client):
    res = client.get('/customers/')
    assert res.status_code == 200
    assert any(term in res.data for term in [b'Clientes e CRM', b'Clientes &amp; CRM', b'Clientes & CRM'])

    # Test all tabs in Customer & CRM Sector
    for endpoint in ['/customers/rfm', '/customers/abc', '/customers/profiles', '/customers/birthdays', '/customers/nps']:
        sub_res = client.get(endpoint)
        assert sub_res.status_code == 200, f"Failed rendering customer endpoint {endpoint}"


def test_finance_route(client):
    res = client.get('/finance/')
    assert res.status_code == 200
    assert b'DRE' in res.data

    # Test all tabs in Finance & DRE Sector
    for endpoint in ['/finance/dre', '/finance/cash-flow', '/finance/aging', '/finance/cash-statement']:
        sub_res = client.get(endpoint)
        assert sub_res.status_code == 200, f"Failed rendering finance endpoint {endpoint}"

def test_integrations_route(client):
    res = client.get('/integrations/')
    assert res.status_code == 200
    assert b'Bling ERP' in res.data

def test_oauth_authorize_without_client_id(client):
    res = client.get('/integrations/authorize', follow_redirects=True)
    assert res.status_code == 200
    assert b'Client ID' in res.data

def test_oauth_callback_without_code(client):
    res = client.get('/integrations/callback', follow_redirects=True)
    assert res.status_code == 200
    assert b'C\xc3\xb3digo de autoriza\xc3\xa7\xc3\xa3o' in res.data or b'autoriza' in res.data

def test_sales_excel_download(client):
    res = client.get('/reports/sales/excel?period=last_30_days')
    assert res.status_code == 200
    assert 'spreadsheetml' in res.headers.get('Content-Type', '')

def test_sales_pdf_download(client):
    res = client.get('/reports/sales/pdf?period=last_30_days')
    assert res.status_code == 200
    assert 'pdf' in res.headers.get('Content-Type', '')

def test_webhook_listener_endpoint(client):
    res = client.post('/integrations/webhook', json={'tipo': 'pedido.alterado', 'id': 12345})
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data['status'] == 'received'

def test_tunnel_endpoints(client, monkeypatch):
    from app.services.tunnel_service import TunnelService

    # Test status endpoint
    res = client.get('/integrations/tunnel/status')
    assert res.status_code == 200
    data = res.get_json()
    assert 'active' in data

    # Test mock start endpoint
    monkeypatch.setattr(TunnelService, 'start_tunnel', lambda port=5000: (True, 'https://test-tunnel.loca.lt/integrations/webhook'))
    res = client.post('/integrations/tunnel/start')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'test-tunnel.loca.lt' in data['url']

    # Test stop endpoint
    monkeypatch.setattr(TunnelService, 'stop_tunnel', lambda: True)
    res = client.post('/integrations/tunnel/stop')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True

def test_fashion_routes(client):
    res = client.get('/fashion/')
    assert res.status_code == 200
    assert any(term in res.data for term in [b'Moda', b'Fashion', b'Varejo'])

    for tab in ['block1', 'block2', 'block3', 'block4']:
        sub_res = client.get(f'/fashion/?tab={tab}')
        assert sub_res.status_code == 200, f"Failed rendering fashion tab {tab}"

