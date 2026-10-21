import time
from datetime import date
from unittest.mock import MagicMock
from app.database import db
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.services.sync_worker import SyncWorker
from app.services.sync_service import SyncService

def test_sync_worker_status_and_lifecycle(app):
    """Testa estado inicial e atualização thread-safe do SyncWorker."""
    status = SyncWorker.get_status()
    assert 'status' in status
    assert 'current_step' in status
    assert 'progress_percent' in status

    SyncWorker.update_progress('stocks', 60, 'Sincronizando saldos...')
    updated = SyncWorker.get_status()
    assert updated['current_step'] == 'stocks'
    assert updated['progress_percent'] == 60
    assert updated['message'] == 'Sincronizando saldos...'


def test_routes_sync_now_and_status(client, app):
    """Testa se os endpoints /sync-now e /sync-status respondem imediatamente com HTTP 200."""
    # 1. Status inicial
    res_status = client.get('/integrations/sync-status')
    assert res_status.status_code == 200
    data_st = res_status.get_json()
    assert 'status' in data_st

    # 2. Inicia sync em background (mockando sync_selected para não bater na API externa)
    orig_sync = SyncService.sync_selected
    SyncService.sync_selected = MagicMock(return_value=(True, {'products': 5, 'stocks': 5}))

    try:
        res_sync = client.post('/integrations/sync-now', json={'products': True, 'orders': False})
        assert res_sync.status_code == 200
        data_sync = res_sync.get_json()
        assert data_sync['success'] is True
        assert data_sync['status'] in ['started', 'busy']

        # Aguarda brevemente a thread concluir
        time.sleep(0.3)
        res_after = client.get('/integrations/sync-status')
        data_after = res_after.get_json()
        assert data_after['status'] in ['running', 'success']
    finally:
        SyncService.sync_selected = orig_sync


def test_sync_orders_incremental_skips_existing_order_details(app):
    """Testa se pedidos com itens já sincronizados NÃO chamam get_order_details desnecessariamente."""
    with app.app_context():
        # Cria pedido existente com 2 itens
        order = Order(
            bling_id=55501,
            number='PED-INCREMENTAL-01',
            order_date=date.today(),
            status='Atendido',
            total=200.0
        )
        db.session.add(order)
        db.session.commit()

        it1 = OrderItem(order=order, product_name='Item 1', quantity=1.0, unit_price=100.0, total_price=100.0)
        it2 = OrderItem(order=order, product_name='Item 2', quantity=1.0, unit_price=100.0, total_price=100.0)
        db.session.add_all([it1, it2])
        db.session.commit()

        # Mock do BlingApiClient
        mock_client = MagicMock()
        mock_client.get_orders.side_effect = [
            [{'id': 55501, 'numero': 'PED-INCREMENTAL-01', 'total': 200.0, 'situacao': {'nome': 'Atendido'}, 'itens': []}],
            [] # fim
        ]

        count = SyncService.sync_orders(client=mock_client)
        assert count == 1
        # Como o pedido já possuía itens, get_order_details NÃO deve ter sido chamado!
        mock_client.get_order_details.assert_not_called()


def test_sync_stocks_paginated_and_multi_deposit(app):
    """Testa se sync_stocks consome o feed paginado de /estoques/saldos e soma depósitos."""
    with app.app_context():
        p1 = Product(bling_id=66601, sku='SKU-DEP-P1', name='Produto Depósito 1', stock=0.0)
        p2 = Product(bling_id=66602, sku='SKU-DEP-P2', name='Produto Depósito 2', stock=0.0)
        db.session.add_all([p1, p2])
        db.session.commit()

        mock_client = MagicMock()
        # Simula resposta paginada com depósitos múltiplos
        mock_client.get_stock_balances.side_effect = [
            [
                {'produto': {'id': 66601}, 'deposito': {'id': 1}, 'saldoFisico': 25.0},
                {'produto': {'id': 66601}, 'deposito': {'id': 2}, 'saldoFisico': 15.0}, # Total P1 = 40.0
                {'produto': {'id': 66602}, 'deposito': {'id': 1}, 'saldoFisico': 10.0}  # Total P2 = 10.0
            ],
            [] # página 2 vazia
        ]

        count = SyncService.sync_stocks(client=mock_client)
        assert count >= 2

        up1 = Product.query.filter_by(bling_id=66601).first()
        up2 = Product.query.filter_by(bling_id=66602).first()
        assert up1.stock == 40.0
        assert up2.stock == 10.0
