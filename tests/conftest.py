import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

import pytest
from app import create_app
from app.database import db
from app.services.demo_data import seed_demo_data

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    IS_POSTGRES = False

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_demo_data()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'admgeral'
        sess['role'] = 'admin'
        sess['is_admin'] = True
        sess['company_name'] = 'Administração Central'
        sess['allowed_screens'] = ['dashboard', 'sales', 'products', 'customers', 'finance', 'fashion', 'reports', 'integrations']
        sess['allowed_reports'] = ['dre', 'cash_flow', 'rfm', 'stock_coverage', 'multichannel', 'fashion_bi']
    return test_client

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
