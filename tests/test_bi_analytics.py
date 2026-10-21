from datetime import date, timedelta
from app.services.bi_analytics import BiAnalytics

def test_date_filter_parsing():
    start, end = BiAnalytics.parse_date_filter('today')
    assert start == date.today()
    assert end == date.today()

    start, end = BiAnalytics.parse_date_filter('last_7_days')
    assert end == date.today()
    assert start == date.today() - timedelta(days=7)

def test_dashboard_metrics(app):
    start, end = BiAnalytics.parse_date_filter('last_30_days')
    metrics = BiAnalytics.get_dashboard_metrics(start, end)

    assert 'total_revenue' in metrics
    assert metrics['total_revenue'] > 0
    assert metrics['orders_count'] > 0
    assert metrics['ticket_medio'] > 0
    assert len(metrics['chart_labels']) > 0
    assert len(metrics['top_products']) > 0

def test_products_abc_curve(app):
    start, end = BiAnalytics.parse_date_filter('last_30_days')
    analytics = BiAnalytics.get_products_analytics(start, end)

    assert analytics['total_products'] > 0
    assert len(analytics['abc_products']) > 0
    
    # Verifica se existem produtos nas classes A, B ou C
    classes = {p['class'] for p in analytics['abc_products']}
    assert 'A' in classes or 'B' in classes or 'C' in classes

    # Validação do saldo de estoque (não pode estar todo zerado)
    assert 'in_stock_count' in analytics
    assert 'zero_stock_count' in analytics
    stocks = [p['stock'] for p in analytics['abc_products']]
    assert any(s > 0 for s in stocks), "Pelo menos um produto na Curva ABC deve ter saldo de estoque positivo"

def test_financial_analytics_and_dre(app):
    start, end = BiAnalytics.parse_date_filter('last_30_days')
    analytics = BiAnalytics.get_finance_analytics(start, end)

    assert analytics['total_receivable'] >= 0
    assert analytics['total_payable'] >= 0
    assert 'dre' in analytics
    assert analytics['dre']['gross_revenue'] >= 0
    assert 'net_profit' in analytics['dre']
