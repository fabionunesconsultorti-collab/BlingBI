import pytest
import os
import tempfile
from app import create_app
from app.database import db
from app.models.master import MasterUser, MasterSegment, PasswordResetToken
from app.models.order import Order
from app.core.tenant_manager import TenantManager

class MultiTenantTestConfig:
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key-multi-tenant'
    # Cria arquivo temporário para o Master DB durante os testes
    _master_tmp = tempfile.mktemp(suffix='_master.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{_master_tmp}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

@pytest.fixture(scope='module')
def test_app():
    app = create_app(MultiTenantTestConfig)
    with app.app_context():
        yield app
    # Limpa arquivo temporário
    if os.path.exists(MultiTenantTestConfig._master_tmp):
        try:
            os.remove(MultiTenantTestConfig._master_tmp)
        except Exception:
            pass

@pytest.fixture
def client(test_app):
    return test_app.test_client()

def test_admin_initialization(test_app):
    """Garante que o Master DB inicializa o usuário 'admgeral' e os segmentos padrão."""
    with test_app.app_context():
        with TenantManager.master_scope():
            admin = MasterUser.query.filter_by(username='admgeral').first()
            assert admin is not None
            assert admin.is_admin is True
            assert admin.check_password('admgeral2026') is True
            assert admin.check_password('senha_errada') is False

            # Verifica segmentos padrão
            fashion_seg = MasterSegment.query.filter_by(slug='fashion').first()
            assert fashion_seg is not None
            assert 'fashion' in fashion_seg.allowed_screens
            assert 'fashion_bi' in fashion_seg.allowed_reports

            food_seg = MasterSegment.query.filter_by(slug='food_restaurant').first()
            assert food_seg is not None
            assert 'fashion' not in food_seg.allowed_screens

def test_login_flow(client, test_app):
    """Testa fluxo de login com credenciais corretas e incorretas."""
    # 1. Login incorreto
    res = client.post('/login', data={'username': 'admgeral', 'password': 'senha_incorreta'}, follow_redirects=True)
    assert 'Usuário ou senha inválidos' in res.get_data(as_text=True)

    # 2. Login correto do admgeral
    res = client.post('/login', data={'username': 'admgeral', 'password': 'admgeral2026'}, follow_redirects=True)
    assert res.status_code == 200
    assert 'Central Multi-Empresas BlingBI' in res.get_data(as_text=True)

    # Logout
    client.get('/logout')

def test_password_change(client, test_app):
    """Testa a alteração de senha de usuário autenticado."""
    # Login
    client.post('/login', data={'username': 'admgeral', 'password': 'admgeral2026'}, follow_redirects=True)

    # Troca de senha
    res = client.post('/change-password', data={
        'current_password': 'admgeral2026',
        'new_password': 'nova_senha_segura_2026',
        'confirm_password': 'nova_senha_segura_2026'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert 'alterada com sucesso' in res.get_data(as_text=True)

    client.get('/logout')

    # Valida que a senha antiga é rejeitada e a nova aceita
    res_fail = client.post('/login', data={'username': 'admgeral', 'password': 'admgeral2026'}, follow_redirects=True)
    assert 'Usuário ou senha inválidos' in res_fail.get_data(as_text=True)

    res_ok = client.post('/login', data={'username': 'admgeral', 'password': 'nova_senha_segura_2026'}, follow_redirects=True)
    assert res_ok.status_code == 200

    # Retorna à senha padrão para consistência dos demais testes
    client.post('/change-password', data={
        'current_password': 'nova_senha_segura_2026',
        'new_password': 'admgeral2026',
        'confirm_password': 'admgeral2026'
    })
    client.get('/logout')

def test_password_reset_token(test_app):
    """Testa geração de token seguro de recuperação de senha e expiração."""
    with test_app.app_context():
        with TenantManager.master_scope():
            user = MasterUser.query.filter_by(username='admgeral').first()
            token_obj = PasswordResetToken.create_token(user, expires_hours=2)
            assert token_obj is not None
            assert token_obj.token is not None
            assert token_obj.is_valid() is True

            # Testa expiração
            token_obj.used = True
            assert token_obj.is_valid() is False

def test_client_creation_and_segment_isolation(client, test_app):
    """Testa criação de cliente pelo admgeral e valida que suas telas são restritas pelo segmento."""
    # 1. Login como admgeral
    client.post('/login', data={'username': 'admgeral', 'password': 'admgeral2026'})

    # 2. Cadastra cliente do segmento Restaurante (não tem a tela 'fashion')
    with test_app.app_context():
        with TenantManager.master_scope():
            food_seg = MasterSegment.query.filter_by(slug='food_restaurant').first()
            seg_id = food_seg.id

    client.post('/admin/clients/new', data={
        'username': 'burger_king_test',
        'email': 'contato@burgerkingtest.com',
        'password': 'senha_cliente_123',
        'company_name': 'Burger King Test Store',
        'segment_id': seg_id,
        'db_type': 'sqlite',
        'seed_data': '0'
    }, follow_redirects=True)

    client.get('/logout')

    # 3. Login como o cliente cadastrado
    res_login = client.post('/login', data={'username': 'burger_king_test', 'password': 'senha_cliente_123'}, follow_redirects=True)
    assert res_login.status_code == 200
    assert 'Burger King Test Store' in res_login.get_data(as_text=True)

    # 4. Acessar tela permitida (Dashboard e Sales) -> Sucesso
    res_sales = client.get('/sales/')
    assert res_sales.status_code == 200

    # 5. Tentar acessar tela não permitida (Fashion BI) -> Bloqueado com redirecionamento
    res_fashion = client.get('/fashion/', follow_redirects=True)
    assert 'não está habilitada para o segmento' in res_fashion.get_data(as_text=True)

    client.get('/logout')

def test_tenant_database_physical_isolation(test_app):
    """Garante que dados inseridos na base do Cliente A não aparecem para o Cliente B."""
    tmp_a = tempfile.mktemp(suffix='_tenant_a.db')
    tmp_b = tempfile.mktemp(suffix='_tenant_b.db')
    uri_a = f'sqlite:///{tmp_a}'
    uri_b = f'sqlite:///{tmp_b}'

    from datetime import datetime
    with test_app.app_context():
        # Inicializa bases
        TenantManager.init_tenant_database(uri_a)
        TenantManager.init_tenant_database(uri_b)

        # Insere pedido na base do Cliente A
        with TenantManager.tenant_scope(uri_a):
            order_a = Order(
                bling_id=999991,
                number='PED-CLI-A-999',
                order_date=datetime.now().date(),
                total=500.0,
                status='Atendido'
            )
            db.session.add(order_a)
            db.session.commit()
            db.session.remove()

        # Insere pedido na base do Cliente B
        with TenantManager.tenant_scope(uri_b):
            order_b = Order(
                bling_id=888881,
                number='PED-CLI-B-111',
                order_date=datetime.now().date(),
                total=120.0,
                status='Atendido'
            )
            db.session.add(order_b)
            db.session.commit()
            db.session.remove()

        # Valida que na base A só existe o pedido do cliente A
        with TenantManager.tenant_scope(uri_a):
            orders_in_a = Order.query.all()
            numbers_a = [o.number for o in orders_in_a]
            assert 'PED-CLI-A-999' in numbers_a
            assert 'PED-CLI-B-111' not in numbers_a
            db.session.remove()

        # Valida que na base B só existe o pedido do cliente B
        with TenantManager.tenant_scope(uri_b):
            orders_in_b = Order.query.all()
            numbers_b = [o.number for o in orders_in_b]
            assert 'PED-CLI-B-111' in numbers_b
            assert 'PED-CLI-A-999' not in numbers_b
            db.session.remove()

    for p in (tmp_a, tmp_b):
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
