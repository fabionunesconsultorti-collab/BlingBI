from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, and_, or_
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.financial import FinancialEntry

class BiAnalytics:
    @staticmethod
    def parse_date_filter(period='last_30_days', start_str=None, end_str=None):
        today = date.today()
        if period == 'today':
            return today, today
        elif period == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif period == 'last_7_days':
            return today - timedelta(days=7), today
        elif period in ['last_30_days', 'month']:
            return today - timedelta(days=30), today
        elif period in ['last_90_days', 'quarter']:
            return today - timedelta(days=90), today
        elif period in ['last_180_days', 'semester']:
            return today - timedelta(days=180), today
        elif period in ['last_365_days', 'year']:
            return today - timedelta(days=365), today
        elif period == 'this_month':
            start = today.replace(day=1)
            return start, today
        elif period == 'last_month':
            first_of_this_month = today.replace(day=1)
            last_day_prev_month = first_of_this_month - timedelta(days=1)
            start_prev_month = last_day_prev_month.replace(day=1)
            return start_prev_month, last_day_prev_month
        elif period == 'all':
            return date(2020, 1, 1), today
        elif period == 'custom' and start_str and end_str:
            try:
                start = datetime.strptime(start_str, '%Y-%m-%d').date()
                end = datetime.strptime(end_str, '%Y-%m-%d').date()
                return start, end
            except ValueError:
                return today - timedelta(days=30), today
        return today - timedelta(days=30), today

    @staticmethod
    def get_dashboard_metrics(start_date, end_date):
        # 1. Total faturado (apenas pedidos Atendidos)
        sales_query = db.session.query(
            func.coalesce(func.sum(Order.total), 0.0),
            func.count(Order.id)
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).first()

        total_revenue = float(sales_query[0])
        orders_count = int(sales_query[1])
        ticket_medio = total_revenue / orders_count if orders_count > 0 else 0.0

        # 2. Clientes ativos e novos
        customers_count = Customer.query.count()

        # 3. Financeiro
        receivables_pending = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'RECEBER',
            FinancialEntry.status.in_(['Pendente', 'Atrasado']),
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar() or 0.0

        payables_pending = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'PAGAR',
            FinancialEntry.status.in_(['Pendente', 'Atrasado']),
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar() or 0.0

        # 4. Evolução temporal (gráfico diário)
        daily_sales = db.session.query(
            Order.order_date,
            func.sum(Order.total).label('daily_total'),
            func.count(Order.id).label('daily_orders')
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).group_by(Order.order_date).order_by(Order.order_date).all()

        labels = [item.order_date.strftime('%d/%m') for item in daily_sales]
        chart_revenue = [round(float(item.daily_total), 2) for item in daily_sales]
        chart_orders = [int(item.daily_orders) for item in daily_sales]

        # 5. Vendas por Canal (Marketplaces / Lojas)
        channel_data = db.session.query(
            Order.channel,
            func.sum(Order.total).label('channel_total')
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).group_by(Order.channel).order_by(desc('channel_total')).all()

        channels_labels = [c[0] for c in channel_data]
        channels_values = [round(float(c[1]), 2) for c in channel_data]

        # 6. Top 5 Produtos
        top_products = db.session.query(
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label('qty_sold'),
            func.sum(OrderItem.total_price).label('revenue_sold')
        ).join(Order, OrderItem.order_id == Order.id).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).group_by(OrderItem.product_name).order_by(desc('revenue_sold')).limit(5).all()

        top_prod_list = [
            {'name': p[0], 'qty': int(p[1]), 'revenue': float(p[2])}
            for p in top_products
        ]

        # 7. Pedidos Recentes
        recent_orders = Order.query.order_by(desc(Order.order_date), desc(Order.id)).limit(6).all()

        return {
            'total_revenue': total_revenue,
            'orders_count': orders_count,
            'ticket_medio': ticket_medio,
            'customers_count': customers_count,
            'receivables_pending': float(receivables_pending),
            'payables_pending': float(payables_pending),
            'chart_labels': labels,
            'chart_revenue': chart_revenue,
            'chart_orders': chart_orders,
            'channels_labels': channels_labels,
            'channels_values': channels_values,
            'top_products': top_prod_list,
            'recent_orders': [o.to_dict() for o in recent_orders]
        }

    @staticmethod
    def get_sales_analytics(start_date, end_date, channel=None, status=None, search=None):
        query = Order.query.filter(Order.order_date >= start_date, Order.order_date <= end_date)
        if channel and channel != 'all':
            query = query.filter(Order.channel == channel)
        if status and status != 'all':
            query = query.filter(Order.status == status)

        if search and search.strip():
            s = search.strip()
            digits = "".join(c for c in s if c.isdigit())
            clean_doc_col = func.replace(func.replace(func.replace(Customer.document, '.', ''), '-', ''), '/', '')
            conditions = [
                Order.number.ilike(f"%{s}%"),
                Customer.name.ilike(f"%{s}%"),
                Customer.document.ilike(f"%{s}%"),
                clean_doc_col.ilike(f"%{s}%")
            ]
            if len(digits) >= 3:
                conditions.append(Order.number.ilike(f"%{digits}%"))
                conditions.append(Customer.document.ilike(f"%{digits}%"))
                conditions.append(clean_doc_col.ilike(f"%{digits}%"))
            query = query.outerjoin(Customer, Order.customer_id == Customer.id).filter(or_(*conditions))

        orders = query.order_by(desc(Order.order_date)).all()

        total_orders = len(orders)
        attended_orders = [o for o in orders if o.status == 'Atendido']
        attended_count = len(attended_orders)
        total_gross = sum(o.total for o in attended_orders)
        total_discounts = sum(o.discount for o in attended_orders)
        total_shipping = sum(o.shipping for o in attended_orders)
        avg_ticket = (total_gross / attended_count) if attended_count > 0 else 0.0

        # Status count
        status_counts = {}
        for o in orders:
            status_counts[o.status] = status_counts.get(o.status, 0) + 1

        # Vendas por canal
        channel_sales = {}
        for o in orders:
            if o.status == 'Atendido':
                channel_sales[o.channel] = channel_sales.get(o.channel, 0.0) + o.total

        # Vendas por UF (Cliente)
        uf_sales = {}
        for o in orders:
            if o.status == 'Atendido' and o.customer and o.customer.state:
                uf = o.customer.state.upper()
                uf_sales[uf] = uf_sales.get(uf, 0.0) + o.total

        sorted_uf = sorted(uf_sales.items(), key=lambda x: x[1], reverse=True)

        return {
            'orders': [o.to_dict() for o in orders],
            'total_orders': total_orders,
            'attended_count': attended_count,
            'total_gross': total_gross,
            'total_discounts': total_discounts,
            'total_shipping': total_shipping,
            'avg_ticket': avg_ticket,
            'status_counts': status_counts,
            'channel_sales': channel_sales,
            'uf_sales': sorted_uf
        }

    @staticmethod
    def get_products_analytics(start_date, end_date):
        # Todos os produtos cadastrados
        products = Product.query.all()

        # Vendas por produto no período
        sold_items = db.session.query(
            OrderItem.product_id,
            OrderItem.product_name,
            OrderItem.sku,
            func.sum(OrderItem.quantity).label('qty_sold'),
            func.sum(OrderItem.total_price).label('revenue_sold'),
            func.sum(OrderItem.cost_price * OrderItem.quantity).label('total_cost')
        ).join(Order, OrderItem.order_id == Order.id).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).group_by(OrderItem.product_id, OrderItem.product_name, OrderItem.sku).order_by(desc('revenue_sold')).all()

        total_product_revenue = sum(float(item.revenue_sold or 0.0) for item in sold_items)

        # Cálculo da Curva ABC (Pareto)
        # Classe A: até 80% do faturamento acumulado
        # Classe B: 80% a 95%
        # Classe C: 95% a 100%
        abc_products = []
        accumulated_revenue = 0.0

        for item in sold_items:
            rev = float(item.revenue_sold or 0.0)
            cost = float(item.total_cost or 0.0)
            margin = rev - cost
            margin_pct = (margin / rev * 100) if rev > 0 else 0.0

            accumulated_revenue += rev
            accumulated_pct = (accumulated_revenue / total_product_revenue * 100) if total_product_revenue > 0 else 100.0

            if accumulated_pct <= 80.0:
                classe = 'A'
            elif accumulated_pct <= 95.0:
                classe = 'B'
            else:
                classe = 'C'

            # Pega estoque atual do produto
            prod_db = db.session.get(Product, item.product_id) if item.product_id else None
            stock_current = prod_db.stock if prod_db else 0.0

            abc_products.append({
                'id': item.product_id,
                'name': item.product_name,
                'sku': item.sku or 'N/A',
                'qty_sold': float(item.qty_sold or 0),
                'revenue': rev,
                'cost': cost,
                'margin': margin,
                'margin_pct': margin_pct,
                'accumulated_pct': accumulated_pct,
                'class': classe,
                'stock': stock_current
            })

        # Contagem de classes ABC
        count_a = sum(1 for p in abc_products if p['class'] == 'A')
        count_b = sum(1 for p in abc_products if p['class'] == 'B')
        count_c = sum(1 for p in abc_products if p['class'] == 'C')

        # Alertas de estoque crítico (menor ou igual a 5 unidades)
        low_stock = [p.to_dict() for p in products if p.stock <= 5]

        return {
            'abc_products': abc_products,
            'total_products': len(products),
            'total_revenue': total_product_revenue,
            'count_a': count_a,
            'count_b': count_b,
            'count_c': count_c,
            'low_stock': low_stock
        }

    @staticmethod
    def get_customers_analytics(start_date, end_date):
        total_customers = Customer.query.count()

        # Clientes com pedidos no período
        cust_orders = db.session.query(
            Customer.id,
            Customer.name,
            Customer.document,
            Customer.city,
            Customer.state,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total).label('total_spent')
        ).join(Order, Customer.id == Order.customer_id).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).group_by(Customer.id).order_by(desc('total_spent')).all()

        active_customers_count = len(cust_orders)
        top_customers = [
            {
                'id': c.id,
                'name': c.name,
                'doc': c.document or 'N/A',
                'city': c.city or '',
                'state': c.state or '',
                'orders': int(c.order_count),
                'total_spent': float(c.total_spent)
            }
            for c in cust_orders[:15]
        ]

        # Clientes recorrentes (mais de 1 pedido)
        recurring = sum(1 for c in cust_orders if c.order_count > 1)
        recurrence_rate = (recurring / active_customers_count * 100) if active_customers_count > 0 else 0.0

        # Distribuição geográfica
        states_data = db.session.query(
            Customer.state,
            func.count(Customer.id)
        ).filter(Customer.state.isnot(None)).group_by(Customer.state).order_by(desc(func.count(Customer.id))).all()

        return {
            'total_customers': total_customers,
            'active_customers_count': active_customers_count,
            'recurring_customers': recurring,
            'recurrence_rate': recurrence_rate,
            'top_customers': top_customers,
            'states_distribution': [{'state': s[0], 'count': s[1]} for s in states_data]
        }

    @staticmethod
    def get_finance_analytics(start_date, end_date):
        # 1. Total Contas a Receber
        rec_paid = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'RECEBER',
            FinancialEntry.status == 'Pago',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar()

        rec_pending = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'RECEBER',
            FinancialEntry.status == 'Pendente',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar()

        rec_overdue = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'RECEBER',
            FinancialEntry.status == 'Atrasado',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar()

        total_receivable = float(rec_paid + rec_pending + rec_overdue)

        # 2. Total Contas a Pagar
        pay_paid = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'PAGAR',
            FinancialEntry.status == 'Pago',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar()

        pay_pending = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'PAGAR',
            FinancialEntry.status == 'Pendente',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar()

        pay_overdue = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0)).filter(
            FinancialEntry.entry_type == 'PAGAR',
            FinancialEntry.status == 'Atrasado',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).scalar()

        total_payable = float(pay_paid + pay_pending + pay_overdue)

        # Saldo projetado e realizado
        net_realized = float(rec_paid - pay_paid)
        net_projected = float(total_receivable - total_payable)

        # Inadimplência
        default_rate = (float(rec_overdue) / total_receivable * 100) if total_receivable > 0 else 0.0

        # DRE Gerencial Sintético
        gross_sales = db.session.query(func.coalesce(func.sum(Order.total), 0.0)).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).scalar()

        canceled_sales = db.session.query(func.coalesce(func.sum(Order.total), 0.0)).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Cancelado'
        ).scalar()

        net_sales = float(gross_sales - canceled_sales)

        # CMV Real apurado a partir dos itens dos pedidos atendidos
        real_cmv = db.session.query(
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.cost_price), 0.0)
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).scalar() or 0.0

        cpv_real = float(real_cmv)
        # Fallback apenas se não houver custos cadastrados e houver vendas
        if cpv_real == 0.0 and net_sales > 0:
            cpv_real = net_sales * 0.52

        gross_profit = net_sales - cpv_real

        # Despesas Operacionais Reais (Contas a Pagar do período não canceladas)
        real_expenses = db.session.query(
            func.coalesce(func.sum(FinancialEntry.amount), 0.0)
        ).filter(
            FinancialEntry.entry_type == 'PAGAR',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date,
            FinancialEntry.status != 'Cancelado'
        ).scalar() or 0.0

        operating_expenses = float(real_expenses)
        operating_result = gross_profit - operating_expenses

        dre = {
            'gross_revenue': float(gross_sales),
            'deductions': float(canceled_sales),
            'net_revenue': net_sales,
            'cpv': cpv_real,
            'gross_profit': gross_profit,
            'operating_expenses': operating_expenses,
            'net_profit': operating_result,
            'net_margin': (operating_result / net_sales * 100) if net_sales > 0 else 0.0
        }

        # Lista de lançamentos
        entries = FinancialEntry.query.filter(
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date
        ).order_by(FinancialEntry.due_date.desc()).all()

        return {
            'rec_paid': float(rec_paid),
            'rec_pending': float(rec_pending),
            'rec_overdue': float(rec_overdue),
            'total_receivable': total_receivable,
            'pay_paid': float(pay_paid),
            'pay_pending': float(pay_pending),
            'pay_overdue': float(pay_overdue),
            'total_payable': total_payable,
            'net_realized': net_realized,
            'net_projected': net_projected,
            'default_rate': default_rate,
            'dre': dre,
            'entries': [e.to_dict() for e in entries]
        }
