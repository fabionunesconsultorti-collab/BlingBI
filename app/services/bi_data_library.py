import polars as pl
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, and_, or_, desc
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.financial import FinancialEntry
from app.models.fashion import ConditionalBag, ProductReturn, SellerAttendance, CustomerSurvey

class BiDataLibrary:
    """
    Biblioteca Central de Dados Analíticos (BI Data Library & Data Access Layer).
    
    Isola completamente os motores e módulos de relatórios do banco de dados relacional
    e dos processos de sincronização/integração com o Bling ERP.
    Fornece consultas padronizadas e conversões eficientes para Polars DataFrames.
    """

    # -------------------------------------------------------------------------
    # 1. UTILITÁRIOS TEMPORAIS E FILTROS
    # -------------------------------------------------------------------------
    @staticmethod
    def parse_date_filter(period: str = 'last_30_days', start_str: Optional[str] = None, end_str: Optional[str] = None) -> Tuple[date, date]:
        """Converte termos amigáveis de período em tupla (start_date, end_date)."""
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

    # -------------------------------------------------------------------------
    # 2. VENDAS, PEDIDOS E ITENS
    # -------------------------------------------------------------------------
    @staticmethod
    def get_orders_df(
        start_date: date,
        end_date: date,
        channel: Optional[str] = None,
        status: Optional[str] = None
    ) -> pl.DataFrame:
        """
        Retorna DataFrame Polars com todos os pedidos dentro do período.
        Colunas: id, bling_id, order_number, order_date, customer_id, customer_name,
                 total, discount, shipping, net_amount, status, channel, seller
        """
        query = db.session.query(
            Order.id,
            Order.bling_id,
            Order.number.label('order_number'),
            Order.order_date,
            Order.customer_id,
            Customer.name.label('customer_name'),
            Order.total,
            Order.discount,
            Order.shipping,
            Order.status,
            Order.channel,
            Order.seller_name
        ).outerjoin(Customer, Order.customer_id == Customer.id)\
         .filter(Order.order_date >= start_date, Order.order_date <= end_date)

        if channel and channel != 'all':
            query = query.filter(Order.channel == channel)
        if status and status != 'all':
            query = query.filter(Order.status == status)

        records = query.all()
        if not records:
            return pl.DataFrame(schema={
                'id': pl.Int64,
                'bling_id': pl.Int64,
                'order_number': pl.Utf8,
                'order_date': pl.Date,
                'customer_id': pl.Int64,
                'customer_name': pl.Utf8,
                'total': pl.Float64,
                'discount': pl.Float64,
                'shipping': pl.Float64,
                'net_amount': pl.Float64,
                'status': pl.Utf8,
                'channel': pl.Utf8,
                'seller': pl.Utf8
            })

        data = [{
            'id': r.id,
            'bling_id': r.bling_id,
            'order_number': r.order_number or f"PED-{r.id}",
            'order_date': r.order_date,
            'customer_id': r.customer_id,
            'customer_name': r.customer_name or 'Consumidor',
            'total': float(r.total or 0.0),
            'discount': float(r.discount or 0.0),
            'shipping': float(r.shipping or 0.0),
            'net_amount': float((r.total or 0.0) - (r.discount or 0.0) + (r.shipping or 0.0)),
            'status': r.status or 'Desconhecido',
            'channel': r.channel or 'Loja Física',
            'seller': r.seller_name or 'Vendedor Padrão'
        } for r in records]

        return pl.DataFrame(data)

    @staticmethod
    def get_order_items_df(
        start_date: date,
        end_date: date,
        channel: Optional[str] = None,
        status: str = 'Atendido'
    ) -> pl.DataFrame:
        """
        Retorna DataFrame Polars detalhado ao nível de item de pedido.
        Cruza informações de custo unitário do produto e categoria.
        """
        query = db.session.query(
            OrderItem.id.label('item_id'),
            OrderItem.order_id,
            Order.number.label('order_number'),
            Order.order_date,
            Order.channel,
            Order.status,
            Order.seller_name,
            OrderItem.product_id,
            Product.sku.label('product_code'),
            Product.name.label('product_name'),
            Product.category.label('product_category'),
            OrderItem.quantity,
            OrderItem.unit_price,
            OrderItem.total_price,
            OrderItem.cost_price,
            Product.cost.label('catalog_cost_price')
        ).join(Order, OrderItem.order_id == Order.id)\
         .outerjoin(Product, OrderItem.product_id == Product.id)\
         .filter(Order.order_date >= start_date, Order.order_date <= end_date)

        if status and status != 'all':
            query = query.filter(Order.status == status)
        if channel and channel != 'all':
            query = query.filter(Order.channel == channel)

        records = query.all()
        if not records:
            return pl.DataFrame(schema={
                'item_id': pl.Int64,
                'order_id': pl.Int64,
                'order_number': pl.Utf8,
                'order_date': pl.Date,
                'channel': pl.Utf8,
                'status': pl.Utf8,
                'seller': pl.Utf8,
                'product_id': pl.Int64,
                'product_code': pl.Utf8,
                'product_name': pl.Utf8,
                'product_category': pl.Utf8,
                'quantity': pl.Float64,
                'unit_price': pl.Float64,
                'total_price': pl.Float64,
                'cost_price': pl.Float64,
                'total_cost': pl.Float64
            })

        data = []
        for r in records:
            qty = float(r.quantity or 0.0)
            tot_price = float(r.total_price or (qty * float(r.unit_price or 0.0)))
            unit_cost = float(r.cost_price if r.cost_price is not None else (r.catalog_cost_price or 0.0))
            tot_cost = qty * unit_cost
            data.append({
                'item_id': r.item_id,
                'order_id': r.order_id,
                'order_number': r.order_number or f"PED-{r.order_id}",
                'order_date': r.order_date,
                'channel': r.channel or 'Loja Física',
                'status': r.status or 'Desconhecido',
                'seller': r.seller_name or 'Vendedor Geral',
                'product_id': r.product_id,
                'product_code': r.product_code or 'S/C',
                'product_name': r.product_name or 'Item sem cadastro',
                'product_category': r.product_category or 'Geral',
                'quantity': qty,
                'unit_price': float(r.unit_price or 0.0),
                'total_price': tot_price,
                'cost_price': unit_cost,
                'total_cost': tot_cost
            })

        return pl.DataFrame(data)

    # -------------------------------------------------------------------------
    # 3. PRODUTOS E ESTOQUE
    # -------------------------------------------------------------------------
    @staticmethod
    def get_products_df(category: Optional[str] = None) -> pl.DataFrame:
        """
        Retorna DataFrame Polars com todos os produtos, saldos de estoque e custos.
        """
        query = db.session.query(
            Product.id,
            Product.sku,
            Product.name,
            Product.category,
            Product.stock,
            Product.price,
            Product.cost
        )
        if category and category != 'all':
            query = query.filter(Product.category == category)

        records = query.all()
        if not records:
            return pl.DataFrame(schema={
                'id': pl.Int64,
                'code': pl.Utf8,
                'name': pl.Utf8,
                'category': pl.Utf8,
                'stock_quantity': pl.Float64,
                'price': pl.Float64,
                'cost_price': pl.Float64,
                'stock_value': pl.Float64
            })

        data = [{
            'id': r.id,
            'code': r.sku or 'S/C',
            'name': r.name or 'Sem Nome',
            'category': r.category or 'Sem Categoria',
            'stock_quantity': float(r.stock or 0.0),
            'price': float(r.price or 0.0),
            'cost_price': float(r.cost or 0.0),
            'stock_value': float(r.stock or 0.0) * float(r.cost or 0.0)
        } for r in records]

        return pl.DataFrame(data)

    # -------------------------------------------------------------------------
    # 4. CLIENTES E CRM
    # -------------------------------------------------------------------------
    @staticmethod
    def get_customers_df() -> pl.DataFrame:
        """
        Retorna DataFrame Polars de todos os clientes com dados cadastrais e de compras.
        """
        records = db.session.query(
            Customer.id,
            Customer.bling_id,
            Customer.name,
            Customer.email,
            Customer.phone,
            Customer.city,
            Customer.state,
            func.count(Order.id).label('total_orders'),
            func.coalesce(func.sum(Order.total), 0.0).label('total_spent'),
            func.max(Order.order_date).label('last_order_date')
        ).outerjoin(Order, Customer.id == Order.customer_id)\
         .group_by(Customer.id).all()

        if not records:
            return pl.DataFrame(schema={
                'id': pl.Int64,
                'bling_id': pl.Int64,
                'name': pl.Utf8,
                'email': pl.Utf8,
                'phone': pl.Utf8,
                'city': pl.Utf8,
                'state': pl.Utf8,
                'total_orders': pl.Int64,
                'total_spent': pl.Float64,
                'last_order_date': pl.Date
            })

        data = [{
            'id': r.id,
            'bling_id': r.bling_id,
            'name': r.name or 'Consumidor',
            'email': r.email or '',
            'phone': r.phone or '',
            'city': r.city or '',
            'state': r.state or '',
            'total_orders': int(r.total_orders or 0),
            'total_spent': float(r.total_spent or 0.0),
            'last_order_date': r.last_order_date
        } for r in records]

        return pl.DataFrame(data)

    # -------------------------------------------------------------------------
    # 5. FINANCEIRO (CONTAS A RECEBER E PAGAR)
    # -------------------------------------------------------------------------
    @staticmethod
    def get_financial_entries_df(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        entry_type: Optional[str] = None
    ) -> pl.DataFrame:
        """
        Retorna DataFrame Polars com lançamentos financeiros.
        entry_type: 'R'/'RECEBER' ou 'P'/'PAGAR' ou None (ambos).
        """
        query = db.session.query(
            FinancialEntry.id,
            FinancialEntry.entry_type,
            FinancialEntry.category,
            FinancialEntry.amount,
            FinancialEntry.due_date,
            FinancialEntry.payment_date,
            FinancialEntry.status,
            FinancialEntry.description
        )

        if start_date and end_date:
            query = query.filter(FinancialEntry.due_date >= start_date, FinancialEntry.due_date <= end_date)
        if entry_type and entry_type != 'all':
            if entry_type.upper() in ['R', 'RECEBER']:
                query = query.filter(FinancialEntry.entry_type.in_(['R', 'RECEBER']))
            elif entry_type.upper() in ['P', 'PAGAR']:
                query = query.filter(FinancialEntry.entry_type.in_(['P', 'PAGAR']))

        records = query.all()
        if not records:
            return pl.DataFrame(schema={
                'id': pl.Int64,
                'entry_type': pl.Utf8,
                'category': pl.Utf8,
                'amount': pl.Float64,
                'due_date': pl.Date,
                'payment_date': pl.Date,
                'status': pl.Utf8,
                'description': pl.Utf8
            })

        data = [{
            'id': r.id,
            'entry_type': r.entry_type,
            'category': r.category or 'Geral',
            'amount': float(r.amount or 0.0),
            'due_date': r.due_date,
            'payment_date': r.payment_date,
            'status': r.status or 'Em aberto',
            'description': r.description or ''
        } for r in records]

        return pl.DataFrame(data)

    # -------------------------------------------------------------------------
    # 6. RESUMO EXECUTIVO CONSOLIDADO
    # -------------------------------------------------------------------------
    @staticmethod
    def get_summary_kpis(start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Calcula os KPIs executivos consolidados para a janela temporal selecionada.
        """
        sales = db.session.query(
            func.coalesce(func.sum(Order.total), 0.0),
            func.count(Order.id)
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).first()

        rev = float(sales[0] or 0.0)
        cnt = int(sales[1] or 0)
        ticket = (rev / cnt) if cnt > 0 else 0.0

        return {
            'total_revenue': rev,
            'orders_count': cnt,
            'avg_ticket': ticket,
            'period_start': start_date,
            'period_end': end_date
        }
