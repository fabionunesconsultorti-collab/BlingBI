import pytest
from datetime import date, timedelta
from app.database import db
from app.models.financial import FinancialEntry
from app.services.accounts_service import AccountsService
from app.services.exporter import BiExporter

def test_accounts_service_crud_and_settlement(app):
    with app.app_context():
        today = date.today()
        # 1. Create a Payable entry
        success, msg, entry = AccountsService.create_entry({
            'entry_type': 'PAGAR',
            'description': 'Fornecedor Teste Peças Automotivas',
            'payee_payer': 'Auto Peças Silva',
            'category': 'Matéria Prima',
            'payment_method': 'Boleto',
            'amount': 1500.0,
            'due_date': today.strftime('%Y-%m-%d'),
            'issue_date': (today - timedelta(days=5)).strftime('%Y-%m-%d'),
            'status': 'Pendente',
            'notes': 'Nota Fiscal 9876'
        })
        assert success is True
        assert entry is not None
        assert entry.id is not None
        assert entry.bling_id is not None
        assert entry.amount == 1500.0
        assert entry.is_overdue is False
        assert entry.days_until_due == 0

        entry_id = entry.id

        # 2. Query data with filters
        data = AccountsService.get_accounts_data({'entry_type': 'PAGAR', 'search': 'Auto Peças Silva'})
        assert len(data['entries']) >= 1
        found = any(e['id'] == entry_id for e in data['entries'])
        assert found is True

        # 3. Settle entry (Baixa direta)
        settle_ok, settle_msg, settled_entry = AccountsService.settle_entry(
            entry_id=entry_id,
            payment_date=today.strftime('%Y-%m-%d'),
            payment_method='PIX',
            notes='Pago via PIX com desconto',
            discount=50.0,
            fine_fee=0.0
        )
        assert settle_ok is True
        assert settled_entry.status == 'Pago'
        assert settled_entry.payment_date == today
        assert settled_entry.payment_method == 'PIX'
        assert settled_entry.discount == 50.0
        assert settled_entry.net_amount == 1450.0

        # 4. Unsettle (Estorno)
        unsettle_ok, unsettle_msg, unsettled_entry = AccountsService.unsettle_entry(entry_id)
        assert unsettle_ok is True
        assert unsettled_entry.status == 'Pendente'
        assert unsettled_entry.payment_date is None

        # 5. Update entry
        upd_ok, upd_msg, upd_entry = AccountsService.update_entry(entry_id, {
            'description': 'Fornecedor Teste Modificado',
            'amount': 1600.0
        })
        assert upd_ok is True
        assert upd_entry.description == 'Fornecedor Teste Modificado'
        assert upd_entry.amount == 1600.0

        # 6. Delete entry
        del_ok, del_msg = AccountsService.delete_entry(entry_id)
        assert del_ok is True
        assert db.session.get(FinancialEntry, entry_id) is None


def test_accounts_summary_metrics_and_alerts(app):
    with app.app_context():
        today = date.today()
        # Seed test items specifically for alerts
        e_today = FinancialEntry(
            entry_type='PAGAR',
            amount=500.0,
            due_date=today,
            status='Pendente',
            description='Conta Hoje Teste',
            payee_payer='Fornecedor Hoje',
            bling_id=990001
        )
        e_overdue = FinancialEntry(
            entry_type='RECEBER',
            amount=1200.0,
            due_date=today - timedelta(days=10),
            status='Pendente',
            description='Recebimento Vencido Teste',
            payee_payer='Cliente Atrasado',
            bling_id=990002
        )
        e_week = FinancialEntry(
            entry_type='RECEBER',
            amount=800.0,
            due_date=today + timedelta(days=3),
            status='Pendente',
            description='Recebimento Semana Teste',
            payee_payer='Cliente Semana',
            bling_id=990003
        )
        db.session.add_all([e_today, e_overdue, e_week])
        db.session.commit()

        summary = AccountsService.get_summary_metrics()
        assert summary['count_today'] >= 1
        assert summary['total_today'] >= 500.0
        assert summary['count_overdue'] >= 1
        assert summary['total_overdue'] >= 1200.0
        assert summary['count_week'] >= 1
        assert summary['total_week'] >= 800.0
        assert summary['total_receber_pending'] >= 2000.0
        assert summary['total_pagar_pending'] >= 500.0
        assert 'saldo_pending' in summary
        assert 'rate_overdue' in summary


def test_accounts_calendar_events(app):
    with app.app_context():
        today = date.today()
        cal_data = AccountsService.get_calendar_events(year=today.year, month=today.month)
        assert cal_data['year'] == today.year
        assert cal_data['month'] == today.month
        assert len(cal_data['weeks']) >= 4
        # Every week has exactly 7 days (Sunday to Saturday)
        for w in cal_data['weeks']:
            assert len(w) == 7
        assert 'month_totals' in cal_data
        assert 'receber' in cal_data['month_totals']
        assert 'pagar' in cal_data['month_totals']


def test_accounts_exporter_excel_and_pdf(app):
    with app.app_context():
        filters = {'entry_type': 'TODOS', 'status': 'TODOS'}
        data = AccountsService.get_accounts_data(filters, page=1, per_page=50)
        summary = AccountsService.get_summary_metrics(filters)

        # Test Excel export
        excel_stream = BiExporter.export_accounts_to_excel(data['entries'], summary, filters)
        assert excel_stream is not None
        assert excel_stream.getvalue().startswith(b'PK')  # OpenPyXL zip archive

        # Test PDF export
        pdf_stream = BiExporter.export_accounts_to_pdf(data['entries'], summary, filters)
        assert pdf_stream is not None
        assert pdf_stream.getvalue().startswith(b'%PDF')


def test_accounts_routes(client):
    # 1. Main View (200 OK)
    resp = client.get('/finance/accounts')
    assert resp.status_code == 200
    assert b"Contas a Pagar & Receber" in resp.data
    assert b"Lista de T" in resp.data

    # 2. Main View with Calendar View
    resp_cal = client.get('/finance/accounts?view=calendar')
    assert resp_cal.status_code == 200
    assert b"Calend" in resp_cal.data

    # 3. Create entry via Route POST (JSON)
    create_payload = {
        'entry_type': 'RECEBER',
        'description': 'Venda Direta BI Teste',
        'payee_payer': 'Cliente Especial',
        'category': 'Vendas',
        'amount': 750.0,
        'due_date': date.today().strftime('%Y-%m-%d'),
        'payment_method': 'PIX'
    }
    resp_create = client.post('/finance/accounts/create', json=create_payload)
    assert resp_create.status_code == 200
    json_data = resp_create.get_json()
    assert json_data['success'] is True
    entry_id = json_data['entry']['id']

    # 4. Settle entry via Route POST (JSON)
    settle_payload = {
        'payment_date': date.today().strftime('%Y-%m-%d'),
        'payment_method': 'PIX',
        'discount': 10.0,
        'fine_fee': 0.0,
        'notes': 'Baixa confirmada via rota'
    }
    resp_settle = client.post(f'/finance/accounts/settle/{entry_id}', json=settle_payload)
    assert resp_settle.status_code == 200
    assert resp_settle.get_json()['success'] is True

    # 5. Unsettle entry via Route POST (JSON)
    resp_unsettle = client.post(f'/finance/accounts/unsettle/{entry_id}', json={})
    assert resp_unsettle.status_code == 200
    assert resp_unsettle.get_json()['success'] is True

    # 6. Export Excel Endpoint
    resp_excel = client.get('/finance/accounts/export/excel')
    assert resp_excel.status_code == 200
    assert resp_excel.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # 7. Export PDF Endpoint
    resp_pdf = client.get('/finance/accounts/export/pdf')
    assert resp_pdf.status_code == 200
    assert resp_pdf.mimetype == "application/pdf"

    # 8. Delete entry via Route POST
    resp_del = client.post(f'/finance/accounts/delete/{entry_id}', json={})
    assert resp_del.status_code == 200
    assert resp_del.get_json()['success'] is True

    # 9. Test Auxiliary Options Route (JSON)
    resp_aux = client.get('/finance/accounts/auxiliary-options')
    assert resp_aux.status_code == 200
    aux_data = resp_aux.get_json()
    assert 'payment_methods' in aux_data
    assert 'categories' in aux_data


def test_accounts_bling_mirroring_success(app, monkeypatch):
    """Testa espelhamento bem-sucedido de baixa para o Bling ERP via API v3."""
    with app.app_context():
        from app.services.bling_api import BlingApiClient
        monkeypatch.setattr(BlingApiClient, 'is_configured', lambda self: True)
        
        called_payload = {}
        def mock_settle_payable(self, bling_id, payload):
            called_payload.update(payload)
            return True, "Baixa registrada no Bling com sucesso!", {'id': bling_id}

        monkeypatch.setattr(BlingApiClient, 'settle_payable', mock_settle_payable)

        # Cria entrada com bling_id real do ERP (< 9000000000)
        entry = FinancialEntry(
            bling_id=884422,
            entry_type='PAGAR',
            description='Duplicata Fornecedor Bling Teste',
            amount=2500.0,
            due_date=date.today(),
            status='Pendente'
        )
        db.session.add(entry)
        db.session.commit()

        res = AccountsService.settle_entry(
            entry_id=entry.id,
            payment_date=date.today().strftime('%Y-%m-%d'),
            payment_method='PIX',
            bling_payment_method_id=9876,
            notes='Comprovante ABC-123'
        )

        assert res.get('success') is True
        assert 'espelhado no Bling ERP com sucesso' in res.get('message')
        assert entry.status == 'Pago'
        assert entry.sync_status == 'synced'
        assert entry.last_sync_at is not None
        assert entry.sync_error_msg is None
        assert called_payload.get('valor') == 2500.0
        assert called_payload.get('idFormaPagamento') == 9876


def test_accounts_bling_mirroring_graceful_error(app, monkeypatch):
    """Testa tratamento gracioso quando a API do Bling rejeita ou falha no espelhamento."""
    with app.app_context():
        from app.services.bling_api import BlingApiClient
        monkeypatch.setattr(BlingApiClient, 'is_configured', lambda self: True)
        
        def mock_settle_receivable(self, bling_id, payload):
            return False, "Bling API: HTTP 422 - data de pagamento posterior ao limite", {}

        monkeypatch.setattr(BlingApiClient, 'settle_receivable', mock_settle_receivable)

        entry = FinancialEntry(
            bling_id=773311,
            entry_type='RECEBER',
            description='Mensalidade Cliente Bling Teste',
            amount=450.0,
            due_date=date.today(),
            status='Pendente'
        )
        db.session.add(entry)
        db.session.commit()

        res = AccountsService.settle_entry(
            entry_id=entry.id,
            payment_date=date.today().strftime('%Y-%m-%d'),
            notes='Tentativa de baixa com erro simulado'
        )

        assert res.get('success') is True  # No BI a operação não trava
        assert entry.status == 'Pago'
        assert entry.sync_status == 'sync_error'
        assert '422' in entry.sync_error_msg
        assert 'Aviso Bling' in res.get('message')


def test_accounts_sync_single_entry_retry(app, monkeypatch):
    """Testa retentativa de sincronização de um título pendente ou com erro."""
    with app.app_context():
        from app.services.bling_api import BlingApiClient
        monkeypatch.setattr(BlingApiClient, 'is_configured', lambda self: True)

        def mock_create_payable(self, payload):
            return True, "OK", {'id': 55667788}

        monkeypatch.setattr(BlingApiClient, 'create_payable', mock_create_payable)

        # Lançamento local com ID sintético (>= 9000000000)
        entry = FinancialEntry(
            bling_id=9991234567,
            entry_type='PAGAR',
            description='Lançamento Local Pendente de Envio',
            amount=320.0,
            due_date=date.today(),
            status='Pendente',
            sync_status='pending_sync'
        )
        db.session.add(entry)
        db.session.commit()

        # Força sincronização
        res = AccountsService.sync_single_entry(entry.id)
        assert res.get('success') is True
        assert entry.bling_id == 55667788
        assert entry.sync_status == 'synced'
        assert entry.last_sync_at is not None


def test_bling_api_diagnostic_error_messages_and_429():
    """Valida mensagens de erro humanizadas e tratamento de 429/timeout no BlingApiClient."""
    from app.services.bling_api import BlingApiClient
    import requests

    # 1. Sem resposta (None)
    err_none = BlingApiClient._extract_error_message(None)
    assert "Sem resposta do servidor Bling" in err_none
    assert "tempo limite" in err_none

    # 2. Rate limit (429)
    resp_429 = requests.Response()
    resp_429.status_code = 429
    err_429 = BlingApiClient._extract_error_message(resp_429)
    assert "HTTP 429" in err_429
    assert "3 chamadas/segundo" in err_429

    # 3. Auth expirada (401)
    resp_401 = requests.Response()
    resp_401.status_code = 401
    err_401 = BlingApiClient._extract_error_message(resp_401)
    assert "HTTP 401" in err_401
    assert "Reconecte sua conta" in err_401

    # 4. Permissão (403)
    resp_403 = requests.Response()
    resp_403.status_code = 403
    err_403 = BlingApiClient._extract_error_message(resp_403)
    assert "HTTP 403" in err_403
    assert "Finanças" in err_403


def test_bling_api_request_429_returns_response_not_none(monkeypatch):
    """Garante que requisições atingindo rate limit 429 após todas as tentativas retornam a resposta (não None)."""
    from app.services.bling_api import BlingApiClient
    import requests

    client = BlingApiClient()
    monkeypatch.setattr(client, '_get_headers', lambda: {'Authorization': 'Bearer test'})

    attempts_count = 0
    def mock_request(*args, **kwargs):
        nonlocal attempts_count
        attempts_count += 1
        resp = requests.Response()
        resp.status_code = 429
        return resp

    import time
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    monkeypatch.setattr(requests, 'request', mock_request)

    res = client.request('GET', '/contas/pagar', retries=2)
    assert res is not None
    assert res.status_code == 429
    assert attempts_count == 3  # 0, 1, 2 = 3 tentativas


def test_accounts_competence_date_payload_and_sync(app, monkeypatch):
    """Garante que competencia (YYYY-MM-DD) é sempre enviada na API Bling e lida na sincronização."""
    with app.app_context():
        from app.services.bling_api import BlingApiClient
        from app.services.sync_service import SyncService
        monkeypatch.setattr(BlingApiClient, 'is_configured', lambda self: True)
        monkeypatch.setattr(BlingApiClient, 'get_contacts', lambda self, **kw: [{'id': 112233, 'nome': 'Enel Energia'}])

        captured_create_payload = {}
        def mock_create_payable(self, payload):
            nonlocal captured_create_payload
            captured_create_payload = payload
            return True, "OK", {'id': 991122}

        monkeypatch.setattr(BlingApiClient, 'create_payable', mock_create_payable)

        # 1. Criação avulsa enviando competencia_date
        res = AccountsService.create_entry({
            'entry_type': 'PAGAR',
            'description': 'Conta Luz Escritório',
            'amount': 280.0,
            'due_date': '2026-11-10',
            'issue_date': '2026-10-20',
            'competence_date': '2026-10-01',
            'payee_payer': 'Enel Energia'
        })
        assert res.get('success') is True
        assert captured_create_payload.get('competencia') == '2026-10-01'
        assert captured_create_payload.get('vencimento') == '2026-11-10'
        assert captured_create_payload.get('dataEmissao') == '2026-10-20'

        entry = res.get('entry')
        assert entry.competence_date == date(2026, 10, 1)

        # 2. Atualização enviando nova competência
        captured_update_payload = {}
        def mock_update_payable(self, bling_id, payload):
            nonlocal captured_update_payload
            captured_update_payload = payload
            return True, "OK", {'id': bling_id}

        monkeypatch.setattr(BlingApiClient, 'update_payable', mock_update_payable)

        res_upd = AccountsService.update_entry(entry.id, {
            'competence_date': '2026-10-15'
        })
        assert res_upd.get('success') is True
        assert captured_update_payload.get('competencia') == '2026-10-15'
        assert entry.competence_date == date(2026, 10, 15)

        # 3. Sincronização vinda do Bling popula competence_date
        mock_raw_item = [{
            'id': 884422,
            'historico': 'Serviço de Nuvem',
            'valor': 199.90,
            'vencimento': '2026-11-05',
            'dataEmissao': '2026-10-05',
            'competencia': '2026-10-01',
            'situacao': 1
        }]
        monkeypatch.setattr(BlingApiClient, 'get_payables', lambda self, **kw: mock_raw_item)

        count = SyncService.sync_payables(BlingApiClient())
        assert count == 1
        synced_e = FinancialEntry.query.filter_by(bling_id=884422).first()
        assert synced_e is not None
        assert synced_e.competence_date == date(2026, 10, 1)


