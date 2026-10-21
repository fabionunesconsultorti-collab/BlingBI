import pytest
from datetime import date
from app.database import db
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.fashion import ProductReturn, ConditionalBag
from app.services.bi_analytics import BiAnalytics
from app.services.pricing_engine import PricingEngine
from app.services.stock_analysis_service import StockAnalysisService
from app.services.fashion_bi import FashionBiEngine

def test_order_item_and_detail_stock(client, app):
    """Testa se OrderItem e endpoint order_detail retornam o saldo de estoque físico do produto vinculado."""
    with app.app_context():
        # Cria produto com estoque físico conhecido
        p = Product(
            bling_id=99901,
            sku='TEST-STOCK-SKU',
            name='Vestido Longo Floral',
            cost=50.0,
            price=150.0,
            stock=42.0,
            size='M',
            color='Floral Azul',
            category='Vestidos'
        )
        db.session.add(p)
        db.session.commit()

        # Cria pedido e item vinculado com os atributos corretos do modelo
        order = Order(
            bling_id=88801,
            number='PED-999',
            order_date=date.today(),
            total=150.0,
            status='Atendido'
        )
        db.session.add(order)
        db.session.commit()

        item = OrderItem(
            order_id=order.id,
            product_id=p.id,
            sku='TEST-STOCK-SKU',
            product_name='Vestido Longo Floral',
            quantity=2.0,
            unit_price=75.0,
            total_price=150.0
        )
        db.session.add(item)
        db.session.commit()

        # 1. Valida to_dict do OrderItem
        item_dict = item.to_dict()
        assert 'stock' in item_dict
        assert item_dict['stock'] == 42.0

        # 2. Valida rota /sales/orders/<id>
        res = client.get(f'/sales/orders/{order.id}')
        assert res.status_code == 200
        data = res.get_json()
        assert len(data['items']) == 1
        assert data['items'][0]['stock'] == 42.0
        assert data['items'][0]['sku'] == 'TEST-STOCK-SKU'


def test_product_return_stock(app):
    """Testa se devoluções e trocas trazem o saldo de estoque físico."""
    with app.app_context():
        p = Product(
            bling_id=99902,
            sku='CALCA-JEANS-01',
            name='Calça Jeans Slim',
            cost=40.0,
            price=120.0,
            stock=18.0,
            size='40',
            color='Azul Escuro'
        )
        db.session.add(p)
        db.session.commit()

        ret = ProductReturn(
            order_id=1,
            product_id=p.id,
            sku='CALCA-JEANS-01',
            product_name='Calça Jeans Slim',
            customer_name='Consumidor Teste',
            return_date=date.today(),
            quantity=1.0,
            reason='Tamanho não serviu'
        )
        db.session.add(ret)
        db.session.commit()

        ret_dict = ret.to_dict()
        assert 'stock' in ret_dict
        assert ret_dict['stock'] == 18.0


def test_dashboard_and_abc_stock_and_characteristics(app):
    """Testa se o Dashboard e a Curva ABC fornecem saldo de estoque e atributos (sku, tamanho, cor)."""
    with app.app_context():
        start, end = BiAnalytics.parse_date_filter('last_30_days')
        dash = BiAnalytics.get_dashboard_metrics(start, end)
        assert 'top_products' in dash
        if dash['top_products']:
            for prod in dash['top_products']:
                assert 'stock' in prod
                assert 'sku' in prod

        abc = BiAnalytics.get_products_analytics(start, end)
        assert 'abc_products' in abc
        if abc['abc_products']:
            first = abc['abc_products'][0]
            assert 'stock' in first
            assert 'size' in first
            assert 'color' in first


def test_pricing_and_stock_analysis_service(app):
    """Testa se a precificação e a análise de estoque incluem saldo e atributos."""
    with app.app_context():
        p = Product(
            bling_id=99903,
            sku='BLUSA-CREPE-01',
            name='Blusa de Crepe Elegance',
            cost=35.0,
            price=90.0,
            stock=25.0,
            size='G',
            color='Preto',
            category='Blusas'
        )
        db.session.add(p)
        db.session.commit()

        # Pricing Engine
        rules = PricingEngine.get_all_rules()
        assert len(rules) > 0
        pricing_data = PricingEngine.calculate_product_channel_pricing(product=p, rule=rules[0])
        assert pricing_data['stock'] == 25.0
        assert pricing_data['size'] == 'G'
        assert pricing_data['color'] == 'Preto'
        assert pricing_data['category'] == 'Blusas'

        # Stock Analysis Service
        stock_analysis = StockAnalysisService.get_stock_analysis({'q': 'BLUSA-CREPE-01'})
        assert len(stock_analysis['products']) == 1
        prod_res = stock_analysis['products'][0]
        assert prod_res['stock'] == 25.0
        assert prod_res['size'] == 'G'
        assert prod_res['color'] == 'Preto'
