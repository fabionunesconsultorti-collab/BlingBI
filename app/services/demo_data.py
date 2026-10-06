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

def seed_demo_data():
    """Gera um conjunto completo de dados de BI para teste e demonstração."""
    # Limpa dados anteriores caso existam
    OrderItem.query.delete()
    Order.query.delete()
    Product.query.delete()
    Customer.query.delete()
    FinancialEntry.query.delete()
    db.session.commit()

    # 1. Cria Clientes
    customer_objs = []
    for idx, (name, doc, ptype, email, phone, city, state) in enumerate(DEMO_CUSTOMERS, start=101):
        c = Customer(
            bling_id=idx,
            name=name,
            document=doc,
            person_type=ptype,
            email=email,
            phone=phone,
            city=city,
            state=state,
            created_at=datetime.utcnow() - timedelta(days=random.randint(20, 180))
        )
        db.session.add(c)
        customer_objs.append(c)
    db.session.commit()

    # 2. Cria Produtos
    product_objs = []
    for idx, (sku, name, price, cost, stock, category) in enumerate(DEMO_PRODUCTS, start=201):
        p = Product(
            bling_id=idx,
            sku=sku,
            name=name,
            price=price,
            cost=cost,
            stock=stock,
            category=category,
            status='A'
        )
        db.session.add(p)
        product_objs.append(p)
    db.session.commit()

    # 3. Cria Pedidos dos últimos 60 dias
    today = date.today()
    order_num = 1001

    for days_ago in range(60, -1, -1):
        order_date = today - timedelta(days=days_ago)
        # 1 a 4 pedidos por dia
        daily_orders_count = random.randint(1, 4)
        for _ in range(daily_orders_count):
            cust = random.choice(customer_objs)
            channel = random.choice(CHANNELS)
            status = random.choice(STATUSES)

            order = Order(
                bling_id=order_num + 5000,
                number=str(order_num),
                order_date=order_date,
                status=status,
                channel=channel,
                customer_id=cust.id,
                total=0.0,
                discount=random.choice([0.0, 10.0, 25.0]),
                shipping=random.choice([0.0, 19.90, 29.90, 45.00])
            )
            db.session.add(order)
            db.session.flush()

            # Adiciona 1 a 3 itens no pedido
            selected_products = random.sample(product_objs, random.randint(1, 3))
            subtotal = 0.0
            for prod in selected_products:
                qty = random.randint(1, 2)
                item_total = prod.price * qty
                subtotal += item_total
                item = OrderItem(
                    order_id=order.id,
                    product_id=prod.id,
                    product_name=prod.name,
                    sku=prod.sku,
                    quantity=qty,
                    unit_price=prod.price,
                    cost_price=prod.cost,
                    total_price=item_total
                )
                db.session.add(item)

            order.total = max(0.0, subtotal - order.discount + order.shipping)
            order_num += 1

    db.session.commit()

    # 4. Cria Contas a Pagar e Receber
    # Contas a Receber (baseadas em vendas atendidas)
    fin_id = 9001
    for days_ago in range(45, -15, -3):
        due = today - timedelta(days=days_ago)
        is_past = due <= today
        status = 'Pago' if is_past and random.random() > 0.1 else ('Atrasado' if is_past else 'Pendente')
        pay_date = due if status == 'Pago' else None

        rec = FinancialEntry(
            bling_id=fin_id,
            entry_type='RECEBER',
            description=f"Recebimento de Venda / Parcela {random.randint(1, 3)}x",
            entity_name=random.choice(DEMO_CUSTOMERS)[0],
            category="Vendas de Mercadorias",
            amount=round(random.uniform(350.0, 3800.0), 2),
            issue_date=due - timedelta(days=15),
            due_date=due,
            payment_date=pay_date,
            status=status,
            payment_method=random.choice(["Pix", "Boleto Bancário", "Cartão de Crédito"])
        )
        db.session.add(rec)
        fin_id += 1

    # Contas a Pagar (fornecedores, impostos, operacional)
    expenses = [
        ("Fornecedor Componentes Tech SP", "Aquisição de Mercadorias / Custo", 1500.0, 7500.0, "Fornecedores"),
        ("Receita Federal / Simples Nacional", "Tributos e Impostos sobre Vendas", 800.0, 2400.0, "Impostos"),
        ("Aluguel Galpão / Escritório", "Despesas Operacionais Fixas", 2200.0, 2200.0, "Operacional"),
        ("Correios & Transportadoras", "Fretes e Logística Reversa", 650.0, 1850.0, "Logística"),
        ("Plataforma E-commerce & Hospedagem", "Softwares e Ferramentas", 350.0, 700.0, "Tecnologia"),
    ]

    for days_ago in range(45, -20, -5):
        due = today - timedelta(days=days_ago)
        is_past = due <= today
        supplier, desc, min_v, max_v, cat = random.choice(expenses)
        status = 'Pago' if is_past and random.random() > 0.08 else ('Atrasado' if is_past else 'Pendente')
        pay_date = due if status == 'Pago' else None

        pag = FinancialEntry(
            bling_id=fin_id,
            entry_type='PAGAR',
            description=desc,
            entity_name=supplier,
            category=cat,
            amount=round(random.uniform(min_v, max_v), 2),
            issue_date=due - timedelta(days=20),
            due_date=due,
            payment_date=pay_date,
            status=status,
            payment_method=random.choice(["Boleto Bancário", "Pix"])
        )
        db.session.add(pag)
        fin_id += 1

    # Atualiza configuração de status
    Setting.set('demo_mode_active', '1')
    Setting.set('demo_cleared', '0')
    Setting.set('last_sync_date', datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S'))
    Setting.set('last_sync_status', 'Dados de Demonstração Carregados')
    db.session.commit()
    return True

def clear_demo_data():
    """
    Remove todos os registros operacionais (pedidos, itens, produtos, clientes, financeiro)
    mantendo intactas as configurações e chaves de integração do Bling.
    """
    try:
        OrderItem.query.delete()
        Order.query.delete()
        Product.query.delete()
        Customer.query.delete()
        FinancialEntry.query.delete()

        Setting.set('demo_mode_active', '0')
        Setting.set('demo_cleared', '1')
        Setting.set('last_sync_date', '-')
        Setting.set('last_sync_status', 'Base zerada - Pronta para sincronização real')
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise e
