#!/usr/bin/env python3
"""
BlingBI Launcher
Inicia o servidor local Flask e abre automaticamente a aplicação no navegador padrão.
"""

import sys
import os
import threading
import webbrowser
import time
from app import create_app
from app.models.order import Order
from app.models.setting import Setting
from app.services.demo_data import seed_demo_data
from app.services.demo_fashion_data import seed_fashion_demo_data

def open_browser(url):
    """Aguarda um instante para o servidor subir e abre no navegador."""
    time.sleep(1.2)
    print(f"\n🚀 Abrindo BlingBI no navegador: {url}")
    webbrowser.open_new(url)

def main():
    port = int(os.environ.get('PORT', 5000))
    host = '127.0.0.1'
    url = f"http://{host}:{port}"

    app = create_app()

    with app.app_context():
        # Se for o primeiro acesso e a base estiver vazia, inicializa com dados de demonstração
        # apenas se o usuário ainda não tiver optado por limpar a base
        if Order.query.count() == 0 and Setting.get('demo_cleared') != '1':
            print("📦 Base de dados inicializada! Populando dados de demonstração para visualização imediata...")
            seed_demo_data()
            seed_fashion_demo_data()
        elif Setting.get('demo_cleared') != '1' and Order.query.filter(Order.payment_method == 'Consignado').count() == 0:
            seed_fashion_demo_data()

    # Verifica se deve abrir o navegador (por padrão abre, exceto se passado --no-browser)
    if '--no-browser' not in sys.argv:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    print(f"\n=======================================================")
    print(f"       🟢 BlingBI - Painel Analítico & Decisão       ")
    print(f"=======================================================")
    print(f" Servidor executando em: {url}")
    print(f" Pressione Ctrl+C para encerrar o servidor.")
    print(f"=======================================================\n")

    app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    main()
