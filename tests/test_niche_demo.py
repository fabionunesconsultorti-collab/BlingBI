import pytest
from app import create_app
from app.database import db
from app.models.product import Product
from app.models.order import Order
from app.models.customer import Customer
from app.models.financial import FinancialEntry
from app.models.setting import Setting
from app.services.niche_demo_data import NICHE_METADATA, seed_niche_demo_data

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

def test_list_demo_niches_endpoint(client):
    """Testa listagem dos 6 setores comerciais via API."""
    res = client.get('/integrations/demo-niches')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert len(data['niches']) == 6
    ids = [n['id'] for n in data['niches']]
    assert 'fashion' in ids
    assert 'furniture_appliances' in ids
    assert 'food_restaurant' in ids
    assert 'home_varieties' in ids
    assert 'toys' in ids
    assert 'tech_mobile' in ids

def test_seed_demo_wrong_password_forbidden(client):
    """Testa que senha incorreta impede a carga da base demonstrativa."""
    res = client.post('/integrations/seed-demo', json={
        'niche': 'furniture_appliances',
        'password': 'senha_errada_123'
    })
    assert res.status_code == 403
    data = res.get_json()
    assert data['success'] is False
    assert 'Senha de segurança incorreta' in data['message']

def test_seed_demo_correct_password_furniture_appliances(client):
    """Testa carga do setor Movelaria & Eletrodomésticos com senha c4nib4l."""
    res = client.post('/integrations/seed-demo', json={
        'niche': 'furniture_appliances',
        'password': 'c4nib4l'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'Movelaria & Eletrodomésticos' in data['message']
    
    # Verifica que produtos do setor foram criados
    products = Product.query.all()
    assert len(products) > 0
    skus = [p.sku for p in products]
    assert 'SOFA-RETR-GRAFITE' in skus
    assert 'GELAD-FROST-450L' in skus

    # Verifica pedidos e clientes
    assert Order.query.count() > 0
    assert Customer.query.count() > 0
    assert FinancialEntry.query.count() > 0

    # Configuração de status salva
    assert Setting.get('demo_niche_id') == 'furniture_appliances'
    assert 'Movelaria' in Setting.get('demo_niche_name')

def test_seed_demo_food_restaurant(client):
    """Testa carga do setor Lanchonete, Bar & Restaurante com senha c4nib4l."""
    res = client.post('/integrations/seed-demo', json={
        'niche': 'food_restaurant',
        'password': 'c4nib4l'
    })
    assert res.status_code == 200
    products = Product.query.all()
    skus = [p.sku for p in products]
    assert 'BURGER-ANGUS-BACON' in skus
    assert 'CHOPP-IPA-500ML' in skus
    assert Setting.get('demo_niche_id') == 'food_restaurant'

def test_seed_demo_home_varieties(client):
    """Testa carga do setor Utilidades Domésticas & Variedades."""
    res = client.post('/integrations/seed-demo', json={
        'niche': 'home_varieties',
        'password': 'c4nib4l'
    })
    assert res.status_code == 200
    products = Product.query.all()
    skus = [p.sku for p in products]
    assert 'POTES-HERM-5PC' in skus
    assert 'MOP-GIRATORIO-360' in skus
    assert Setting.get('demo_niche_id') == 'home_varieties'

def test_seed_demo_toys(client):
    """Testa carga do setor Loja de Brinquedos."""
    res = client.post('/integrations/seed-demo', json={
        'niche': 'toys',
        'password': 'c4nib4l'
    })
    assert res.status_code == 200
    products = Product.query.all()
    skus = [p.sku for p in products]
    assert 'TABULEIRO-CATAN' in skus
    assert 'BONECA-REBORN-48CM' in skus
    assert Setting.get('demo_niche_id') == 'toys'

def test_seed_demo_tech_mobile(client):
    """Testa carga do setor Artigos para Celular & Informática."""
    res = client.post('/integrations/seed-demo', json={
        'niche': 'tech_mobile',
        'password': 'c4nib4l'
    })
    assert res.status_code == 200
    products = Product.query.all()
    skus = [p.sku for p in products]
    assert 'PELICULA-3D-PRIV' in skus
    assert 'CARREG-GAN-35W' in skus
    assert Setting.get('demo_niche_id') == 'tech_mobile'
