import re
from sqlalchemy import or_, desc, asc
from app.database import db
from app.models.product import Product

COMMON_COLORS = [
    'off white', 'azul marinho', 'azul serenity', 'verde oliva', 'verde agua', 'verde água',
    'amarelo manteiga', 'rose gold', 'rosé gold', 'rosa pink', 'preto', 'branco',
    'marrom', 'azul', 'verde', 'rosa', 'fucsia', 'fúcsia', 'vermelho', 'vermelha',
    'amarelo', 'amarela', 'terracota', 'dourado', 'prata', 'bege', 'nude', 'laranja',
    'cinza', 'lavanda', 'lilás', 'vinho', 'bordo', 'bordô', 'mostarda', 'caramelo', 'pink'
]

STANDARD_SIZES = ['34', '36', '38', '40', '42', '44', '46', 'PP', 'P', 'M', 'G', 'GG', 'Único']

def parse_product_attributes(name: str):
    """
    Extrai inteligentemente tamanho e cor do nome do produto caso existam no padrão Bling / Varejo de Moda.
    """
    if not name:
        return None, None
    size = None
    color = None
    
    # 1. Detecção de Tamanho
    tam_match = re.search(r'(?:Tam|Tamanho)[\s:]*([0-9]{2}|PP|P|M|G|GG|XG|XGG|UNICO|ÚNICO)\b', name, re.IGNORECASE)
    if tam_match:
        val = tam_match.group(1).upper()
        size = 'Único' if val in ('UNICO', 'ÚNICO') else val
    else:
        end_match = re.search(r'[\s,:-](PP|P|M|G|GG|XG|34|36|38|40|42|44|46|48)$', name.strip(), re.IGNORECASE)
        if end_match:
            size = end_match.group(1).upper()
        else:
            glued = re.search(r'(?:preto|branco|marrom|azul|verde|rosa|amarelo|gola|listra)[\s:]*([0-9]{2}|PP|P|M|G|GG)\b', name, re.IGNORECASE)
            if glued:
                size = glued.group(1).upper()

    # 2. Detecção de Cor
    cor_explicit = re.search(r'(?:Cor|Cores)[\s:]*([a-zA-ZáàâãéèêíïóôõöúçñÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ\s/]+?)(?:\s+(?:Tam|Tamanho|[0-9]{2}|PP|P|M|G|GG)|,|$)', name, re.IGNORECASE)
    if cor_explicit:
        c_raw = cor_explicit.group(1).strip()
        if len(c_raw) >= 3 and not c_raw.lower().startswith('diversas') and not c_raw.lower().startswith('variadas'):
            color = c_raw.title()

    if not color:
        for cp in COMMON_COLORS:
            if re.search(r'\b' + re.escape(cp) + r'\b', name, re.IGNORECASE):
                color = cp.title()
                break

    return size, color


def enrich_products_attributes_if_needed():
    """
    Varre os produtos no banco de dados e preenche size/color caso estejam nulos,
    garantindo que produtos já sincronizados do Bling sejam catalogados por tamanho e cor.
    """
    needs_enrichment = Product.query.filter(
        or_(Product.size.is_(None), Product.size == '', Product.color.is_(None), Product.color == '')
    ).limit(1).first()
    
    if not needs_enrichment:
        return

    products = Product.query.all()
    updated = False
    for p in products:
        s, c = parse_product_attributes(p.name)
        if s and not p.size:
            p.size = s
            updated = True
        if c and not p.color:
            p.color = c
            updated = True

    if updated:
        db.session.commit()


def get_catalog_filter_options():
    """
    Retorna opções dinâmicas para preenchimento dos selects de filtro de produtos.
    """
    db_sizes = [r[0] for r in db.session.query(Product.size).filter(Product.size.isnot(None), Product.size != '').distinct().all() if r[0]]
    all_sizes = sorted(list(set(STANDARD_SIZES + db_sizes)), key=lambda x: (
        0 if x in ['PP', 'P', 'M', 'G', 'GG'] else (1 if x.isdigit() else 2),
        int(x) if x.isdigit() else x
    ))

    db_colors = [r[0] for r in db.session.query(Product.color).filter(Product.color.isnot(None), Product.color != '').distinct().all() if r[0]]
    default_colors = ['Amarelo', 'Azul', 'Azul Marinho', 'Bege', 'Branco', 'Cinza', 'Dourado', 'Laranja', 'Marrom', 'Off White', 'Preto', 'Rosa', 'Terracota', 'Verde', 'Verde Oliva', 'Vermelho', 'Vinho']
    all_colors = sorted(list(set(default_colors + db_colors)))

    return {
        'sizes': all_sizes,
        'colors': all_colors
    }


def search_catalog_products(q=None, size=None, color=None, stock_status='all', status='all', sort='name_asc'):
    """
    Executa busca geral com múltiplos critérios combináveis:
    - q: Nome ou SKU
    - size: Tamanho específico (ex: P, M, 38)
    - color: Cor específica (ex: Preto, Off White)
    - stock_status: 'all', 'in_stock' (> 0), 'zero_stock' (<= 0)
    - status: 'all', 'A' (Ativo), 'I' (Inativo)
    - sort: ordenação dos resultados
    """
    query = Product.query

    # 1. Busca por termo geral (Nome ou SKU)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(Product.name.ilike(term), Product.sku.ilike(term)))

    # 2. Busca por Tamanho
    if size and size != 'all':
        size_clean = size.strip()
        # Procura tanto na coluna size quanto no nome do produto (ex: 'Tam:38', ' 38', 'tam: 38')
        size_conditions = [
            Product.size == size_clean,
            Product.name.ilike(f"%Tam:{size_clean}%"),
            Product.name.ilike(f"%Tamanho:{size_clean}%"),
            Product.name.ilike(f"% {size_clean}"),
            Product.name.ilike(f"% {size_clean} %")
        ]
        query = query.filter(or_(*size_conditions))

    # 3. Busca por Cor
    if color and color != 'all':
        color_clean = color.strip()
        query = query.filter(or_(
            Product.color.ilike(f"%{color_clean}%"),
            Product.name.ilike(f"%{color_clean}%")
        ))

    # 4. Saldo em Estoque
    if stock_status == 'in_stock':
        query = query.filter(Product.stock > 0)
    elif stock_status == 'zero_stock':
        query = query.filter(Product.stock <= 0)

    # 5. Status do produto
    if status and status != 'all':
        query = query.filter(Product.status == status)

    # 6. Ordenação
    if sort == 'stock_desc':
        query = query.order_by(desc(Product.stock), asc(Product.name))
    elif sort == 'stock_asc':
        query = query.order_by(asc(Product.stock), asc(Product.name))
    elif sort == 'price_desc':
        query = query.order_by(desc(Product.price), asc(Product.name))
    elif sort == 'price_asc':
        query = query.order_by(asc(Product.price), asc(Product.name))
    else: # name_asc
        query = query.order_by(asc(Product.name))

    products = query.all()

    # Monta métricas consolidadas dos produtos filtrados
    total_found = len(products)
    total_stock_qty = sum(float(p.stock or 0.0) for p in products)
    total_stock_value = sum(float(p.stock or 0.0) * float(p.price or 0.0) for p in products if (p.stock or 0) > 0)
    avg_price = (sum(float(p.price or 0.0) for p in products) / total_found) if total_found > 0 else 0.0

    prods_data = []
    for p in products:
        p_price = float(p.price or 0.0)
        p_cost = float(p.cost or 0.0)
        margin_rs = p_price - p_cost
        margin_pct = (margin_rs / p_price * 100) if p_price > 0 else 0.0

        # Se size ou color não estiverem gravados, resolve pelo nome em runtime
        p_size = p.size
        p_color = p.color
        if not p_size or not p_color:
            s_det, c_det = parse_product_attributes(p.name)
            p_size = p_size or s_det or 'N/D'
            p_color = p_color or c_det or 'N/D'

        prods_data.append({
            'id': p.id,
            'bling_id': p.bling_id,
            'sku': p.sku or 'S/ Cód',
            'name': p.name,
            'size': p_size,
            'color': p_color,
            'stock': float(p.stock or 0.0),
            'price': p_price,
            'cost': p_cost,
            'margin_rs': margin_rs,
            'margin_pct': margin_pct,
            'status': p.status or 'A'
        })

    return {
        'products': prods_data,
        'summary': {
            'total_found': total_found,
            'total_stock_qty': total_stock_qty,
            'total_stock_value': total_stock_value,
            'avg_price': avg_price
        }
    }


def get_inventory_catalog_analytics(start_date, end_date, q=None, size=None, color=None, stock_status='all', abc_class='all', status='all', sort='name_asc'):
    """
    Retorna métricas e catálogo completo integrado para a aba Inventário & Catálogo de Produtos,
    com suporte à busca por tamanho, cor, nome, SKU, saldo em estoque e curva ABC.
    """
    from app.models.order import Order, OrderItem
    from sqlalchemy import func

    # 1. Agrega vendas por produto no período
    sold_rows = db.session.query(
        OrderItem.product_id,
        func.sum(OrderItem.quantity).label('qty_sold'),
        func.sum(OrderItem.total_price).label('revenue_sold'),
        func.sum(OrderItem.cost_price * OrderItem.quantity).label('total_cost')
    ).join(Order, OrderItem.order_id == Order.id).filter(
        Order.order_date >= start_date,
        Order.order_date <= end_date,
        Order.status == 'Atendido'
    ).group_by(OrderItem.product_id).order_by(desc('revenue_sold')).all()

    total_revenue_all = sum(float(r.revenue_sold or 0.0) for r in sold_rows)
    acc = 0.0
    abc_sales_map = {}
    for r in sold_rows:
        rev = float(r.revenue_sold or 0.0)
        cost = float(r.total_cost or 0.0)
        margin = rev - cost
        margin_pct = (margin / rev * 100) if rev > 0 else 0.0
        acc += rev
        pct = (acc / total_revenue_all * 100) if total_revenue_all > 0 else 100.0
        cl = 'A' if pct <= 80.0 else ('B' if pct <= 95.0 else 'C')
        abc_sales_map[r.product_id] = {
            'qty_sold': float(r.qty_sold or 0.0),
            'revenue': rev,
            'margin': margin,
            'margin_pct': margin_pct,
            'class': cl
        }

    # 2. Constrói query de produtos
    query = Product.query

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(Product.name.ilike(term), Product.sku.ilike(term)))

    if size and size != 'all':
        size_clean = size.strip()
        query = query.filter(or_(
            Product.size == size_clean,
            Product.name.ilike(f"%Tam:{size_clean}%"),
            Product.name.ilike(f"%Tamanho:{size_clean}%"),
            Product.name.ilike(f"% {size_clean}"),
            Product.name.ilike(f"% {size_clean} %")
        ))

    if color and color != 'all':
        color_clean = color.strip()
        query = query.filter(or_(
            Product.color.ilike(f"%{color_clean}%"),
            Product.name.ilike(f"%{color_clean}%")
        ))

    if stock_status == 'in_stock':
        query = query.filter(Product.stock > 0)
    elif stock_status == 'zero_stock':
        query = query.filter(Product.stock <= 0)

    if status and status != 'all':
        query = query.filter(Product.status == status)

    # Ordenação padrão da query
    if sort == 'stock_desc':
        query = query.order_by(desc(Product.stock), asc(Product.name))
    elif sort == 'stock_asc':
        query = query.order_by(asc(Product.stock), asc(Product.name))
    elif sort == 'price_desc':
        query = query.order_by(desc(Product.price), asc(Product.name))
    elif sort == 'price_asc':
        query = query.order_by(asc(Product.price), asc(Product.name))
    else:
        query = query.order_by(asc(Product.name))

    db_products = query.all()

    # Monta lista de produtos enriquecida
    items = []
    count_a = 0
    count_b = 0
    count_c = 0
    total_stock_qty = 0.0
    total_stock_value = 0.0
    total_revenue_filtered = 0.0
    total_sold_qty_filtered = 0.0

    for p in db_products:
        s_data = abc_sales_map.get(p.id, {
            'qty_sold': 0.0,
            'revenue': 0.0,
            'margin': float(p.price or 0.0) - float(p.cost or 0.0),
            'margin_pct': ((float(p.price or 0.0) - float(p.cost or 0.0)) / float(p.price) * 100) if (p.price and p.price > 0) else 0.0,
            'class': '-'
        })

        if abc_class and abc_class != 'all':
            if s_data['class'] != abc_class:
                continue

        if s_data['class'] == 'A': count_a += 1
        elif s_data['class'] == 'B': count_b += 1
        elif s_data['class'] == 'C': count_c += 1

        p_stock = float(p.stock or 0.0)
        p_price = float(p.price or 0.0)
        p_cost = float(p.cost or 0.0)
        total_stock_qty += p_stock
        if p_stock > 0:
            total_stock_value += (p_stock * p_price)
        total_revenue_filtered += s_data['revenue']
        total_sold_qty_filtered += s_data['qty_sold']

        p_size = p.size
        p_color = p.color
        if not p_size or not p_color:
            s_det, c_det = parse_product_attributes(p.name)
            p_size = p_size or s_det or 'N/D'
            p_color = p_color or c_det or 'N/D'

        items.append({
            'id': p.id,
            'bling_id': p.bling_id,
            'sku': p.sku or 'S/ Cód',
            'name': p.name,
            'size': p_size,
            'color': p_color,
            'class': s_data['class'],
            'stock': p_stock,
            'qty_sold': s_data['qty_sold'],
            'revenue': s_data['revenue'],
            'price': p_price,
            'cost': p_cost,
            'margin': s_data['margin'],
            'margin_pct': s_data['margin_pct'],
            'status': p.status or 'A'
        })

    if sort == 'sales_desc':
        items.sort(key=lambda x: x['qty_sold'], reverse=True)
    elif sort == 'revenue_desc':
        items.sort(key=lambda x: x['revenue'], reverse=True)

    total_found = len(items)
    avg_price = (sum(i['price'] for i in items) / total_found) if total_found > 0 else 0.0

    return {
        'total_products': Product.query.count(),
        'total_found': total_found,
        'count_a': count_a,
        'count_b': count_b,
        'count_c': count_c,
        'total_stock_qty': total_stock_qty,
        'total_stock_value': total_stock_value,
        'total_revenue': total_revenue_filtered,
        'total_sold_qty': total_sold_qty_filtered,
        'avg_price': avg_price,
        'products': items,
        'abc_products': items
    }

