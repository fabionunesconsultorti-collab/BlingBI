import pytest
from unittest.mock import MagicMock
from app.database import db
from app.models.order import Order, OrderItem
from app.services.sync_service import SyncService

def test_sync_orders_updates_existing_order_with_items(app):
    with app.app_context():
        # Get an existing order (from seed_demo_data)
        existing_order = Order.query.first()
        assert existing_order is not None
        assert len(existing_order.items) > 0
        bling_id = existing_order.bling_id

        # Mock client to return this order with new items
        mock_client = MagicMock()
        mock_client.get_orders.side_effect = [
            [
                {
                    'id': bling_id,
                    'numero': '99999',
                    'data': '2026-10-06',
                    'total': 250.00,
                    'situacao': {'nome': 'Atendido'},
                    'loja': {'nome': 'Loja Teste'},
                    'itens': [
                        {
                            'descricao': 'Item Novo 1',
                            'codigo': 'SKU-NEW-1',
                            'quantidade': 2.0,
                            'valor': 100.0,
                            'produto': {'id': 99999}
                        },
                        {
                            'descricao': 'Item Novo 2',
                            'codigo': 'SKU-NEW-2',
                            'quantidade': 1.0,
                            'valor': 50.0,
                            'produto': {'id': None}
                        }
                    ]
                }
            ],
            [] # Page 2 returns empty to break
        ]

        # Execute sync_orders
        count = SyncService.sync_orders(client=mock_client)
        assert count == 1

        # Check order updated cleanly
        updated_order = Order.query.filter_by(bling_id=bling_id).first()
        assert updated_order.number == '99999'
        assert updated_order.total == 250.00
        assert len(updated_order.items) == 2
        skus = [it.sku for it in updated_order.items]
        assert 'SKU-NEW-1' in skus
        assert 'SKU-NEW-2' in skus

def test_clear_demo_data(app):
    from app.services.demo_data import clear_demo_data, seed_demo_data
    from app.models.product import Product
    from app.models.customer import Customer
    from app.models.financial import FinancialEntry
    from app.models.setting import Setting

    with app.app_context():
        # Ensure we have records
        assert Order.query.count() > 0
        assert Product.query.count() > 0
        assert Customer.query.count() > 0
        assert FinancialEntry.query.count() > 0

        # Set a dummy bling credential to ensure it is NOT wiped
        Setting.set('bling_client_id', 'test_client_id_123')
        Setting.set('bling_access_token', 'test_access_token_456')

        # Clear demo data
        result = clear_demo_data()
        assert result is True

        # Assert records were wiped
        assert Order.query.count() == 0
        assert OrderItem.query.count() == 0
        assert Product.query.count() == 0
        assert Customer.query.count() == 0
        assert FinancialEntry.query.count() == 0

        # Assert settings and credentials were preserved
        assert Setting.get('bling_client_id') == 'test_client_id_123'
        assert Setting.get('bling_access_token') == 'test_access_token_456'
        assert Setting.get('demo_mode_active') == '0'
        assert Setting.get('demo_cleared') == '1'

def test_clear_demo_route(client, app):
    from app.models.setting import Setting

    with app.app_context():
        Setting.set('bling_client_id', 'preserve_me')
        assert Order.query.count() > 0

    # 1. Test without password -> 403
    res_no_pw = client.post('/integrations/clear-demo', json={})
    assert res_no_pw.status_code == 403
    assert 'incorreta' in res_no_pw.get_json()['message']

    # 2. Test with wrong password -> 403
    res_wrong_pw = client.post('/integrations/clear-demo', json={'password': 'wrongpassword'})
    assert res_wrong_pw.status_code == 403
    assert 'incorreta' in res_wrong_pw.get_json()['message']

    with app.app_context():
        # Ensure database was NOT cleared
        assert Order.query.count() > 0

    # 3. Test with correct password c4nib4l -> 200
    res_ok = client.post('/integrations/clear-demo', json={'password': 'c4nib4l'})
    assert res_ok.status_code == 200
    data = res_ok.get_json()
    assert data['success'] is True

    with app.app_context():
        assert Order.query.count() == 0
        assert Setting.get('bling_client_id') == 'preserve_me'
        assert Setting.get('demo_cleared') == '1'


def test_bling_api_products_and_stock_balances(app):
    from app.services.bling_api import BlingApiClient

    client = BlingApiClient()
    def fake_request(method, endpoint, params=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if endpoint == '/produtos':
            mock_resp.json.return_value = {
                'data': [{'id': 12345, 'nome': 'Camiseta Básica', 'codigo': 'TSHIRT-01', 'preco': 49.90}]
            }
        elif endpoint == '/estoques/saldos':
            mock_resp.json.return_value = {
                'data': [
                    {'produto': {'id': 12345}, 'deposito': {'id': 1, 'nome': 'Geral'}, 'saldoFisico': 30, 'saldoVirtual': 25},
                    {'produto': {'id': 12345}, 'deposito': {'id': 2, 'nome': 'Loja'}, 'saldoFisico': 20, 'saldoVirtual': 20}
                ]
            }
        return mock_resp

    client.request = MagicMock(side_effect=fake_request)

    # 1. get_products com filtros
    prods = client.get_products(page=1, limit=10, code='TSHIRT-01', product_type='P')
    assert len(prods) == 1
    client.request.assert_called_with('GET', '/produtos', params={'pagina': 1, 'limite': 10, 'codigo': 'TSHIRT-01', 'tipo': 'P'})

    # 2. get_stock_balances com array idsProdutos[]
    balances = client.get_stock_balances(product_ids=[12345, 67890])
    assert len(balances) == 2
    client.request.assert_called_with('GET', '/estoques/saldos', params={'idsProdutos[]': [12345, 67890]})

    # 3. get_product_with_stock consolidado
    prod_stock = client.get_product_with_stock(sku='TSHIRT-01')
    assert prod_stock is not None
    assert prod_stock['id'] == 12345
    assert prod_stock['saldo_fisico'] == 50.0 # 30 + 20 somando depósitos
    assert prod_stock['saldo_disponivel'] == 45.0 # 25 + 20


def test_sync_stocks_aggregates_multiple_deposits(app):
    from app.models.product import Product

    with app.app_context():
        # Cria produto de teste com estoque inicial 0
        p = Product(
            bling_id=77701,
            sku='TEST-DEP-01',
            name='Vestido Teste Depósitos Múltiplos',
            stock=0.0
        )
        db.session.add(p)
        db.session.commit()

        # Mock client que retorna múltiplos depósitos para o produto 77701
        mock_client = MagicMock()
        mock_client.get_stock_balances.return_value = [
            {'produto': {'id': 77701}, 'deposito': {'id': 101, 'nome': 'CD Principal'}, 'saldoFisico': 35.0, 'saldoVirtual': 30.0},
            {'produto': {'id': 77701}, 'deposito': {'id': 102, 'nome': 'Loja Shopping'}, 'saldoFisico': 15.0, 'saldoVirtual': 15.0}
        ]

        count = SyncService.sync_stocks(client=mock_client)
        assert count > 0

        # Verifica se o estoque foi consolidado somando todos os depósitos (35 + 15 = 50)
        updated_p = Product.query.filter_by(bling_id=77701).first()
        assert updated_p.stock == 50.0

