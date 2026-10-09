import pytest
from datetime import date, timedelta
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.demo_data import seed_demo_data

def test_multichannel_performance(app):
    with app.app_context():
        seed_demo_data()
        start, end = BiAnalytics.parse_date_filter('last_60_days')
        res = StandardReportsEngine.get_multichannel_performance(start, end)

        assert 'channels' in res
        assert 'summary' in res
        assert 'charts' in res
        assert res['summary']['total_net_sales'] > 0
        assert res['summary']['total_gross_profit'] >= 0
        assert res['summary']['overall_margin_pct'] >= 0
        assert len(res['charts']['sales_by_channel']['labels']) == len(res['channels'])
        assert 'funnel_status' in res['charts']

def test_stock_coverage_and_abc(app):
    with app.app_context():
        seed_demo_data()
        start, end = BiAnalytics.parse_date_filter('last_60_days')
        res = StandardReportsEngine.get_stock_coverage_and_abc(start, end)

        assert 'items' in res
        assert 'summary' in res
        assert 'charts' in res
        assert res['summary']['total_products'] > 0
        assert res['summary']['total_stock_capital'] > 0
        assert 'pareto' in res['charts']
        assert 'coverage_status' in res['charts']

        # Verifica campos dos itens
        if res['items']:
            item0 = res['items'][0]
            assert 'abc_class' in item0
            assert item0['abc_class'] in ['A', 'B', 'C']
            assert 'coverage_days' in item0
            assert 'cov_status' in item0

def test_rfm_matrix(app):
    with app.app_context():
        seed_demo_data()
        res = StandardReportsEngine.get_rfm_matrix()

        assert 'customers' in res
        assert 'summary' in res
        assert 'charts' in res
        assert res['summary']['total_customers'] > 0
        assert res['summary']['avg_ltv'] > 0
        assert 'rfm_clusters' in res['charts']
        assert 'rfm_revenue' in res['charts']

        # Verifica campos do cliente
        if res['customers']:
            c0 = res['customers'][0]
            assert 'r_score' in c0
            assert 'f_score' in c0
            assert 'm_score' in c0
            assert 'cluster' in c0
            assert 'action_tip' in c0

def test_dre_statement_and_cash_flow(app):
    with app.app_context():
        seed_demo_data()
        start, end = BiAnalytics.parse_date_filter('last_30_days')
        dre = StandardReportsEngine.get_dre_statement(start, end)

        assert 'lines' in dre
        assert 'summary' in dre
        assert 'charts' in dre
        assert dre['summary']['gross_sales'] > 0
        assert dre['summary']['cmv'] >= 0
        assert 'waterfall' in dre['charts']

        cf = StandardReportsEngine.get_cash_flow_projection(30)
        assert 'daily_rows' in cf
        assert 'summary' in cf
        assert 'charts' in cf
        assert cf['summary']['total_receivables'] >= 0

def test_standard_reports_routes(client, app):
    with app.app_context():
        seed_demo_data()

    # Hub
    resp = client.get('/reports/')
    assert resp.status_code == 200

    resp = client.get('/reports/hub')
    assert resp.status_code == 200

    # Multicanal
    resp = client.get('/reports/multichannel')
    assert resp.status_code == 200

    # Cobertura de Estoque
    resp = client.get('/reports/stock-coverage')
    assert resp.status_code == 200

    # DRE
    resp = client.get('/reports/dre')
    assert resp.status_code == 200

    # RFM
    resp = client.get('/reports/rfm')
    assert resp.status_code == 200

    # Fluxo de Caixa
    resp = client.get('/reports/cash-flow')
    assert resp.status_code == 200

def test_standard_reports_exports(client, app):
    with app.app_context():
        seed_demo_data()

    # Multicanal Excel & PDF
    resp = client.get('/reports/multichannel/excel')
    assert resp.status_code == 200
    assert 'spreadsheetml' in resp.content_type

    resp = client.get('/reports/multichannel/pdf')
    assert resp.status_code == 200
    assert resp.content_type == 'application/pdf'

    # Cobertura Excel & PDF
    resp = client.get('/reports/stock-coverage/excel')
    assert resp.status_code == 200
    assert 'spreadsheetml' in resp.content_type

    resp = client.get('/reports/stock-coverage/pdf')
    assert resp.status_code == 200
    assert resp.content_type == 'application/pdf'

    # DRE Excel & PDF
    resp = client.get('/reports/dre/excel')
    assert resp.status_code == 200
    assert 'spreadsheetml' in resp.content_type

    resp = client.get('/reports/dre/pdf')
    assert resp.status_code == 200
    assert resp.content_type == 'application/pdf'

    # RFM Excel & PDF
    resp = client.get('/reports/rfm/excel')
    assert resp.status_code == 200
    assert 'spreadsheetml' in resp.content_type

    resp = client.get('/reports/rfm/pdf')
    assert resp.status_code == 200
    assert resp.content_type == 'application/pdf'
