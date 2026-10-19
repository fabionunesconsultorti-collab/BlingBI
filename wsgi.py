#!/usr/bin/env python3
"""
Ponto de entrada WSGI para ambientes de produção (Gunicorn, uWSGI, Render, Railway, Docker).
"""

import os
from app import create_app
from app.models.order import Order
from app.models.setting import Setting
from app.services.demo_data import seed_demo_data
from app.services.demo_fashion_data import seed_fashion_demo_data

app = create_app()

# Inicialização automática de dados caso o banco esteja novo/vazio
with app.app_context():
    try:
        from app.database import db
        db.create_all()
        if Order.query.count() == 0 and Setting.get('demo_cleared') != '1':
            print("📦 Base de dados inicializada! Populando dados de demonstração para visualização imediata...")
            seed_demo_data()
            seed_fashion_demo_data()
        elif Setting.get('demo_cleared') != '1' and Order.query.filter(Order.payment_method == 'Consignado').count() == 0:
            seed_fashion_demo_data()
    except Exception as e:
        print(f"ℹ️ Verificação de seed inicial concluída: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
