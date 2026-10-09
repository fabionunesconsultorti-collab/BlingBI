import pytest
import io
import json
import zipfile
from datetime import date
from app.reports.registry import report_registry
from app.reports.package_manager import ReportPackageManager
from app.services.bi_data_library import BiDataLibrary

def test_bi_data_library_queries(app):
    """Testa métodos analíticos da BiDataLibrary."""
    with app.app_context():
        start_date = date(2020, 1, 1)
        end_date = date(2030, 12, 31)

        df_orders = BiDataLibrary.get_orders_df(start_date, end_date)
        assert not df_orders.is_empty()
        assert 'order_number' in df_orders.columns
        assert 'total' in df_orders.columns

        df_items = BiDataLibrary.get_order_items_df(start_date, end_date)
        assert not df_items.is_empty()
        assert 'unit_price' in df_items.columns
        assert 'total_cost' in df_items.columns

        df_products = BiDataLibrary.get_products_df()
        assert not df_products.is_empty()
        assert 'stock_quantity' in df_products.columns

        df_customers = BiDataLibrary.get_customers_df()
        assert not df_customers.is_empty()
        assert 'total_spent' in df_customers.columns

        df_finance = BiDataLibrary.get_financial_entries_df()
        assert not df_finance.is_empty()
        assert 'amount' in df_finance.columns

        kpis = BiDataLibrary.get_summary_kpis(start_date, end_date)
        assert kpis['total_revenue'] > 0
        assert kpis['orders_count'] > 0

def test_report_registry_discovery(app):
    """Valida auto-descoberta dos 6 módulos encapsulados."""
    with app.app_context():
        report_registry.discover_and_register_modules()
        modules = report_registry.get_all()
        module_ids = [m.id for m in modules]

        assert len(modules) >= 6
        assert 'multichannel' in module_ids
        assert 'stock_coverage' in module_ids
        assert 'rfm' in module_ids
        assert 'dre' in module_ids
        assert 'cash_flow' in module_ids
        assert 'fashion_bi' in module_ids

        # Valida metadados
        multi = report_registry.get('multichannel')
        assert multi is not None
        assert multi.name == "Performance Multicanal & Margem"
        assert multi.category == "comercial"
        assert "excel" in multi.metadata.export_formats
        assert "pdf" in multi.metadata.export_formats

def test_reports_hub_view(client):
    """Valida carregamento do Catálogo Dinâmico de Relatórios (/reports/hub)."""
    resp = client.get('/reports/hub')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Catálogo de Relatórios &amp; Inteligência Estratégica" in html or "Catálogo de Relatórios" in html
    assert "Performance Multicanal" in html
    assert "Cobertura de Estoque" in html
    assert "Segmentação RFM de Clientes" in html

def test_dynamic_report_view_and_toggle(client):
    """Testa visualização dinâmica e toggle de ativação."""
    # 1. Acesso ao relatório ativo
    resp = client.get('/reports/view/multichannel')
    assert resp.status_code == 200

    # 2. Toggle para desativar
    toggle_resp = client.post('/reports/manage/toggle/multichannel')
    assert toggle_resp.status_code == 200
    data = toggle_resp.get_json()
    assert data['success'] is True
    assert data['enabled'] is False

    # 3. Acesso bloqueado gracioso quando desativado
    resp_disabled = client.get('/reports/view/multichannel', follow_redirects=True)
    assert resp_disabled.status_code == 200
    html = resp_disabled.data.decode('utf-8')
    assert "desativado" in html

    # 4. Reativa
    toggle_resp2 = client.post('/reports/manage/toggle/multichannel')
    assert toggle_resp2.get_json()['enabled'] is True

def test_package_export_and_import(app):
    """Valida empacotamento em ZIP e importação de relatório."""
    with app.app_context():
        # 1. Exporta pacote ZIP do multichannel
        zip_buf, filename = ReportPackageManager.export_package('multichannel')
        assert zip_buf is not None
        assert filename.endswith('.zip')

        # Verifica integridade do zip
        with zipfile.ZipFile(zip_buf, 'r') as zf:
            names = zf.namelist()
            assert 'manifest.json' in names
            assert 'engine.py' in names

        # 2. Testa importação via stream
        zip_buf.seek(0)
        success, msg = ReportPackageManager.import_package(zip_buf)
        assert success is True
        assert "sucesso" in msg.lower()
