import pytest
from datetime import date, timedelta
from app.services.bi_analytics import BiAnalytics
from app.services.fashion_bi import FashionBiEngine
from app.services.demo_fashion_data import seed_fashion_demo_data

def test_fashion_demo_seed_and_models(app):
    with app.app_context():
        seed_fashion_demo_data()
        from app.models.fashion import ConditionalBag, ProductReturn, SellerAttendance, CustomerSurvey
        assert ConditionalBag.query.count() > 0
        assert ProductReturn.query.count() > 0
        assert SellerAttendance.query.count() > 0
        assert CustomerSurvey.query.count() > 0

def test_filter_options_retrieval(app):
    with app.app_context():
        seed_fashion_demo_data()
        options = FashionBiEngine.get_filter_options()
        assert 'sellers' in options
        assert len(options['sellers']) > 0
        assert 'categories' in options
        assert len(options['categories']) > 0
        assert 'reasons' in options
        assert len(options['reasons']) > 0
        assert 'months' in options
        assert len(options['months']) == 12

def test_block1_customer_profile_and_abc_curve(app):
    with app.app_context():
        seed_fashion_demo_data()
        start, end = BiAnalytics.parse_date_filter('last_60_days')

        # 1. Perfil com moda estatística e gráficos
        prof_res = FashionBiEngine.get_customer_purchase_profiles(start, end)
        assert 'profiles' in prof_res
        assert 'charts' in prof_res
        assert len(prof_res['profiles']) > 0
        p0 = prof_res['profiles'][0]
        assert 'preferred_size' in p0
        assert 'preferred_color' in p0
        assert 'preferred_style' in p0
        assert p0['total_spent'] > 0
        assert 'sizes' in prof_res['charts']

        # 2. Curva ABC de clientes com gráfico
        abc = FashionBiEngine.get_customer_abc_curve(start, end)
        assert 'customers' in abc
        assert 'summary' in abc
        assert 'chart' in abc
        assert abc['summary']['total_revenue'] > 0
        assert abc['summary']['class_a_count'] >= 0
        assert len(abc['chart']['labels']) == 3

        # Teste com filtro por classe
        abc_filtered = FashionBiEngine.get_customer_abc_curve(start, end, abc_class='A')
        for c in abc_filtered['customers']:
            assert c['abc_class'] == 'A'

        # 3. Aniversariantes do mês com gráfico
        bdays_res = FashionBiEngine.get_birthday_customers(target_month=10)
        assert 'customers' in bdays_res
        assert 'chart' in bdays_res
        assert len(bdays_res['chart']['labels']) == 5

def test_block2_conditional_bags_and_returns(app):
    with app.app_context():
        seed_fashion_demo_data()
        start, end = BiAnalytics.parse_date_filter('last_60_days')

        # 1. Malas Condicionais com gráfico
        bags = FashionBiEngine.get_conditional_bags_analytics(start, end)
        assert bags['total_bags'] > 0
        assert bags['total_sent'] > 0
        assert bags['overall_conversion_rate'] >= 0
        assert len(bags['sellers_conversion']) > 0
        assert 'chart' in bags
        assert len(bags['chart']['labels']) > 0

        # 2. Ranking de produtos por categoria com gráfico
        top_cat = FashionBiEngine.get_top_products_by_category(start, end)
        assert 'products' in top_cat
        assert 'chart' in top_cat
        if top_cat['products']:
            assert 'rank_in_category' in top_cat['products'][0]
            assert top_cat['products'][0]['rank_in_category'] <= 5

        # 3. Trocas e devoluções com gráfico
        returns = FashionBiEngine.get_returns_and_exchanges_report(start, end)
        assert returns['total_returns'] > 0
        assert len(returns['reasons_distribution']) > 0
        assert 'chart' in returns
        assert len(returns['chart']['labels']) > 0

def test_block3_service_performance_kpis(app):
    with app.app_context():
        seed_fashion_demo_data()
        start, end = BiAnalytics.parse_date_filter('last_60_days')

        kpis = FashionBiEngine.get_service_performance_kpis(start, end)
        assert kpis['store_pa'] > 0
        assert kpis['store_ticket'] > 0
        assert len(kpis['sellers_kpis']) > 0
        seller = kpis['sellers_kpis'][0]
        assert 'pa' in seller
        assert 'conversion_rate' in seller
        assert 'charts' in kpis
        assert 'pa' in kpis['charts']
        assert 'conversion' in kpis['charts']

def test_block4_crm_inactives_and_satisfaction(app):
    with app.app_context():
        seed_fashion_demo_data()
        start, end = BiAnalytics.parse_date_filter('last_60_days')

        # 1. Inativos e Recência com gráficos
        inactives = FashionBiEngine.get_inactive_customers_report()
        assert inactives['total_analyzed'] > 0
        assert len(inactives['customers']) > 0
        c0 = inactives['customers'][0]
        assert 'days_inactive' in c0
        assert 'tier' in c0
        assert 'chart' in inactives
        assert len(inactives['chart']['labels']) == 4

        # 2. Cohort de Recompra com gráfico
        cohort = FashionBiEngine.get_repurchase_cohort()
        assert 'matrix' in cohort
        assert 'chart' in cohort

        # 3. NPS e CSAT com gráfico
        satisfaction = FashionBiEngine.get_satisfaction_metrics(start, end)
        assert satisfaction['total_responses'] > 0
        assert -100 <= satisfaction['nps_score'] <= 100
        assert 1.0 <= satisfaction['csat_score'] <= 5.0
        assert 'chart' in satisfaction
        assert len(satisfaction['chart']['data']) == 3

def test_fashion_routes_and_exports(client):
    # 1. Rota principal
    res = client.get('/fashion/')
    assert res.status_code == 200
    assert b"BI Varejo de Moda" in res.data
    assert b"Perfil & Comportamento" in res.data
    assert b"chartAbcRevenue" in res.data

    # 2. Navegação por abas com filtros
    for tab in ['block1', 'block2', 'block3', 'block4']:
        res_tab = client.get(f'/fashion/?tab={tab}&seller=all&period=last_30_days')
        assert res_tab.status_code == 200

    # 3. Exportações Excel (.xlsx)
    res_abc = client.get('/fashion/export/abc')
    assert res_abc.status_code == 200
    assert res_abc.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    res_inact = client.get('/fashion/export/inactives')
    assert res_inact.status_code == 200
    assert res_inact.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    res_bags = client.get('/fashion/export/bags')
    assert res_bags.status_code == 200
    assert res_bags.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    # 4. Exportações PDF (.pdf)
    res_abc_pdf = client.get('/fashion/export/abc/pdf')
    assert res_abc_pdf.status_code == 200
    assert res_abc_pdf.headers['Content-Type'] == 'application/pdf'

    res_bags_pdf = client.get('/fashion/export/bags/pdf')
    assert res_bags_pdf.status_code == 200
    assert res_bags_pdf.headers['Content-Type'] == 'application/pdf'

    res_kpis_pdf = client.get('/fashion/export/kpis/pdf')
    assert res_kpis_pdf.status_code == 200
    assert res_kpis_pdf.headers['Content-Type'] == 'application/pdf'

    res_inact_pdf = client.get('/fashion/export/inactives/pdf')
    assert res_inact_pdf.status_code == 200
    assert res_inact_pdf.headers['Content-Type'] == 'application/pdf'


def test_consign_orders_and_subsequent_pieces_matching(app):
    """
    Valida a regra de negócio do varejo de moda:
    Pedidos com payment_method 'Consignado' e cruzamento com pedidos do mesmo cliente
    que contenham as peças retiradas na mala.
    """
    with app.app_context():
        from app.database import db
        from app.models.customer import Customer
        from app.models.product import Product
        from app.models.order import Order, OrderItem
        from app.services.fashion_bi import FashionBiEngine
        from datetime import date, timedelta

        cust = Customer(bling_id=88801, name="Cliente Teste Condicional", email="cliente.cond@teste.com")
        db.session.add(cust)
        db.session.flush()

        p1 = Product(bling_id=77701, name="Vestido Seda Exclusivo", sku="TEST-VEST-01", price=300.0, cost=120.0)
        p2 = Product(bling_id=77702, name="Calça Alfaiataria Chic", sku="TEST-CALC-02", price=250.0, cost=100.0)
        p3 = Product(bling_id=77703, name="Blusa Tricot Manga", sku="TEST-BLUS-03", price=150.0, cost=60.0)
        db.session.add_all([p1, p2, p3])
        db.session.flush()

        today = date.today()
        # 1. Pedido de Consignado enviado há 5 dias
        consign_order = Order(
            bling_id=99901,
            number="CSG-TEST-001",
            order_date=today - timedelta(days=5),
            total=700.0,
            status="Atendido",
            seller_name="Camila Consultora",
            payment_method="Consignado",
            customer_id=cust.id
        )
        db.session.add(consign_order)
        db.session.flush()

        i1 = OrderItem(order_id=consign_order.id, product_id=p1.id, sku=p1.sku, product_name=p1.name, quantity=1.0, unit_price=300.0, total_price=300.0)
        i2 = OrderItem(order_id=consign_order.id, product_id=p2.id, sku=p2.sku, product_name=p2.name, quantity=1.0, unit_price=250.0, total_price=250.0)
        i3 = OrderItem(order_id=consign_order.id, product_id=p3.id, sku=p3.sku, product_name=p3.name, quantity=1.0, unit_price=150.0, total_price=150.0)
        db.session.add_all([i1, i2, i3])

        # 2. Pedido de Faturamento da MESMA cliente há 2 dias comprando 2 das 3 peças
        sale_order = Order(
            bling_id=99902,
            number="FAT-TEST-001",
            order_date=today - timedelta(days=2),
            total=550.0,
            status="Atendido",
            seller_name="Camila Consultora",
            payment_method="Cartão de Crédito",
            customer_id=cust.id
        )
        db.session.add(sale_order)
        db.session.flush()

        s1 = OrderItem(order_id=sale_order.id, product_id=p1.id, sku=p1.sku, product_name=p1.name, quantity=1.0, unit_price=300.0, total_price=300.0)
        s2 = OrderItem(order_id=sale_order.id, product_id=p2.id, sku=p2.sku, product_name=p2.name, quantity=1.0, unit_price=250.0, total_price=250.0)
        db.session.add_all([s1, s2])
        db.session.commit()

        # 3. Processa relatório de Malas Condicionais
        start = today - timedelta(days=30)
        end = today
        res = FashionBiEngine.get_conditional_bags_analytics(start, end, seller="Camila Consultora")

        matching_bag = next((b for b in res['bags'] if b['order_number'] == 'CSG-TEST-001'), None)
        assert matching_bag is not None
        assert matching_bag['items_sent'] == 3
        assert matching_bag['items_invoiced'] == 2
        assert matching_bag['items_returned'] == 1
        assert matching_bag['total_sent_value'] == 700.0
        assert matching_bag['total_invoiced_value'] == 550.0
        assert matching_bag['conversion_rate'] == 66.7
        assert '#FAT-TEST-001' in matching_bag['invoiced_orders']
        assert matching_bag['status'] == 'Parcialmente Faturada'
