import random
from datetime import datetime, timedelta, date
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.financial import FinancialEntry
from app.models.setting import Setting

DEMO_CUSTOMERS = [
    ("TechCorp Informática Ltda", "12.345.678/0001-90", "J", "contato@techcorp.com.br", "(11) 98765-4321", "São Paulo", "SP"),
    ("Móveis & Decoração Brasil", "98.765.432/0001-10", "J", "compras@moveisbrasil.com.br", "(41) 99876-5432", "Curitiba", "PR"),
    ("Carlos Eduardo Silva", "123.456.789-00", "F", "carlos.silva@email.com", "(21) 97654-3210", "Rio de Janeiro", "RJ"),
    ("Mariana Souza Oliveira", "234.567.890-11", "F", "mariana.souza@email.com", "(31) 98877-6655", "Belo Horizonte", "MG"),
    ("Distribuidora Aliança S/A", "45.678.901/0001-22", "J", "pedidos@alianca.com.br", "(19) 99123-4567", "Campinas", "SP"),
    ("Fernanda Costa Pereira", "345.678.901-22", "F", "fernanda.costa@email.com", "(51) 98111-2233", "Porto Alegre", "RS"),
    ("Inovação Varejo ME", "78.901.234/0001-55", "J", "financeiro@inovacaovarejo.com.br", "(47) 99444-5566", "Joinville", "SC"),
    ("Lucas Martins Rocha", "456.789.012-33", "F", "lucas.rocha@email.com", "(61) 98222-3344", "Brasília", "DF"),
    ("Juliana Lima Santos", "567.890.123-44", "F", "juliana.lima@email.com", "(71) 98333-4455", "Salvador", "BA"),
    ("Mercado Global Eireli", "32.109.876/0001-33", "J", "atendimento@mercadoglobal.com", "(81) 99555-6677", "Recife", "PE"),
]

DEMO_PRODUCTS = [
    ("MON-27-4K", "Monitor Gamer 27' 4K 144Hz", 1899.90, 1150.00, 42, "Informática"),
    ("KB-MECH-RGB", "Teclado Mecânico RGB Switch Blue", 289.90, 130.00, 85, "Periféricos"),
    ("MOU-PRO-WRL", "Mouse Sem Fio Sensor 16000 DPI", 199.90, 85.00, 120, "Periféricos"),
    ("HD-SSD-1TB", "SSD NVMe M.2 1TB 3500MB/s", 429.90, 240.00, 65, "Hardware"),
    ("HD-SSD-2TB", "SSD NVMe M.2 2TB 7000MB/s", 799.90, 460.00, 28, "Hardware"),
    ("CAB-USBC-2M", "Cabo USB-C Trançado Reforçado 2m", 49.90, 14.00, 310, "Acessórios"),
    ("FONE-ANC-BT", "Headset Bluetooth com Cancelamento de Ruído", 549.90, 280.00, 50, "Áudio"),
    ("SUP-ERG-NOTE", "Suporte Ergonômico de Alumínio para Notebook", 139.90, 52.00, 94, "Acessórios"),
    ("WEBCAM-4K", "Webcam 4K Ultra HD com Microfone Duplo", 459.90, 220.00, 35, "Vídeo"),
    ("MIC-USB-COND", "Microfone Condensador USB para Podcast", 329.90, 155.00, 18, "Áudio"),
]

CHANNELS = ["Mercado Livre", "Site Próprio", "Shopee", "Amazon Brasil", "Loja Física / Balcão"]
STATUSES = ["Atendido", "Atendido", "Atendido", "Atendido", "Em aberto", "Cancelado"]

from app.services.niche_demo_data import seed_niche_demo_data, clear_operational_data, NICHE_METADATA

def seed_demo_data(niche: str = "fashion"):
    """Gera um conjunto completo de dados de BI para teste e demonstração para o nicho especificado."""
    return seed_niche_demo_data(niche=niche, clear_first=True)

def clear_demo_data():
    """
    Remove todos os registros operacionais (pedidos, itens, produtos, clientes, financeiro, malas)
    mantendo intactas as configurações e chaves de integração do Bling.
    """
    try:
        clear_operational_data()

        Setting.set('demo_mode_active', '0')
        Setting.set('demo_cleared', '1')
        Setting.set('demo_niche_id', '')
        Setting.set('demo_niche_name', '')
        Setting.set('last_sync_date', '-')
        Setting.set('last_sync_status', 'Base zerada - Pronta para sincronização real')
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise e

