import polars as pl
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func, or_
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.fashion import ConditionalBag, ProductReturn, SellerAttendance, CustomerSurvey

class FashionBiEngine:
    """
    Motor analítico de Business Intelligence especializado em Varejo de Moda e Customer Success.
    Processa dados com Polars em alta performance com vetorização e lazy evaluation.
    """

    @staticmethod
    def get_filter_options() -> Dict[str, List[str]]:
        """
        Retorna listas de opções dinâmicas para preenchimento dos filtros.
        """
        # Apenas consultores devidamente cadastrados nos pedidos (sem inventar nomes fictícios)
        fictitious = {'Camila Duarte', 'Mariana Rios', 'Beatriz Santos', 'Lucas Mendes', 'Camila Consultora'}
        sellers = [
            r[0] for r in db.session.query(Order.seller_name).filter(
                Order.seller_name.isnot(None), 
                Order.seller_name != '',
                Order.seller_name != 'None'
            ).distinct().all() 
            if r[0] and r[0] not in fictitious
        ]

        categories = [r[0] for r in db.session.query(Product.category).filter(Product.category.isnot(None)).distinct().all() if r[0]]
        if not categories:
            categories = ["Vestidos", "Alfaiataria", "Jeanswear", "Blusas & Camisas", "Conjuntos", "Festas & Noite"]

        reasons = [r[0] for r in db.session.query(ProductReturn.reason).distinct().all() if r[0]]
        if not reasons:
            reasons = ["Modelagem pequena", "Tamanho não serviu", "Defeito de costura / acabamento", "Não gostou do caimento no corpo", "Desistência / Presente repetido"]

        return {
            'sellers': sorted(list(set(sellers))),
            'categories': sorted(list(set(categories))),
            'reasons': sorted(list(set(reasons))),
            'tiers': ['Ativo (< 60d)', 'Atenção (60-90d)', 'Inativo (91-180d)', 'Churn (> 180d)'],
            'abc_classes': ['A', 'B', 'C'],
            'months': [
                {'num': 1, 'name': 'Janeiro'}, {'num': 2, 'name': 'Fevereiro'}, {'num': 3, 'name': 'Março'},
                {'num': 4, 'name': 'Abril'}, {'num': 5, 'name': 'Maio'}, {'num': 6, 'name': 'Junho'},
                {'num': 7, 'name': 'Julho'}, {'num': 8, 'name': 'Agosto'}, {'num': 9, 'name': 'Setembro'},
                {'num': 10, 'name': 'Outubro'}, {'num': 11, 'name': 'Novembro'}, {'num': 12, 'name': 'Dezembro'}
            ]
        }

    @staticmethod
    def _extract_sales_dataframe(
        start_date: date, 
        end_date: date,
        seller: Optional[str] = None,
        category: Optional[str] = None
    ) -> pl.DataFrame:
        """
        Extrai vendas e itens do período em um DataFrame Polars unificado, aplicando filtros opcionais.
        """
        query = (
            db.session.query(
                Order.id.label('order_id'),
                Order.number.label('order_number'),
                Order.order_date.label('order_date'),
                Order.total.label('order_total'),
                Order.seller_name.label('seller_name'),
                Order.customer_id.label('customer_id'),
                Customer.name.label('customer_name'),
                Customer.phone.label('customer_phone'),
                Customer.email.label('customer_email'),
                Customer.city.label('customer_city'),
                Customer.state.label('customer_state'),
                Customer.birth_date.label('customer_birth_date'),
                OrderItem.id.label('item_id'),
                OrderItem.product_id.label('product_id'),
                OrderItem.product_name.label('product_name'),
                OrderItem.sku.label('sku'),
                OrderItem.quantity.label('quantity'),
                OrderItem.unit_price.label('unit_price'),
                OrderItem.total_price.label('total_price'),
                OrderItem.size.label('item_size'),
                OrderItem.color.label('item_color'),
                OrderItem.style.label('item_style'),
                Product.category.label('product_category'),
                Product.size.label('product_size'),
                Product.color.label('product_color'),
                Product.style.label('product_style')
            )
            .join(OrderItem, Order.id == OrderItem.order_id)
            .outerjoin(Customer, Order.customer_id == Customer.id)
            .outerjoin(Product, OrderItem.product_id == Product.id)
            .filter(
                Order.status == 'Atendido',
                Order.order_date >= start_date,
                Order.order_date <= end_date
            )
        )

        if seller and seller != 'all':
            query = query.filter(Order.seller_name == seller)

        if category and category != 'all':
            query = query.filter(Product.category == category)

        rows = query.all()
        if not rows:
            return pl.DataFrame({
                'order_id': pl.Series([], dtype=pl.Int64),
                'order_number': pl.Series([], dtype=pl.Utf8),
                'order_date': pl.Series([], dtype=pl.Date),
                'order_total': pl.Series([], dtype=pl.Float64),
                'seller_name': pl.Series([], dtype=pl.Utf8),
                'customer_id': pl.Series([], dtype=pl.Int64),
                'customer_name': pl.Series([], dtype=pl.Utf8),
                'customer_phone': pl.Series([], dtype=pl.Utf8),
                'customer_email': pl.Series([], dtype=pl.Utf8),
                'customer_city': pl.Series([], dtype=pl.Utf8),
                'customer_state': pl.Series([], dtype=pl.Utf8),
                'customer_birth_date': pl.Series([], dtype=pl.Date),
                'item_id': pl.Series([], dtype=pl.Int64),
                'product_id': pl.Series([], dtype=pl.Int64),
                'product_name': pl.Series([], dtype=pl.Utf8),
                'sku': pl.Series([], dtype=pl.Utf8),
                'quantity': pl.Series([], dtype=pl.Float64),
                'unit_price': pl.Series([], dtype=pl.Float64),
                'total_price': pl.Series([], dtype=pl.Float64),
                'size': pl.Series([], dtype=pl.Utf8),
                'color': pl.Series([], dtype=pl.Utf8),
                'style': pl.Series([], dtype=pl.Utf8),
                'category': pl.Series([], dtype=pl.Utf8)
            })

        data_dict = []
        for r in rows:
            resolved_size = r.item_size or r.product_size or 'M'
            resolved_color = r.item_color or r.product_color or 'Padrão'
            resolved_style = r.item_style or r.product_style or r.product_category or 'Casual'
            resolved_seller = r.seller_name or 'Consultora Loja'
            resolved_category = r.product_category or 'Geral'

            data_dict.append({
                'order_id': r.order_id,
                'order_number': str(r.order_number),
                'order_date': r.order_date,
                'order_total': float(r.order_total or 0.0),
                'seller_name': resolved_seller,
                'customer_id': r.customer_id or 0,
                'customer_name': r.customer_name or 'Consumidor Final',
                'customer_phone': r.customer_phone or '',
                'customer_email': r.customer_email or '',
                'customer_city': r.customer_city or '',
                'customer_state': r.customer_state or '',
                'customer_birth_date': r.customer_birth_date,
                'item_id': r.item_id,
                'product_id': r.product_id or 0,
                'product_name': r.product_name or 'Produto',
                'sku': r.sku or 'SKU-000',
                'quantity': float(r.quantity or 1.0),
                'unit_price': float(r.unit_price or 0.0),
                'total_price': float(r.total_price or 0.0),
                'size': resolved_size,
                'color': resolved_color,
                'style': resolved_style,
                'category': resolved_category
            })

        return pl.DataFrame(data_dict)

    # =========================================================================
    # BLOCO 1: PERFIL E COMPORTAMENTO DE COMPRA
    # =========================================================================

    @classmethod
    def get_customer_purchase_profiles(
        cls, 
        start_date: date, 
        end_date: date,
        seller: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Histórico de Compras por Cliente com cálculo de Moda estatística e distribuições para gráficos.
        """
        df = cls._extract_sales_dataframe(start_date, end_date, seller=seller, category=category)
        if df.is_empty():
            return {
                'profiles': [],
                'charts': {
                    'sizes': {'labels': [], 'data': []},
                    'colors': {'labels': [], 'data': []},
                    'styles': {'labels': [], 'data': []}
                }
            }

        profiles_df = (
            df.lazy()
            .filter(pl.col("customer_id") > 0)
            .group_by(["customer_id", "customer_name", "customer_phone", "customer_city", "customer_state"])
            .agg([
                pl.col("size").mode().first().alias("preferred_size"),
                pl.col("color").mode().first().alias("preferred_color"),
                pl.col("style").mode().first().alias("preferred_style"),
                pl.col("quantity").sum().alias("total_pieces"),
                pl.col("total_price").sum().alias("total_spent"),
                pl.col("order_id").n_unique().alias("orders_count"),
                pl.col("order_date").max().alias("last_purchase_date")
            ])
            .with_columns(
                avg_ticket=(pl.col("total_spent") / pl.col("orders_count")).round(2),
                avg_pieces_per_order=(pl.col("total_pieces") / pl.col("orders_count")).round(1)
            )
            .sort("total_spent", descending=True)
            .collect()
        )

        # Distribuições para gráficos representativos
        size_agg = df.group_by("size").agg(total=pl.col("quantity").sum()).sort("total", descending=True).limit(7)
        color_agg = df.group_by("color").agg(total=pl.col("quantity").sum()).sort("total", descending=True).limit(7)
        style_agg = df.group_by("style").agg(total=pl.col("quantity").sum()).sort("total", descending=True).limit(7)

        return {
            'profiles': profiles_df.to_dicts(),
            'charts': {
                'sizes': {
                    'labels': size_agg["size"].to_list(),
                    'data': [round(float(v), 0) for v in size_agg["total"].to_list()]
                },
                'colors': {
                    'labels': color_agg["color"].to_list(),
                    'data': [round(float(v), 0) for v in color_agg["total"].to_list()]
                },
                'styles': {
                    'labels': style_agg["style"].to_list(),
                    'data': [round(float(v), 0) for v in style_agg["total"].to_list()]
                }
            }
        }

    @classmethod
    def get_customer_abc_curve(
        cls, 
        start_date: date, 
        end_date: date,
        seller: Optional[str] = None,
        abc_class: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Curva ABC de Clientes com regra 80/20, suporte a filtro por classe e dados de gráficos.
        """
        df = cls._extract_sales_dataframe(start_date, end_date, seller=seller)
        empty_summary = {
            'class_a_count': 0, 'class_a_revenue': 0.0, 'class_a_perc': 0.0,
            'class_b_count': 0, 'class_b_revenue': 0.0, 'class_b_perc': 0.0,
            'class_c_count': 0, 'class_c_revenue': 0.0, 'class_c_perc': 0.0,
            'total_revenue': 0.0, 'total_customers': 0
        }
        empty_chart = {
            'labels': ['Classe A (80%)', 'Classe B (15%)', 'Classe C (5%)'],
            'revenue': [0, 0, 0],
            'counts': [0, 0, 0]
        }

        if df.is_empty():
            return {
                'customers': [],
                'summary': empty_summary,
                'chart': empty_chart
            }

        cust_totals = (
            df.lazy()
            .filter(pl.col("customer_id") > 0)
            .group_by(["customer_id", "customer_name", "customer_phone", "customer_city", "customer_state"])
            .agg([
                pl.col("total_price").sum().alias("total_revenue"),
                pl.col("quantity").sum().alias("total_pieces"),
                pl.col("order_id").n_unique().alias("orders_count")
            ])
            .sort("total_revenue", descending=True)
            .collect()
        )

        if cust_totals.is_empty():
            return {
                'customers': [],
                'summary': empty_summary,
                'chart': empty_chart
            }

        total_general = float(cust_totals["total_revenue"].sum())
        if total_general == 0:
            total_general = 1.0

        abc_df = (
            cust_totals.lazy()
            .with_columns(
                cum_revenue=pl.col("total_revenue").cum_sum()
            )
            .with_columns(
                cum_perc=((pl.col("cum_revenue") / pl.lit(total_general)) * 100).round(2),
                revenue_perc=((pl.col("total_revenue") / pl.lit(total_general)) * 100).round(2)
            )
            .with_columns(
                abc_class=pl.when(pl.col("cum_perc") <= 80.0)
                .then(pl.lit("A"))
                .when(pl.col("cum_perc") <= 95.0)
                .then(pl.lit("B"))
                .otherwise(pl.lit("C"))
            )
            .collect()
        )

        summary_a = abc_df.filter(pl.col("abc_class") == "A")
        summary_b = abc_df.filter(pl.col("abc_class") == "B")
        summary_c = abc_df.filter(pl.col("abc_class") == "C")

        rev_a = float(summary_a["total_revenue"].sum() if not summary_a.is_empty() else 0.0)
        rev_b = float(summary_b["total_revenue"].sum() if not summary_b.is_empty() else 0.0)
        rev_c = float(summary_c["total_revenue"].sum() if not summary_c.is_empty() else 0.0)

        summary = {
            'class_a_count': len(summary_a),
            'class_a_revenue': round(rev_a, 2),
            'class_a_perc': round((rev_a / total_general) * 100, 1),
            'class_b_count': len(summary_b),
            'class_b_revenue': round(rev_b, 2),
            'class_b_perc': round((rev_b / total_general) * 100, 1),
            'class_c_count': len(summary_c),
            'class_c_revenue': round(rev_c, 2),
            'class_c_perc': round((rev_c / total_general) * 100, 1),
            'total_revenue': round(total_general, 2),
            'total_customers': len(abc_df)
        }

        chart = {
            'labels': ['Classe A (80%)', 'Classe B (15%)', 'Classe C (5%)'],
            'revenue': [round(rev_a, 2), round(rev_b, 2), round(rev_c, 2)],
            'counts': [len(summary_a), len(summary_b), len(summary_c)]
        }

        # Aplica filtro por classe se requisitado
        filtered_customers = abc_df
        if abc_class and abc_class in ['A', 'B', 'C']:
            filtered_customers = abc_df.filter(pl.col("abc_class") == abc_class)

        return {
            'customers': filtered_customers.to_dicts(),
            'summary': summary,
            'chart': chart
        }

    @classmethod
    def get_birthday_customers(cls, target_month: Optional[int] = None) -> Dict[str, Any]:
        """
        Relatório de Aniversariantes do Mês com filtro e distribuição semanal para gráfico.
        """
        today = date.today()
        month = int(target_month) if target_month and str(target_month).isdigit() else today.month

        customers = Customer.query.filter(Customer.birth_date.isnot(None)).all()
        if not customers:
            return {'customers': [], 'chart': {'labels': [], 'data': []}}

        data = []
        weeks_count = [0, 0, 0, 0, 0] # Dias 1-7, 8-14, 15-21, 22-28, 29-31

        for c in customers:
            bdate = c.birth_date
            if bdate and bdate.month == month:
                try:
                    this_year_birthday = date(today.year, bdate.month, bdate.day)
                    days_diff = (this_year_birthday - today).days
                except ValueError:
                    this_year_birthday = date(today.year, bdate.month, 28)
                    days_diff = (this_year_birthday - today).days

                age = today.year - bdate.year

                # Agrupa na semana do mês para gráfico
                day = bdate.day
                if day <= 7:
                    weeks_count[0] += 1
                elif day <= 14:
                    weeks_count[1] += 1
                elif day <= 21:
                    weeks_count[2] += 1
                elif day <= 28:
                    weeks_count[3] += 1
                else:
                    weeks_count[4] += 1

                data.append({
                    'id': c.id,
                    'name': c.name,
                    'phone': c.phone or '',
                    'email': c.email or '',
                    'city': c.city or '',
                    'state': c.state or '',
                    'birth_date': bdate.strftime('%d/%m/%Y'),
                    'day': bdate.day,
                    'age': age,
                    'days_until': days_diff,
                    'status': 'Hoje!' if days_diff == 0 else (f'Em {days_diff} dias' if days_diff > 0 else f'Passou há {-days_diff} dias'),
                    'preferred_size': c.preferred_size or 'M',
                    'preferred_style': c.preferred_style or 'Casual'
                })

        data.sort(key=lambda x: x['day'])
        return {
            'customers': data,
            'chart': {
                'labels': ['Dias 1 a 7', 'Dias 8 a 14', 'Dias 15 a 21', 'Dias 22 a 28', 'Dias 29 a 31'],
                'data': weeks_count
            }
        }

    # =========================================================================
    # BLOCO 2: MOVIMENTAÇÃO E PREFERÊNCIAS DE MODA
    # =========================================================================

    @classmethod
    def get_conditional_bags_analytics(
        cls, 
        start_date: date, 
        end_date: date,
        seller: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Relatório Estratégico de Malas Condicionais (Consignação no Varejo de Moda).
        Regra de Negócio:
        1. Considera os pedidos que entram como consignado na forma de pagamento (ou observações).
        2. Cruza com os pedidos do mesmo cliente que envolverem as peças que estavam no consignado dele.
        """
        empty_res = {
            'bags': [],
            'total_bags': 0,
            'total_sent': 0,
            'total_invoiced': 0,
            'total_returned': 0,
            'overall_conversion_rate': 0.0,
            'total_invoiced_value': 0.0,
            'total_sent_value': 0.0,
            'sellers_conversion': [],
            'chart': {'labels': [], 'sent': [], 'invoiced': [], 'conv_rate': []}
        }

        # 1. Busca pedidos de consignação no período
        consign_query = Order.query.filter(
            or_(
                func.lower(Order.payment_method).like('%consignad%'),
                func.lower(Order.notes).like('%consignad%'),
                func.lower(Order.channel).like('%consignad%')
            ),
            Order.order_date >= start_date,
            Order.order_date <= end_date
        )

        if seller and seller != 'all':
            consign_query = consign_query.filter(Order.seller_name == seller)

        consign_orders = consign_query.order_by(Order.order_date.desc()).all()

        bag_data = []

        if consign_orders:
            for cord in consign_orders:
                cust = cord.customer
                cust_name = cust.name if cust else 'Cliente Não Informado'
                sent_dt_str = cord.order_date.strftime('%Y-%m-%d') if cord.order_date else ''
                
                # Mapeia itens enviados na consignação com saldo de estoque
                prods_cat = Product.query.all()
                prod_sku_map = {p.sku.strip().upper(): p for p in prods_cat if p.sku}
                prod_name_map = {p.name.strip().upper(): p for p in prods_cat if p.name}

                sent_items = []
                for item in cord.items:
                    prod = item.product
                    if not prod and item.sku:
                        prod = prod_sku_map.get(item.sku.strip().upper())
                    if not prod and item.product_name:
                        prod = prod_name_map.get(item.product_name.strip().upper())

                    stock_val = float(prod.stock or 0.0) if prod else 0.0

                    sent_items.append({
                        'id': item.id,
                        'product_id': item.product_id or (prod.id if prod else None),
                        'sku': (item.sku or (prod.sku if prod else '')).strip().upper(),
                        'name': item.product_name,
                        'size': item.size or (prod.size if prod else ''),
                        'color': item.color or (prod.color if prod else ''),
                        'quantity': float(item.quantity or 1.0),
                        'unit_price': float(item.unit_price or 0.0),
                        'total_price': float(item.total_price or 0.0),
                        'stock': stock_val,
                        'invoiced_qty': 0.0,
                        'returned_qty': 0.0,
                        'status': 'Devolvido ao Estoque'
                    })

                total_pieces_sent = sum(it['quantity'] for it in sent_items)
                total_val_sent = float(cord.total) if cord.total else sum(it['total_price'] for it in sent_items)

                # Busca pedidos do MESMO cliente que envolverem as peças que estavam no consignado
                invoiced_orders_set = set()
                if cord.customer_id:
                    client_orders = Order.query.filter(
                        Order.customer_id == cord.customer_id,
                        Order.id != cord.id,
                        Order.order_date >= cord.order_date,
                        Order.status != 'Cancelado'
                    ).order_by(Order.order_date.asc()).all()

                    for subsequent_order in client_orders:
                        matched_order = False
                        for s_item in subsequent_order.items:
                            s_sku = (s_item.sku or '').strip().upper()
                            s_pid = s_item.product_id
                            s_name = (s_item.product_name or '').strip().lower()
                            s_qty = float(s_item.quantity or 1.0)

                            for sent_it in sent_items:
                                is_match = False
                                if s_sku and sent_it['sku'] and s_sku == sent_it['sku']:
                                    is_match = True
                                elif s_pid and sent_it['product_id'] and s_pid == sent_it['product_id']:
                                    is_match = True
                                elif s_name and sent_it['name'].strip().lower() == s_name:
                                    is_match = True

                                if is_match:
                                    remaining = sent_it['quantity'] - sent_it['invoiced_qty']
                                    if remaining > 0 and s_qty > 0:
                                        alloc = min(remaining, s_qty)
                                        sent_it['invoiced_qty'] += alloc
                                        s_qty -= alloc
                                        matched_order = True
                                        sent_it['status'] = f'Comprado (#{subsequent_order.number})'

                        if matched_order:
                            invoiced_orders_set.add(f"#{subsequent_order.number}")

                # Atualiza peças devolvidas e status individual dos itens
                for sent_it in sent_items:
                    sent_it['returned_qty'] = max(0.0, sent_it['quantity'] - sent_it['invoiced_qty'])

                total_pieces_invoiced = sum(it['invoiced_qty'] for it in sent_items)
                total_pieces_returned = max(0.0, total_pieces_sent - total_pieces_invoiced)
                total_val_invoiced = sum(it['invoiced_qty'] * it['unit_price'] for it in sent_items)

                conv_rate = round((total_pieces_invoiced / total_pieces_sent * 100), 1) if total_pieces_sent > 0 else 0.0

                # Status da mala condicional
                days_since = (date.today() - cord.order_date).days if cord.order_date else 0
                if total_pieces_invoiced >= total_pieces_sent and total_pieces_sent > 0:
                    bag_status = '100% Convertida'
                elif total_pieces_invoiced > 0:
                    bag_status = 'Parcialmente Faturada'
                elif days_since <= 7:
                    bag_status = 'Em Aberto'
                else:
                    bag_status = 'Devolvida Integral'

                if status and status != 'all':
                    status_low = status.lower()
                    if status_low not in bag_status.lower():
                        continue

                inv_orders_list = sorted(list(invoiced_orders_set))
                bag_data.append({
                    'id': cord.id,
                    'order_id': cord.id,
                    'order_number': cord.number,
                    'order_bling_id': cord.bling_id,
                    'bag_code': cord.number if str(cord.number).startswith('CSG') else f"CSG-#{cord.number}",
                    'customer_id': cord.customer_id,
                    'customer_name': cust_name,
                    'seller_name': cord.seller_name or 'Consultor(a)',
                    'items_sent': int(total_pieces_sent),
                    'items_invoiced': int(total_pieces_invoiced),
                    'items_returned': int(total_pieces_returned),
                    'total_sent_value': round(total_val_sent, 2),
                    'total_invoiced_value': round(total_val_invoiced, 2),
                    'conversion_rate': conv_rate,
                    'status': bag_status,
                    'sent_date': sent_dt_str,
                    'invoiced_orders': inv_orders_list,
                    'invoiced_orders_str': ", ".join(inv_orders_list) if inv_orders_list else "Aguardando Venda",
                    'items_detail': sent_items
                })
        else:
            # Fallback de compatibilidade retroativa com ConditionalBag
            query = ConditionalBag.query.filter(
                ConditionalBag.sent_date >= start_date,
                ConditionalBag.sent_date <= end_date
            )
            if seller and seller != 'all':
                query = query.filter(ConditionalBag.seller_name == seller)
            if status and status != 'all':
                query = query.filter(ConditionalBag.status == status)

            legacy_bags = query.all()
            for b in legacy_bags:
                d = b.to_dict()
                # Tenta localizar pedido consignado correspondente
                matched_ord = None
                if b.customer_id:
                    matched_ord = Order.query.filter(
                        Order.customer_id == b.customer_id,
                        Order.order_date == b.sent_date
                    ).first()
                if not matched_ord and b.bag_code:
                    clean_code = b.bag_code.replace('BAG-', '').replace('CSG-', '')
                    matched_ord = Order.query.filter(Order.number.like(f"%{clean_code}%")).first()

                if matched_ord:
                    d['order_id'] = matched_ord.id
                    d['order_number'] = matched_ord.number
                    d['order_bling_id'] = matched_ord.bling_id
                else:
                    d['order_id'] = None
                    d['order_number'] = b.bag_code.replace('BAG-', 'CSG-')
                    d['order_bling_id'] = None

                d['invoiced_orders'] = []
                d['invoiced_orders_str'] = 'Consignado'
                d['items_detail'] = []
                bag_data.append(d)

        if not bag_data:
            return empty_res

        total_sent = sum(b['items_sent'] for b in bag_data)
        total_invoiced = sum(b['items_invoiced'] for b in bag_data)
        total_returned = sum(b['items_returned'] for b in bag_data)
        total_val_sent = sum(b['total_sent_value'] for b in bag_data)
        total_val_invoiced = sum(b['total_invoiced_value'] for b in bag_data)
        overall_conversion = round((total_invoiced / total_sent * 100), 1) if total_sent > 0 else 0.0

        # Performance por vendedora
        df_bags = pl.DataFrame([
            {
                'seller_name': b['seller_name'],
                'items_sent': b['items_sent'],
                'items_invoiced': b['items_invoiced'],
                'total_invoiced_value': b['total_invoiced_value']
            } for b in bag_data
        ])

        sellers_df = (
            df_bags.lazy()
            .group_by("seller_name")
            .agg([
                pl.col("items_sent").sum().alias("sent"),
                pl.col("items_invoiced").sum().alias("invoiced"),
                pl.col("total_invoiced_value").sum().alias("revenue"),
                pl.len().alias("bags_count")
            ])
            .with_columns(
                conv_rate=pl.when(pl.col("sent") > 0)
                .then((pl.col("invoiced") / pl.col("sent") * 100).round(1))
                .otherwise(0.0)
            )
            .sort("conv_rate", descending=True)
            .collect()
        )

        sellers_list = sellers_df.to_dicts()

        chart = {
            'labels': [s['seller_name'] for s in sellers_list],
            'sent': [int(s['sent']) for s in sellers_list],
            'invoiced': [int(s['invoiced']) for s in sellers_list],
            'conv_rate': [float(s['conv_rate']) for s in sellers_list]
        }

        return {
            'bags': bag_data,
            'total_bags': len(bag_data),
            'total_sent': total_sent,
            'total_invoiced': total_invoiced,
            'total_returned': total_returned,
            'overall_conversion_rate': overall_conversion,
            'total_sent_value': round(total_val_sent, 2),
            'total_invoiced_value': round(total_val_invoiced, 2),
            'sellers_conversion': sellers_list,
            'chart': chart
        }

    @classmethod
    def get_top_products_by_category(
        cls, 
        start_date: date, 
        end_date: date,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ranking dos Produtos Mais Vendidos por Categoria (Window Rank) com gráfico comparativo.
        """
        df = cls._extract_sales_dataframe(start_date, end_date, category=category)
        if df.is_empty():
            return {'products': [], 'chart': {'labels': [], 'revenues': [], 'pieces': []}}

        ranked_df = (
            df.lazy()
            .group_by(["category", "sku", "product_name"])
            .agg([
                pl.col("quantity").sum().alias("total_quantity"),
                pl.col("total_price").sum().alias("total_revenue")
            ])
            .with_columns(
                rank_in_category=pl.col("total_revenue").rank(descending=True).over("category").cast(pl.Int32)
            )
            .filter(pl.col("rank_in_category") <= 5)
            .sort(["category", "rank_in_category"])
            .collect()
        )

        ranked_list = ranked_df.to_dicts()

        # Enriquece ranking com saldo de estoque real do catálogo
        all_prods = Product.query.all()
        p_by_sku = {p.sku.strip().upper(): p for p in all_prods if p.sku}
        p_by_name = {p.name.strip().upper(): p for p in all_prods if p.name}
        for item in ranked_list:
            sku = (item.get('sku') or '').strip().upper()
            pname = (item.get('product_name') or '').strip().upper()
            p = p_by_sku.get(sku) or p_by_name.get(pname)
            item['stock'] = float(p.stock or 0.0) if p else 0.0

        # Top 8 para gráfico horizontal
        top_chart = ranked_df.sort("total_revenue", descending=True).limit(8)
        chart = {
            'labels': [p['product_name'][:22] for p in top_chart.to_dicts()],
            'revenues': [round(float(p['total_revenue']), 2) for p in top_chart.to_dicts()],
            'pieces': [int(p['total_quantity']) for p in top_chart.to_dicts()]
        }

        return {
            'products': ranked_list,
            'chart': chart
        }

    @classmethod
    def get_returns_and_exchanges_report(
        cls, 
        start_date: date, 
        end_date: date,
        seller: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Relatório de Trocas e Devoluções com filtro e gráfico de rosca de motivos.
        """
        query = ProductReturn.query.filter(
            ProductReturn.return_date >= start_date,
            ProductReturn.return_date <= end_date
        )

        if seller and seller != 'all':
            query = query.filter(ProductReturn.seller_name == seller)

        if reason and reason != 'all':
            query = query.filter(ProductReturn.reason == reason)

        returns = query.all()
        sales_df = cls._extract_sales_dataframe(start_date, end_date, seller=seller)

        empty_res = {
            'returns': [],
            'total_returns': 0,
            'total_pieces_returned': 0.0,
            'overall_return_rate': 0.0,
            'reasons_distribution': [],
            'sku_return_rates': [],
            'chart': {'labels': [], 'pieces': [], 'percentages': []}
        }

        if not returns:
            return empty_res

        returns_data = []
        all_prods_ret = Product.query.all()
        ret_by_sku = {p.sku.strip().upper(): p for p in all_prods_ret if p.sku}
        ret_by_name = {p.name.strip().upper(): p for p in all_prods_ret if p.name}

        for r in returns:
            rd = r.to_dict()
            if not rd.get('stock') or rd.get('stock') == 0.0:
                sku_clean = (r.sku or '').strip().upper()
                name_clean = (r.product_name or '').strip().upper()
                p_match = ret_by_sku.get(sku_clean) or ret_by_name.get(name_clean)
                if p_match:
                    rd['stock'] = float(p_match.stock or 0.0)
            returns_data.append(rd)

        ret_df = pl.DataFrame(returns_data)

        total_pieces_returned = float(ret_df["quantity"].sum())
        total_pieces_sold = float(sales_df["quantity"].sum()) if not sales_df.is_empty() else 0.0
        overall_rate = round((total_pieces_returned / total_pieces_sold * 100), 2) if total_pieces_sold > 0 else 0.0

        reasons_df = (
            ret_df.lazy()
            .group_by("reason")
            .agg(
                count=pl.len(),
                pieces=pl.col("quantity").sum()
            )
            .with_columns(
                percentage=(pl.col("pieces") / pl.lit(total_pieces_returned if total_pieces_returned > 0 else 1.0) * 100).round(1)
            )
            .sort("pieces", descending=True)
            .collect()
        )

        reasons_list = reasons_df.to_dicts()

        chart = {
            'labels': [r['reason'] for r in reasons_list],
            'pieces': [int(r['pieces']) for r in reasons_list],
            'percentages': [float(r['percentage']) for r in reasons_list]
        }

        ret_sku_df = ret_df.group_by(["sku", "product_name"]).agg(returned_qty=pl.col("quantity").sum())

        if not sales_df.is_empty():
            sold_sku_df = sales_df.group_by(["sku", "product_name"]).agg(sold_qty=pl.col("quantity").sum())
            merged_sku = ret_sku_df.join(sold_sku_df, on=["sku", "product_name"], how="left").fill_null(0.0)
            merged_sku = (
                merged_sku.lazy()
                .with_columns(
                    return_rate=pl.when(pl.col("sold_qty") > 0)
                    .then((pl.col("returned_qty") / pl.col("sold_qty") * 100).round(1))
                    .otherwise(100.0)
                )
                .sort("returned_qty", descending=True)
                .collect()
            )
            sku_return_rates = merged_sku.to_dicts()
        else:
            sku_return_rates = ret_sku_df.to_dicts()

        return {
            'returns': returns_data,
            'total_returns': len(returns),
            'total_pieces_returned': total_pieces_returned,
            'overall_return_rate': overall_rate,
            'reasons_distribution': reasons_list,
            'sku_return_rates': sku_return_rates,
            'chart': chart
        }

    # =========================================================================
    # BLOCO 3: DESEMPENHO DO ATENDIMENTO (KPIS)
    # =========================================================================

    @classmethod
    def get_service_performance_kpis(
        cls, 
        start_date: date, 
        end_date: date,
        seller: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Desempenho da equipe comercial com gráficos de P.A., Conversão e Ticket Médio.
        """
        sales_df = cls._extract_sales_dataframe(start_date, end_date, seller=seller)

        att_query = SellerAttendance.query.filter(
            SellerAttendance.attendance_date >= start_date,
            SellerAttendance.attendance_date <= end_date
        )
        if seller and seller != 'all':
            att_query = att_query.filter(SellerAttendance.seller_name == seller)

        attendances = att_query.all()
        att_df = pl.DataFrame([a.to_dict() for a in attendances]) if attendances else pl.DataFrame({
            'seller_name': pl.Series([], dtype=pl.Utf8),
            'converted': pl.Series([], dtype=pl.Boolean),
            'channel': pl.Series([], dtype=pl.Utf8)
        })

        if sales_df.is_empty():
            return {
                'store_pa': 0.0,
                'store_ticket': 0.0,
                'store_conversion': 0.0,
                'sellers_kpis': [],
                'customer_tickets': [],
                'charts': {
                    'pa': {'labels': [], 'data': [], 'benchmark': 0.0},
                    'conversion': {'labels': [], 'rates': [], 'tickets': []},
                    'top_tickets': {'labels': [], 'data': []}
                }
            }

        seller_sales = (
            sales_df.lazy()
            .group_by("seller_name")
            .agg([
                pl.col("quantity").sum().alias("total_pieces"),
                pl.col("total_price").sum().alias("total_revenue"),
                pl.col("order_id").n_unique().alias("orders_count")
            ])
            .with_columns(
                pa=(pl.col("total_pieces") / pl.col("orders_count")).round(2),
                ticket_medio=(pl.col("total_revenue") / pl.col("orders_count")).round(2)
            )
            .collect()
        )

        if not att_df.is_empty():
            att_summary = (
                att_df.lazy()
                .group_by("seller_name")
                .agg([
                    pl.len().alias("total_attendances"),
                    pl.col("converted").filter(pl.col("converted") == True).len().alias("converted_attendances")
                ])
                .with_columns(
                    conversion_rate=(pl.col("converted_attendances") / pl.col("total_attendances") * 100).round(1)
                )
                .collect()
            )
            sellers_merged = seller_sales.join(att_summary, on="seller_name", how="full").fill_null(0)
            if "conversion_rate" not in sellers_merged.columns:
                sellers_merged = sellers_merged.with_columns(conversion_rate=pl.lit(0.0))
        else:
            sellers_merged = seller_sales.with_columns(
                total_attendances=pl.col("orders_count"),
                converted_attendances=pl.col("orders_count"),
                conversion_rate=pl.lit(100.0)
            )

        sellers_kpis = sellers_merged.sort("total_revenue", descending=True).to_dicts()

        tot_pieces = float(sales_df["quantity"].sum())
        tot_orders = int(sales_df["order_id"].n_unique())
        tot_revenue = float(sales_df["total_price"].sum())

        store_pa = round(tot_pieces / tot_orders, 2) if tot_orders > 0 else 0.0
        store_ticket = round(tot_revenue / tot_orders, 2) if tot_orders > 0 else 0.0

        total_att = len(attendances)
        conv_att = sum(1 for a in attendances if a.converted)
        store_conv = round(conv_att / total_att * 100, 1) if total_att > 0 else 0.0

        cust_tickets = (
            sales_df.lazy()
            .filter(pl.col("customer_id") > 0)
            .group_by(["customer_id", "customer_name"])
            .agg([
                pl.col("total_price").sum().alias("revenue"),
                pl.col("order_id").n_unique().alias("orders")
            ])
            .with_columns(
                ticket=(pl.col("revenue") / pl.col("orders")).round(2)
            )
            .sort("ticket", descending=True)
            .limit(8)
            .collect()
            .to_dicts()
        )

        charts = {
            'pa': {
                'labels': [s['seller_name'] for s in sellers_kpis],
                'data': [float(s['pa']) for s in sellers_kpis],
                'benchmark': store_pa
            },
            'conversion': {
                'labels': [s['seller_name'] for s in sellers_kpis],
                'rates': [float(s['conversion_rate']) for s in sellers_kpis],
                'tickets': [float(s['ticket_medio']) for s in sellers_kpis]
            },
            'top_tickets': {
                'labels': [c['customer_name'][:18] for c in cust_tickets],
                'data': [float(c['ticket']) for c in cust_tickets]
            }
        }

        return {
            'store_pa': store_pa,
            'store_ticket': store_ticket,
            'store_conversion': store_conv,
            'sellers_kpis': sellers_kpis,
            'customer_tickets': cust_tickets,
            'charts': charts
        }

    # =========================================================================
    # BLOCO 4: RELACIONAMENTO E FIDELIZAÇÃO (CRM)
    # =========================================================================

    @classmethod
    def get_inactive_customers_report(
        cls, 
        reference_date: Optional[date] = None,
        tier_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Relatório de Inatividade e Recência com filtro de faixa e gráficos representativos.
        """
        ref_date = reference_date or date.today()

        query = (
            db.session.query(
                Order.customer_id,
                Customer.name.label('customer_name'),
                Customer.phone.label('customer_phone'),
                Customer.email.label('customer_email'),
                Customer.city.label('customer_city'),
                Customer.state.label('customer_state'),
                Customer.preferred_size,
                Customer.preferred_style,
                func.max(Order.order_date).label('last_purchase'),
                func.count(Order.id).label('total_orders'),
                func.sum(Order.total).label('lifetime_value')
            )
            .join(Customer, Order.customer_id == Customer.id)
            .filter(Order.status == 'Atendido')
            .group_by(Order.customer_id, Customer.name, Customer.phone, Customer.email, Customer.city, Customer.state, Customer.preferred_size, Customer.preferred_style)
        )

        rows = query.all()
        empty_res = {
            'active_count': 0, 'warning_count': 0, 'inactive_count': 0, 'churn_count': 0,
            'customers': [],
            'chart': {'labels': [], 'counts': [], 'ltv': []}
        }

        if not rows:
            return empty_res

        data = []
        ltv_by_tier = {'Ativo': 0.0, 'Atenção': 0.0, 'Inativo': 0.0, 'Churn': 0.0}

        for r in rows:
            last_dt = r.last_purchase
            days_inactive = (ref_date - last_dt).days if last_dt else 999
            val = float(r.lifetime_value or 0.0)

            if days_inactive < 60:
                tier = 'Ativo (< 60d)'
                ltv_by_tier['Ativo'] += val
            elif days_inactive <= 90:
                tier = 'Atenção (60-90d)'
                ltv_by_tier['Atenção'] += val
            elif days_inactive <= 180:
                tier = 'Inativo (91-180d)'
                ltv_by_tier['Inativo'] += val
            else:
                tier = 'Churn (> 180d)'
                ltv_by_tier['Churn'] += val

            data.append({
                'customer_id': r.customer_id,
                'customer_name': r.customer_name,
                'customer_phone': r.customer_phone or '',
                'customer_email': r.customer_email or '',
                'location': f"{r.customer_city or ''}/{r.customer_state or ''}",
                'last_purchase': last_dt.strftime('%d/%m/%Y') if last_dt else '-',
                'days_inactive': days_inactive,
                'tier': tier,
                'total_orders': r.total_orders,
                'lifetime_value': round(val, 2),
                'preferred_size': r.preferred_size or 'M',
                'preferred_style': r.preferred_style or 'Casual'
            })

        df_inact = pl.DataFrame(data)

        active_count = len(df_inact.filter(pl.col("days_inactive") < 60))
        warning_count = len(df_inact.filter((pl.col("days_inactive") >= 60) & (pl.col("days_inactive") <= 90)))
        inactive_count = len(df_inact.filter((pl.col("days_inactive") > 90) & (pl.col("days_inactive") <= 180)))
        churn_count = len(df_inact.filter(pl.col("days_inactive") > 180))

        # Filtro opcional por faixa
        filtered_df = df_inact
        if tier_filter and tier_filter != 'all':
            filtered_df = df_inact.filter(pl.col("tier") == tier_filter)

        sorted_customers = filtered_df.sort("days_inactive", descending=True).to_dicts()

        chart = {
            'labels': ['Ativo (< 60d)', 'Atenção (60-90d)', 'Inativo (91-180d)', 'Churn (> 180d)'],
            'counts': [active_count, warning_count, inactive_count, churn_count],
            'ltv': [round(ltv_by_tier['Ativo'], 2), round(ltv_by_tier['Atenção'], 2), round(ltv_by_tier['Inativo'], 2), round(ltv_by_tier['Churn'], 2)]
        }

        return {
            'active_count': active_count,
            'warning_count': warning_count,
            'inactive_count': inactive_count,
            'churn_count': churn_count,
            'total_analyzed': len(data),
            'customers': sorted_customers,
            'chart': chart
        }

    @classmethod
    def get_repurchase_cohort(cls) -> Dict[str, Any]:
        """
        Análise de Recompra e Retenção por Safra (Cohort Analysis) com gráfico de linha de retenção.
        """
        orders = (
            db.session.query(Order.customer_id, Order.order_date)
            .filter(Order.status == 'Atendido', Order.customer_id.isnot(None))
            .all()
        )

        if not orders:
            return {'cohort_months': [], 'matrix': [], 'chart': {'labels': [], 'datasets': []}}

        df_orders = pl.DataFrame([
            {'customer_id': o[0], 'order_date': o[1]}
            for o in orders
        ])

        df_orders = df_orders.with_columns(
            order_month=pl.col("order_date").dt.strftime("%Y-%m")
        )

        first_purchases = (
            df_orders.group_by("customer_id")
            .agg(first_month=pl.col("order_month").min())
        )

        joined = df_orders.join(first_purchases, on="customer_id")

        cohort_raw = (
            joined.group_by(["first_month", "order_month"])
            .agg(customers_active=pl.col("customer_id").n_unique())
            .sort(["first_month", "order_month"])
        )

        safras = sorted(cohort_raw["first_month"].unique().to_list())
        matrix = []

        chart_labels = []
        chart_datasets = []

        for safra in safras:
            safra_df = cohort_raw.filter(pl.col("first_month") == safra)
            initial_count_row = safra_df.filter(pl.col("order_month") == safra)
            initial_count = int(initial_count_row["customers_active"][0]) if not initial_count_row.is_empty() else 1

            retention_by_period = {}
            percentages = []
            months_list = []

            for row in safra_df.to_dicts():
                mes_ped = row["order_month"]
                active = row["customers_active"]
                perc = round((active / initial_count) * 100, 1)
                retention_by_period[mes_ped] = {
                    'count': active,
                    'percentage': perc
                }
                percentages.append(perc)
                months_list.append(mes_ped)

            if not chart_labels and months_list:
                chart_labels = months_list

            chart_datasets.append({
                'label': f'Safra {safra}',
                'data': percentages
            })

            matrix.append({
                'cohort': safra,
                'initial_size': initial_count,
                'retention': retention_by_period
            })

        return {
            'cohort_months': safras,
            'matrix': matrix,
            'chart': {
                'labels': chart_labels or safras,
                'datasets': chart_datasets
            }
        }

    @classmethod
    def get_satisfaction_metrics(
        cls, 
        start_date: date, 
        end_date: date,
        seller: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pesquisas de Satisfação NPS e CSAT com gráfico de rosca de distribuição.
        """
        query = CustomerSurvey.query.filter(
            CustomerSurvey.survey_date >= start_date,
            CustomerSurvey.survey_date <= end_date
        )

        if seller and seller != 'all':
            query = query.filter(CustomerSurvey.seller_name == seller)

        surveys = query.all()

        empty_res = {
            'total_responses': 0,
            'nps_score': 0,
            'csat_score': 0.0,
            'promoters_count': 0,
            'passives_count': 0,
            'detractors_count': 0,
            'promoters_perc': 0.0,
            'passives_perc': 0.0,
            'detractors_perc': 0.0,
            'surveys': [],
            'chart': {'labels': ['Promotores (9-10)', 'Neutros (7-8)', 'Detratores (0-6)'], 'data': [0, 0, 0]}
        }

        if not surveys:
            return empty_res

        surv_data = [s.to_dict() for s in surveys]
        df_surv = pl.DataFrame(surv_data)

        total = len(surveys)
        promoters = len(df_surv.filter(pl.col("nps_score") >= 9))
        passives = len(df_surv.filter((pl.col("nps_score") >= 7) & (pl.col("nps_score") <= 8)))
        detractors = len(df_surv.filter(pl.col("nps_score") <= 6))

        prom_perc = round((promoters / total) * 100, 1)
        pass_perc = round((passives / total) * 100, 1)
        detr_perc = round((detractors / total) * 100, 1)

        nps_score = round(prom_perc - detr_perc, 1)
        csat_avg = round(float(df_surv["csat_score"].mean()), 2)

        chart = {
            'labels': ['Promotores (9-10)', 'Neutros (7-8)', 'Detratores (0-6)'],
            'data': [promoters, passives, detractors]
        }

        return {
            'total_responses': total,
            'nps_score': nps_score,
            'csat_score': csat_avg,
            'promoters_count': promoters,
            'passives_count': passives,
            'detractors_count': detractors,
            'promoters_perc': prom_perc,
            'passives_perc': pass_perc,
            'detractors_perc': detr_perc,
            'surveys': surv_data[:20],
            'chart': chart
        }
