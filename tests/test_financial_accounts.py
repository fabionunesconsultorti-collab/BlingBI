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
