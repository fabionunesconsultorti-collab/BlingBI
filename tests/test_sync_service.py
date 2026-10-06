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
