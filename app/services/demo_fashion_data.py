import random
from datetime import datetime, timedelta, date
from sqlalchemy import func
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.fashion import ConditionalBag, ProductReturn, SellerAttendance, CustomerSurvey

FASHION_PRODUCTS = [
    ("VEST-MIDI-FLORAL", "Vestido Midi Floral Evasê", 389.90, 160.00, 35, "Vestidos", "M", "Floral / Terracota", "Casual Chic"),
    ("BLAZER-LINHO-OFF", "Blazer Linho Puro Estruturado", 549.90, 240.00, 22, "Alfaiataria", "G", "Off White", "Alfaiataria"),
    ("CALCA-ALF-PRETA", "Calça Alfaiataria Cenoura com Cinto", 319.90, 130.00, 45, "Alfaiataria", "38", "Preto Clássico", "Alfaiataria"),
    ("JEANS-WIDE-LEG", "Calça Jeans Wide Leg Cintura Alta", 299.90, 120.00, 60, "Jeanswear", "40", "Azul Médio", "Urbano / Casual"),
    ("CAMISA-SEDA-AZUL", "Camisa Manga Longa Toque de Seda", 279.90, 110.00, 30, "Blusas & Camisas", "P", "Azul Serenity", "Elegante"),
    ("CROPPED-TRICOT", "Cropped Tricot Canelado Decote V", 159.90, 60.00, 50, "Blusas & Camisas", "M", "Fúcsia Vibrante", "Casual"),
    ("CONJ-RESORT-VERAO", "Conjunto Resort Coleção Verão (Top + Shorts)", 429.90, 180.00, 25, "Conjuntos", "M", "Verde Oliva", "Resort"),
    ("VEST-FESTA-PAETE", "Vestido Longo Gala Paetê", 899.90, 390.00, 15, "Festas & Noite", "P", "Dourado Champagne", "Gala"),
    ("JAQUETA-COURO-ECO", "Jaqueta Biker Couro Ecológico", 499.90, 210.00, 28, "Casacos & Jaquetas", "G", "Preto", "Moderno"),
    ("SAIA-PLISSADA-MIDI", "Saia Plissada Midi Acetinada", 259.90, 95.00, 40, "Saias", "M", "Rosé Gold", "Romântico Chic"),
]

SIZES = ["PP", "P", "M", "G", "GG", "36", "38", "40", "42", "44"]
COLORS = ["Preto", "Branco", "Off White", "Azul Serenity", "Fúcsia", "Verde Oliva", "Terracota", "Rosé Gold", "Dourado", "Marinho"]
STYLES = ["Casual", "Casual Chic", "Alfaiataria", "Romântico", "Moderno", "Festas & Gala", "Resort", "Urbano"]
CHANNELS = ["WhatsApp VIP", "Loja Física", "Instagram Direct", "Telefone", "E-commerce"]
RETURN_REASONS = [
    "Tamanho / Caimento inadequado",
    "Gosto pessoal / Estilo",
    "Defeito de fabricação",
    "Arrependimento de compra",
    "Cor diferente do esperado"
]
FEEDBACKS = [
    "Atendimento impecável e peças de altíssima qualidade!",
    "Amei o caimento das peças, a consultora foi super atenciosa.",
    "Entrega rápida e produtos maravilhosos.",
    "Gostei muito das opções sugeridas na mala condicional.",
    "Excelente consultoria de estilo e pós-venda exemplar."
]

def get_registered_sellers():
    """Retorna exclusivamente consultores reais cadastrados na conta Bling ou na base."""
    try:
        from app.services.bling_api import BlingApiClient
        client = BlingApiClient()
        res = client.request('GET', '/vendedores?limite=100')
        if res and res.status_code == 200:
            names = [v.get('contato', {}).get('nome') or v.get('nome') for v in res.json().get('data', []) if v.get('contato', {}).get('nome') or v.get('nome')]
            if names:
                return names
    except Exception:
        pass

    fictitious = {'Camila Duarte', 'Mariana Rios', 'Beatriz Santos', 'Lucas Mendes', 'Camila Consultora'}
    existing = [
        r[0] for r in db.session.query(Order.seller_name).filter(
            Order.seller_name.isnot(None),
            Order.seller_name != '',
            Order.seller_name != 'None'
        ).distinct().all() 
        if r[0] and r[0] not in fictitious
    ]
    if existing:
        return existing
    return ['Natalia Ferruci']

def seed_fashion_demo_data():
    """
    Popula ou enriquece a base com dados realistas do ecossistema de Varejo de Moda e Customer Success.
    NÃO inventa consultores: utiliza exclusivamente os consultores devidamente cadastrados.
    """
    today = date.today()
    registered_sellers = get_registered_sellers()
    default_seller = registered_sellers[0] if registered_sellers else "Natalia Ferruci"

    # 1. Atualiza ou cria produtos de moda
    max_b_id = db.session.query(func.max(Product.bling_id)).scalar() or 90000
    for idx, (sku, name, price, cost, stock, cat, size, color, style) in enumerate(FASHION_PRODUCTS, start=1):
        p = Product.query.filter_by(sku=sku).first()
        if not p:
            max_b_id += 1
            p = Product(
                bling_id=max_b_id,
                sku=sku,
                name=name,
                price=price,
                cost=cost,
                stock=stock,
                category=cat,
                size=size,
                color=color,
                style=style,
                status='A'
            )
            db.session.add(p)
        else:
            p.size = size
            p.color = color
            p.style = style
            p.category = cat
    db.session.commit()

    # 2. Atualiza clientes com atributos de moda e datas de nascimento
    customers = Customer.query.all()
    for idx, c in enumerate(customers):
        if not c.birth_date:
            if idx % 3 == 0:
                b_month = today.month
                b_day = random.randint(1, min(28, today.day + 10))
            else:
                b_month = random.randint(1, 12)
                b_day = random.randint(1, 28)
            b_year = random.randint(1975, 2002)
            c.birth_date = date(b_year, b_month, b_day)

        if not c.preferred_size:
            c.preferred_size = random.choice(SIZES)
        if not c.preferred_style:
            c.preferred_style = random.choice(STYLES)
    db.session.commit()

    # 3. Atualiza atributos nos itens (SEM alterar vendedor do pedido)
    orders = Order.query.all()
    for o in orders:
        if not o.payment_method:
            o.payment_method = random.choice(["Cartão de Crédito", "Pix", "Boleto Bancário"])
        for item in o.items:
            if not item.size:
                item.size = random.choice(SIZES)
            if not item.color:
                item.color = random.choice(COLORS)
            if not item.style:
                item.style = random.choice(STYLES)
    db.session.commit()

    # 4. Cria Pedidos de Consignado e Pedidos de Faturamento da Mesma Cliente
    if ConditionalBag.query.count() == 0 and customers:
        fashion_prods = Product.query.filter(Product.category.in_(["Vestidos", "Alfaiataria", "Jeanswear", "Blusas & Camisas", "Conjuntos", "Saias"])).all()
        if not fashion_prods:
            fashion_prods = Product.query.limit(10).all()

        max_order_bid = db.session.query(func.max(Order.bling_id)).scalar() or 500000

        for i in range(1, 21):
            cust = random.choice(customers)
            seller = default_seller
            sent_days_ago = random.randint(3, 40)
            sent_dt = today - timedelta(days=sent_days_ago)
            consign_num = f"CSG-{sent_dt.strftime('%y%m')}-{i:03d}"

            max_order_bid += 1
            # 4.1 Pedido de Consignado (Mala de Prova)
            consign_order = Order(
                bling_id=max_order_bid,
                number=consign_num,
                order_date=sent_dt,
                total=0.0,
                discount=0.0,
                shipping=0.0,
                status='Atendido',
                channel=random.choice(["WhatsApp VIP", "Loja Física"]),
                seller_name=seller,
                payment_method='Consignado',
                notes=f"Mala condicional #{consign_num} enviada com looks selecionados para prova domiciliar.",
                customer_id=cust.id
            )
            db.session.add(consign_order)
            db.session.flush()

            # Adiciona de 5 a 8 peças na mala consignada
            chosen_prods = random.sample(fashion_prods, min(len(fashion_prods), random.randint(5, 8)))
            consign_total = 0.0
            consign_items = []

            for p in chosen_prods:
                u_price = float(p.price or 250.0)
                c_price = float(p.cost or 110.0)
                item = OrderItem(
                    order_id=consign_order.id,
                    product_id=p.id,
                    product_name=p.name,
                    sku=p.sku,
                    size=p.size or random.choice(SIZES),
                    color=p.color or random.choice(COLORS),
                    style=p.style or random.choice(STYLES),
                    quantity=1.0,
                    unit_price=u_price,
                    cost_price=c_price,
                    total_price=u_price
                )
                db.session.add(item)
                consign_items.append(item)
                consign_total += u_price

            consign_order.total = round(consign_total, 2)

            # 4.2 Pedido de Faturamento da MESMA cliente com as peças do consignado
            # 75% das malas convertem vendas parciais ou totais
            if i % 4 != 0 and len(consign_items) >= 2:
                invoiced_count = random.randint(2, max(2, len(consign_items) - 1))
                invoiced_items_sample = random.sample(consign_items, invoiced_count)

                sale_dt = sent_dt + timedelta(days=random.randint(2, 5))
                sale_num = f"FAT-{sale_dt.strftime('%y%m')}-{i:03d}"
                max_order_bid += 1

                sale_order = Order(
                    bling_id=max_order_bid,
                    number=sale_num,
                    order_date=sale_dt,
                    total=0.0,
                    discount=0.0,
                    shipping=0.0,
                    status='Atendido',
                    channel=consign_order.channel,
                    seller_name=seller,
                    payment_method=random.choice(["Cartão de Crédito", "Pix"]),
                    notes=f"Faturamento de peças referente à mala condicional #{consign_num}",
                    customer_id=cust.id
                )
                db.session.add(sale_order)
                db.session.flush()

                sale_total = 0.0
                for c_item in invoiced_items_sample:
                    sale_item = OrderItem(
                        order_id=sale_order.id,
                        product_id=c_item.product_id,
                        product_name=c_item.product_name,
                        sku=c_item.sku,
                        size=c_item.size,
                        color=c_item.color,
                        style=c_item.style,
                        quantity=1.0,
                        unit_price=c_item.unit_price,
                        cost_price=c_item.cost_price,
                        total_price=c_item.unit_price
                    )
                    db.session.add(sale_item)
                    sale_total += c_item.unit_price

                sale_order.total = round(sale_total, 2)

            # Mantém também ConditionalBag sincronizado para compatibilidade
            sent_pieces_count = len(consign_items)
            inv_pieces_count = invoiced_count if (i % 4 != 0 and len(consign_items) >= 2) else 0
            ret_pieces_count = sent_pieces_count - inv_pieces_count
            inv_val = sum(it.unit_price for it in invoiced_items_sample) if (i % 4 != 0 and len(consign_items) >= 2) else 0.0

            bag = ConditionalBag(
                bag_code=consign_num,
                customer_id=cust.id,
                customer_name=cust.name,
                seller_name=seller,
                items_sent=sent_pieces_count,
                items_invoiced=inv_pieces_count,
                items_returned=ret_pieces_count,
                total_sent_value=round(consign_total, 2),
                total_invoiced_value=round(inv_val, 2),
                status='Finalizada' if inv_pieces_count > 0 else ('Em Aberto' if sent_days_ago <= 7 else 'Cancelada'),
                sent_date=sent_dt,
                return_date=sent_dt + timedelta(days=3),
                notes=f"Mala condicional de peças consignadas #{consign_num}"
            )
            db.session.add(bag)

        db.session.commit()

    # 5. Cria Trocas e Devoluções se ainda não existirem
    if ProductReturn.query.count() == 0 and orders:
        fashion_prods = Product.query.filter(Product.category.in_(["Vestidos", "Alfaiataria", "Jeanswear", "Blusas & Camisas"])).all()
        for i in range(1, 18):
            rand_order = random.choice(orders)
            rand_prod = random.choice(fashion_prods) if fashion_prods else random.choice(Product.query.all())
            cust = rand_order.customer or (customers[0] if customers else None)
            ret_days_ago = random.randint(1, 40)
            ret_dt = today - timedelta(days=ret_days_ago)

            ret = ProductReturn(
                order_id=rand_order.id,
                product_id=rand_prod.id,
                sku=rand_prod.sku,
                product_name=rand_prod.name,
                customer_id=cust.id if cust else None,
                customer_name=cust.name if cust else "Consumidor Final",
                seller_name=rand_order.seller_name or default_seller,
                quantity=float(random.randint(1, 2)),
                reason=random.choice(RETURN_REASONS),
                return_date=ret_dt
            )
            db.session.add(ret)
        db.session.commit()

    # 6. Cria Atendimentos / Leads comerciais se ainda não existirem
    if SellerAttendance.query.count() == 0 and customers:
        for i in range(1, 50):
            seller = default_seller
            cust = random.choice(customers)
            channel = random.choice(CHANNELS)
            converted = random.choice([True, True, False, False, True]) # ~60% conversão
            att_days_ago = random.randint(1, 45)
            att_dt = today - timedelta(days=att_days_ago)

            att = SellerAttendance(
                seller_name=seller,
                customer_id=cust.id,
                customer_name=cust.name,
                channel=channel,
                converted=converted,
                attendance_date=att_dt,
                notes="Atendimento consultivo com indicação de paleta de cores e lookbook"
            )
            db.session.add(att)
        db.session.commit()

    # 7. Cria Pesquisas de Satisfação NPS / CSAT se ainda não existirem
    if CustomerSurvey.query.count() == 0 and customers:
        for i in range(1, 35):
            cust = random.choice(customers)
            seller = default_seller
            # Distribuição realista de NPS no varejo premium de moda (maioria promotores)
            nps = random.choice([10, 10, 9, 9, 8, 7, 10, 9, 5, 10])
            csat = 5 if nps >= 9 else (4 if nps >= 7 else 3)
            surv_days_ago = random.randint(1, 40)
            surv_dt = today - timedelta(days=surv_days_ago)

            surv = CustomerSurvey(
                customer_id=cust.id,
                customer_name=cust.name,
                seller_name=seller,
                nps_score=nps,
                csat_score=csat,
                feedback=random.choice(FEEDBACKS),
                survey_date=surv_dt
            )
            db.session.add(surv)
        db.session.commit()

    print("👗 Dados de demonstração de Varejo de Moda e CS populados com sucesso!")
