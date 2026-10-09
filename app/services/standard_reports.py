import polars as pl
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func, and_, or_, desc
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.financial import FinancialEntry

class StandardReportsEngine:
    """
    Motor analítico para geração dos Relatórios Padronizados Estratégicos Bling ERP API v3.
    Processa agregações multivariadas via Polars e SQLAlchemy para suporte à tomada de decisão.
    """

    # =========================================================================
    # PILAR 1: PERFORMANCE MULTICANAL & MARGEM POR MARKETPLACE
    # =========================================================================
    @staticmethod
    def get_multichannel_performance(
        start_date: date, 
        end_date: date, 
        channel_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gera o relatório padronizado de Performance Multicanal e Rentabilidade Real por Canal.
        Cruza faturamento, descontos, fretes e CMV dos itens para calcular a margem de contribuição.
        """
        # 1. Busca todos os pedidos do período para análise de funil e cancelamento
        all_orders_query = db.session.query(
            Order.id,
            Order.channel,
            Order.status,
            Order.total,
            Order.discount,
            Order.shipping
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date
        )

        if channel_filter and channel_filter != 'all':
            all_orders_query = all_orders_query.filter(Order.channel == channel_filter)

        all_orders = all_orders_query.all()

        if not all_orders:
            return {
                'channels': [],
                'summary': {
                    'total_gross_sales': 0.0,
                    'total_net_sales': 0.0,
                    'total_cmv': 0.0,
                    'total_gross_profit': 0.0,
                    'overall_margin_pct': 0.0,
                    'orders_attended': 0,
                    'orders_cancelled': 0,
                    'fill_rate_pct': 0.0,
                    'lost_revenue_cancelled': 0.0,
                    'avg_ticket': 0.0
                },
                'charts': {
                    'sales_by_channel': {'labels': [], 'net_sales': [], 'gross_profit': [], 'margins': []},
                    'channel_share': {'labels': [], 'data': []},
                    'funnel_status': {'labels': ['Atendido', 'Em aberto', 'Cancelado'], 'data': [0, 0, 0]}
                }
            }

        # Estatísticas de Funil
        status_counts = {'Atendido': 0, 'Em aberto': 0, 'Cancelado': 0}
        lost_revenue_cancelled = 0.0

        for o in all_orders:
            st = o.status or 'Atendido'
            if st in status_counts:
                status_counts[st] += 1
            else:
                status_counts['Atendido'] += 1

            if st == 'Cancelado':
                lost_revenue_cancelled += float(o.total or 0.0)

        total_orders_count = len(all_orders)
        orders_attended = status_counts['Atendido']
        orders_cancelled = status_counts['Cancelado']
        fill_rate_pct = round((orders_attended / total_orders_count * 100), 1) if total_orders_count > 0 else 0.0

        # 2. Busca pedidos atendidos com itens para cálculo de CMV e Margem
        items_query = db.session.query(
            Order.id.label('order_id'),
            Order.channel.label('channel'),
            Order.total.label('order_total'),
            Order.discount.label('order_discount'),
            Order.shipping.label('order_shipping'),
            OrderItem.quantity.label('quantity'),
            OrderItem.unit_price.label('unit_price'),
            OrderItem.cost_price.label('cost_price'),
            OrderItem.total_price.label('item_total')
        ).join(
            OrderItem, OrderItem.order_id == Order.id
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        )

        if channel_filter and channel_filter != 'all':
            items_query = items_query.filter(Order.channel == channel_filter)

        raw_items = items_query.all()

        channels_list = []
        if raw_items:
            # Processamento em Polars
            df = pl.DataFrame({
                'order_id': [r.order_id for r in raw_items],
                'channel': [r.channel or 'Loja Virtual' for r in raw_items],
                'order_total': [float(r.order_total or 0.0) for r in raw_items],
                'quantity': [float(r.quantity or 1.0) for r in raw_items],
                'cost_price': [float(r.cost_price or 0.0) for r in raw_items],
                'item_total': [float(r.item_total or 0.0) for r in raw_items]
            })

            # Calcula CMV do item
            df = df.with_columns([
                (pl.col('quantity') * pl.col('cost_price')).alias('item_cmv')
            ])

            # Agrupamento por pedido primeiro para obter totais de pedidos sem duplicar
            orders_unique_df = df.group_by(['order_id', 'channel']).agg([
                pl.first('order_total').alias('order_total'),
                pl.sum('item_cmv').alias('order_cmv'),
                pl.sum('quantity').alias('order_items_qty')
            ])

            # Agrupamento final por canal
            channel_agg = orders_unique_df.group_by('channel').agg([
                pl.count('order_id').alias('orders_count'),
                pl.sum('order_total').alias('net_sales'),
                pl.sum('order_cmv').alias('total_cmv'),
                pl.sum('order_items_qty').alias('total_items')
            ]).sort('net_sales', descending=True)

            for row in channel_agg.iter_rows(named=True):
                c_name = row['channel']
                c_orders = row['orders_count']
                c_net = round(row['net_sales'], 2)
                c_cmv = round(row['total_cmv'], 2)
                c_profit = round(c_net - c_cmv, 2)
                c_margin = round((c_profit / c_net * 100), 1) if c_net > 0 else 0.0
                c_ticket = round(c_net / c_orders, 2) if c_orders > 0 else 0.0
                c_pa = round(row['total_items'] / c_orders, 1) if c_orders > 0 else 0.0

                # Cancelados específicos deste canal
                ch_cancelled = len([o for o in all_orders if o.channel == c_name and o.status == 'Cancelado'])
                ch_total_orders = len([o for o in all_orders if o.channel == c_name])
                ch_canc_rate = round((ch_cancelled / ch_total_orders * 100), 1) if ch_total_orders > 0 else 0.0

                channels_list.append({
                    'channel': c_name,
                    'orders_count': c_orders,
                    'net_sales': c_net,
                    'cmv': c_cmv,
                    'gross_profit': c_profit,
                    'margin_pct': c_margin,
                    'avg_ticket': c_ticket,
                    'items_per_order': c_pa,
                    'cancelled_count': ch_cancelled,
                    'cancellation_rate': ch_canc_rate
                })

        # Totais consolidados
        total_net_sales = sum(c['net_sales'] for c in channels_list)
        total_cmv = sum(c['cmv'] for c in channels_list)
        total_gross_profit = sum(c['gross_profit'] for c in channels_list)
        overall_margin_pct = round((total_gross_profit / total_net_sales * 100), 1) if total_net_sales > 0 else 0.0
        avg_ticket = round(total_net_sales / orders_attended, 2) if orders_attended > 0 else 0.0

        # Prepara dados para os gráficos Chart.js
        chart_labels = [c['channel'] for c in channels_list]
        chart_net_sales = [c['net_sales'] for c in channels_list]
        chart_profit = [c['gross_profit'] for c in channels_list]
        chart_margins = [c['margin_pct'] for c in channels_list]

        return {
            'channels': channels_list,
            'summary': {
                'total_net_sales': total_net_sales,
                'total_cmv': total_cmv,
                'total_gross_profit': total_gross_profit,
                'overall_margin_pct': overall_margin_pct,
                'orders_attended': orders_attended,
                'orders_cancelled': orders_cancelled,
                'fill_rate_pct': fill_rate_pct,
                'lost_revenue_cancelled': round(lost_revenue_cancelled, 2),
                'avg_ticket': avg_ticket
            },
            'charts': {
                'sales_by_channel': {
                    'labels': chart_labels,
                    'net_sales': chart_net_sales,
                    'gross_profit': chart_profit,
                    'margins': chart_margins
                },
                'channel_share': {
                    'labels': chart_labels,
                    'data': chart_net_sales
                },
                'funnel_status': {
                    'labels': ['Atendido', 'Em aberto', 'Cancelado'],
                    'data': [status_counts['Atendido'], status_counts['Em aberto'], status_counts['Cancelado']]
                }
            }
        }


    # =========================================================================
    # PILAR 2: PRODUTOS, GIRO, CURVA ABC & ALERTA DE RUPTURA / COBERTURA
    # =========================================================================
    @staticmethod
    def get_stock_coverage_and_abc(
        start_date: date, 
        end_date: date, 
        category_filter: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cruza saldo em estoque da API com vendas no período para calcular:
        - Run-rate (Venda média diária)
        - Dias de Cobertura de Estoque (DDE)
        - Níveis térmicos de Ruptura (Crítico < 7d, Atenção 7-15d, Equilibrado, Excesso > 45d, Sem Giro)
        - Curva ABC de Pareto sobre Receita e Margem Real
        """
        period_days = max(1, (end_date - start_date).days + 1)

        # 1. Todos os produtos ativos no catálogo
        prod_query = db.session.query(
            Product.id,
            Product.sku,
            Product.name,
            Product.category,
            Product.price,
            Product.cost,
            Product.stock
        ).filter(Product.status == 'A')

        if category_filter and category_filter != 'all':
            prod_query = prod_query.filter(Product.category == category_filter)

        products = prod_query.all()
        if not products:
            return {
                'items': [],
                'summary': {
                    'total_products': 0,
                    'critical_rupture_count': 0,
                    'deadstock_capital': 0.0,
                    'total_stock_capital': 0.0,
                    'avg_coverage_days': 0.0
                },
                'charts': {
                    'pareto': {'labels': [], 'revenues': [], 'cum_pct': []},
                    'coverage_status': {'labels': [], 'data': []}
                }
            }

        # 2. Vendas do período por produto
        sales_query = db.session.query(
            OrderItem.product_id,
            func.coalesce(func.sum(OrderItem.quantity), 0.0).label('total_qty'),
            func.coalesce(func.sum(OrderItem.total_price), 0.0).label('total_rev'),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.cost_price), 0.0).label('total_cmv')
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).group_by(OrderItem.product_id).all()

        sales_map = {
            s.product_id: {
                'qty': float(s.total_qty),
                'rev': float(s.total_rev),
                'cmv': float(s.total_cmv)
            } for s in sales_query
        }

        # Monta lista bruta para cálculo do Pareto
        raw_rows = []
        for p in products:
            s_data = sales_map.get(p.id, {'qty': 0.0, 'rev': 0.0, 'cmv': 0.0})
            units_sold = s_data['qty']
            rev = s_data['rev']
            cmv = s_data['cmv']
            gross_profit = rev - cmv
            run_rate = units_sold / period_days
            stock = float(p.stock or 0.0)
            cost = float(p.cost or 0.0)

            # Cálculo de cobertura
            if run_rate > 0:
                coverage_days = round(stock / run_rate, 1)
            else:
                coverage_days = 999.0 if stock > 0 else 0.0

            # Classificação de status de estoque
            if stock <= 0 and units_sold > 0:
                cov_status = 'ESGOTADO'
                badge_color = 'danger'
            elif run_rate > 0 and coverage_days < 7:
                cov_status = 'CRÍTICO'
                badge_color = 'danger'
            elif run_rate > 0 and 7 <= coverage_days <= 15:
                cov_status = 'ATENÇÃO'
                badge_color = 'warning'
            elif run_rate > 0 and 16 <= coverage_days <= 45:
                cov_status = 'EQUILIBRADO'
                badge_color = 'success'
            elif run_rate > 0 and coverage_days > 45:
                cov_status = 'EXCESSO'
                badge_color = 'info'
            elif stock > 0 and units_sold == 0:
                cov_status = 'SEM GIRO'
                badge_color = 'secondary'
            else:
                cov_status = 'EQUILIBRADO'
                badge_color = 'success'

            # Capital imobilizado em risco (parado ou excessivo > 45d)
            deadstock_capital = stock * cost if (cov_status in ['SEM GIRO', 'EXCESSO']) else 0.0

            raw_rows.append({
                'id': p.id,
                'sku': p.sku or 'N/A',
                'name': p.name,
                'category': p.category or 'Geral',
                'price': float(p.price or 0.0),
                'cost': cost,
                'stock': stock,
                'units_sold': units_sold,
                'revenue': rev,
                'cmv': cmv,
                'gross_profit': gross_profit,
                'run_rate': round(run_rate, 2),
                'coverage_days': coverage_days,
                'cov_status': cov_status,
                'badge_color': badge_color,
                'stock_capital': round(stock * cost, 2),
                'deadstock_capital': round(deadstock_capital, 2)
            })

        # Processamento de Curva ABC (Pareto) via Polars
        df_prod = pl.DataFrame(raw_rows).sort('revenue', descending=True)
        total_revenue = df_prod['revenue'].sum()

        if total_revenue > 0:
            df_prod = df_prod.with_columns([
                (pl.col('revenue').cum_sum() / total_revenue * 100).alias('cum_pct')
            ]).with_columns([
                pl.when(pl.col('cum_pct') <= 80.0)
                .then(pl.lit('A'))
                .when(pl.col('cum_pct') <= 95.0)
                .then(pl.lit('B'))
                .otherwise(pl.lit('C'))
                .alias('abc_class')
            ])
        else:
            df_prod = df_prod.with_columns([
                pl.lit(0.0).alias('cum_pct'),
                pl.lit('C').alias('abc_class')
            ])

        items_list = df_prod.to_dicts()

        # Filtro opcional por status de estoque
        if status_filter and status_filter != 'all':
            items_list = [i for i in items_list if i['cov_status'] == status_filter]

        # Resumo de inteligência executiva
        total_stock_capital = sum(i['stock_capital'] for i in items_list)
        total_deadstock_capital = sum(i['deadstock_capital'] for i in items_list)
        critical_rupture_count = len([i for i in items_list if i['cov_status'] in ['CRÍTICO', 'ESGOTADO']])
        
        active_coverages = [i['coverage_days'] for i in items_list if i['run_rate'] > 0 and i['coverage_days'] < 999]
        avg_coverage_days = round(sum(active_coverages) / len(active_coverages), 1) if active_coverages else 0.0

        # Gráfico de Pareto: Top 15 SKUs
        top_15 = df_prod.head(15).to_dicts()
        pareto_labels = [f"{t['sku']} - {t['name'][:18]}" for t in top_15]
        pareto_revenues = [round(t['revenue'], 2) for t in top_15]
        pareto_cum_pct = [round(t['cum_pct'], 1) for t in top_15]

        # Gráfico Donut de Status de Cobertura
        status_counts = {'CRÍTICO': 0, 'ESGOTADO': 0, 'ATENÇÃO': 0, 'EQUILIBRADO': 0, 'EXCESSO': 0, 'SEM GIRO': 0}
        for item in df_prod.to_dicts():
            st = item['cov_status']
            if st in status_counts:
                status_counts[st] += 1

        return {
            'items': items_list,
            'summary': {
                'total_products': len(products),
                'critical_rupture_count': critical_rupture_count,
                'deadstock_capital': round(total_deadstock_capital, 2),
                'total_stock_capital': round(total_stock_capital, 2),
                'avg_coverage_days': avg_coverage_days
            },
            'charts': {
                'pareto': {
                    'labels': pareto_labels,
                    'revenues': pareto_revenues,
                    'cum_pct': pareto_cum_pct
                },
                'coverage_status': {
                    'labels': list(status_counts.keys()),
                    'data': list(status_counts.values())
                }
            }
        }


    # =========================================================================
    # PILAR 3: MATRIZ RFM (RECÊNCIA, FREQUÊNCIA E VALOR) & SEGMENTAÇÃO CRM
    # =========================================================================
    @staticmethod
    def get_rfm_matrix(
        reference_date: Optional[date] = None, 
        cluster_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa a segmentação RFM (Recência, Frequência e Valor Monetário) de toda a base de clientes.
        Classifica em clusters estratégicos para campanhas de fidelização e reativação de churn.
        """
        ref_date = reference_date or date.today()

        # Extrai todas as compras por cliente
        orders_query = db.session.query(
            Customer.id.label('customer_id'),
            Customer.name.label('customer_name'),
            Customer.email.label('customer_email'),
            Customer.phone.label('customer_phone'),
            Customer.city.label('customer_city'),
            Customer.state.label('customer_state'),
            Order.id.label('order_id'),
            Order.order_date.label('order_date'),
            Order.total.label('order_total')
        ).join(
            Order, Order.customer_id == Customer.id
        ).filter(
            Order.status == 'Atendido'
        ).all()

        if not orders_query:
            return {
                'customers': [],
                'summary': {
                    'total_customers': 0,
                    'champions_count': 0,
                    'loyal_count': 0,
                    'at_risk_count': 0,
                    'churn_count': 0,
                    'avg_ltv': 0.0
                },
                'charts': {
                    'rfm_clusters': {'labels': [], 'data': []},
                    'rfm_revenue': {'labels': [], 'data': []}
                }
            }

        # Polars para cálculo RFM por cliente
        df = pl.DataFrame({
            'customer_id': [r.customer_id for r in orders_query],
            'customer_name': [r.customer_name for r in orders_query],
            'customer_email': [r.customer_email or '' for r in orders_query],
            'customer_phone': [r.customer_phone or '' for r in orders_query],
            'customer_city': [r.customer_city or 'N/A' for r in orders_query],
            'customer_state': [r.customer_state or 'N/A' for r in orders_query],
            'order_id': [r.order_id for r in orders_query],
            'order_date': [r.order_date for r in orders_query],
            'order_total': [float(r.order_total or 0.0) for r in orders_query]
        })

        # Agrega métricas R, F, M
        cust_rfm = df.group_by([
            'customer_id', 'customer_name', 'customer_email', 'customer_phone', 'customer_city', 'customer_state'
        ]).agg([
            pl.max('order_date').alias('last_order_date'),
            pl.count('order_id').alias('frequency'),
            pl.sum('order_total').alias('monetary')
        ])

        customers_list = []
        cluster_counts = {
            '👑 Campeões': 0,
            '💎 Clientes Leais': 0,
            '🌱 Promissores / Novos': 0,
            '⚠️ Em Risco': 0,
            '💤 Inativos / Churn': 0,
            '👥 Outros': 0
        }
        cluster_revenues = {k: 0.0 for k in cluster_counts.keys()}

        for row in cust_rfm.iter_rows(named=True):
            last_date = row['last_order_date']
            recency_days = (ref_date - last_date).days if last_date else 999
            freq = row['frequency']
            mon = round(row['monetary'], 2)

            # Pontuação R (1 a 5)
            if recency_days <= 30:
                r_score = 5
            elif recency_days <= 60:
                r_score = 4
            elif recency_days <= 90:
                r_score = 3
            elif recency_days <= 180:
                r_score = 2
            else:
                r_score = 1

            # Pontuação F (1 a 5)
            if freq >= 6:
                f_score = 5
            elif freq >= 4:
                f_score = 4
            elif freq >= 3:
                f_score = 3
            elif freq == 2:
                f_score = 2
            else:
                f_score = 1

            # Pontuação M (1 a 5)
            if mon >= 3000:
                m_score = 5
            elif mon >= 1500:
                m_score = 4
            elif mon >= 800:
                m_score = 3
            elif mon >= 300:
                m_score = 2
            else:
                m_score = 1

            # Definição do Cluster Estratégico
            if r_score >= 4 and f_score >= 4 and m_score >= 4:
                cluster = '👑 Campeões'
                action_tip = 'Tratamento VIP, lançamentos em primeira mão, programa fidelidade'
            elif r_score >= 3 and f_score >= 3:
                cluster = '💎 Clientes Leais'
                action_tip = 'Cross-sell, upgrade de categoria e incentivo a avaliações'
            elif r_score >= 4 and f_score <= 2:
                cluster = '🌱 Promissores / Novos'
                action_tip = 'Nutrição pós-compra, onboarding da marca, cupom para 2ª compra'
            elif r_score <= 2 and f_score >= 3:
                cluster = '⚠️ Em Risco'
                action_tip = 'Oferta de reativação personalizada, contato consultivo via WhatsApp'
            elif r_score == 1 and f_score <= 2:
                cluster = '💤 Inativos / Churn'
                action_tip = 'Campanha agressiva de retorno com desconto de queima de estoque'
            else:
                cluster = '👥 Outros'
                action_tip = 'Comunicação padrão e promoções sazonais'

            cluster_counts[cluster] += 1
            cluster_revenues[cluster] += mon

            customers_list.append({
                'id': row['customer_id'],
                'name': row['customer_name'],
                'email': row['customer_email'],
                'phone': row['customer_phone'],
                'city': row['customer_city'],
                'state': row['customer_state'],
                'last_order_date': last_date.strftime('%d/%m/%Y') if last_date else 'N/A',
                'recency_days': recency_days,
                'frequency': freq,
                'monetary': mon,
                'r_score': r_score,
                'f_score': f_score,
                'm_score': m_score,
                'rfm_score': f"{r_score}{f_score}{m_score}",
                'cluster': cluster,
                'action_tip': action_tip
            })

        # Ordena clientes por maior valor monetário acumulado (LTV)
        customers_list.sort(key=lambda x: x['monetary'], reverse=True)

        if cluster_filter and cluster_filter != 'all':
            customers_list = [c for c in customers_list if c['cluster'] == cluster_filter]

        total_customers = len(cust_rfm)
        total_revenue = sum(c['monetary'] for c in customers_list)
        avg_ltv = round(total_revenue / total_customers, 2) if total_customers > 0 else 0.0

        return {
            'customers': customers_list,
            'summary': {
                'total_customers': total_customers,
                'champions_count': cluster_counts['👑 Campeões'],
                'loyal_count': cluster_counts['💎 Clientes Leais'],
                'at_risk_count': cluster_counts['⚠️ Em Risco'],
                'churn_count': cluster_counts['💤 Inativos / Churn'],
                'avg_ltv': avg_ltv
            },
            'charts': {
                'rfm_clusters': {
                    'labels': list(cluster_counts.keys()),
                    'data': list(cluster_counts.values())
                },
                'rfm_revenue': {
                    'labels': list(cluster_revenues.keys()),
                    'data': [round(v, 2) for v in cluster_revenues.values()]
                }
            }
        }


    # =========================================================================
    # PILAR 4: DRE GERENCIAL SINTÉTICO & FLUXO DE CAIXA PROJETADO
    # =========================================================================
    @staticmethod
    def get_dre_statement(start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Gera a DRE Gerencial Sintética estruturada por Regime de Competência:
        Receita Bruta -> Deduções -> Receita Líquida -> CMV -> Lucro Bruto -> Despesas Fixas -> Lucro Líquido
        """
        # 1. Receita Bruta de Pedidos Atendidos
        orders_attended = db.session.query(
            func.coalesce(func.sum(Order.total), 0.0).label('total'),
            func.coalesce(func.sum(Order.discount), 0.0).label('discount')
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).first()

        net_sales = float(orders_attended.total or 0.0)
        discounts = float(orders_attended.discount or 0.0)
        gross_sales = net_sales + discounts

        # 2. Devoluções / Cancelamentos no período
        cancelled_total = db.session.query(
            func.coalesce(func.sum(Order.total), 0.0)
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Cancelado'
        ).scalar() or 0.0

        # 3. CMV (Custo das Mercadorias Vendidas) dos itens atendidos
        cmv_total = db.session.query(
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.cost_price), 0.0)
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).scalar() or 0.0

        # 4. Despesas Operacionais em Contas a Pagar
        expenses_query = db.session.query(
            FinancialEntry.category,
            func.sum(FinancialEntry.amount).label('total_amount')
        ).filter(
            FinancialEntry.entry_type == 'PAGAR',
            FinancialEntry.due_date >= start_date,
            FinancialEntry.due_date <= end_date,
            FinancialEntry.status != 'Cancelado'
        ).group_by(FinancialEntry.category).all()

        operating_expenses = {}
        for exp in expenses_query:
            cat_name = exp.category or 'Despesas Gerais'
            operating_expenses[cat_name] = float(exp.total_amount or 0.0)

        total_operating_expenses = sum(operating_expenses.values())

        # Cálculos de Linhas da DRE
        deductions = discounts + float(cancelled_total)
        net_operating_revenue = max(0.0, gross_sales - deductions)
        gross_profit = net_operating_revenue - float(cmv_total)
        gross_margin_pct = round((gross_profit / net_operating_revenue * 100), 1) if net_operating_revenue > 0 else 0.0

        ebitda = gross_profit - total_operating_expenses
        ebitda_margin_pct = round((ebitda / net_operating_revenue * 100), 1) if net_operating_revenue > 0 else 0.0

        # Estimativa de custos financeiros (taxas de intermediadores ~3.5%)
        financial_expenses = round(net_operating_revenue * 0.035, 2)
        net_profit = ebitda - financial_expenses
        net_margin_pct = round((net_profit / net_operating_revenue * 100), 1) if net_operating_revenue > 0 else 0.0

        dre_lines = [
            {'code': '1.0', 'name': '(+) RECEITA BRUTA DE VENDAS', 'value': gross_sales, 'type': 'positive', 'level': 1},
            {'code': '1.1', 'name': '(-) Descontos Comerciais Concedidos', 'value': -discounts, 'type': 'negative', 'level': 2},
            {'code': '1.2', 'name': '(-) Cancelamentos de Pedidos', 'value': -float(cancelled_total), 'type': 'negative', 'level': 2},
            {'code': '2.0', 'name': '(=) RECEITA OPERACIONAL LÍQUIDA (ROL)', 'value': net_operating_revenue, 'type': 'subtotal', 'level': 1},
            {'code': '2.1', 'name': '(-) Custo das Mercadorias Vendidas (CMV)', 'value': -float(cmv_total), 'type': 'negative', 'level': 2},
            {'code': '3.0', 'name': '(=) LUCRO BRUTO', 'value': gross_profit, 'type': 'subtotal', 'level': 1, 'margin_pct': gross_margin_pct},
            {'code': '4.0', 'name': '(-) DESPESAS OPERACIONAIS & ADMINISTRATIVAS', 'value': -total_operating_expenses, 'type': 'negative', 'level': 1}
        ]

        # Adiciona detalhamento de despesas por categoria
        for cat, val in operating_expenses.items():
            dre_lines.append({
                'code': '4.x',
                'name': f"   • {cat}",
                'value': -val,
                'type': 'detail',
                'level': 3
            })

        dre_lines.extend([
            {'code': '5.0', 'name': '(=) RESULTADO OPERACIONAL (EBITDA)', 'value': ebitda, 'type': 'subtotal', 'level': 1, 'margin_pct': ebitda_margin_pct},
            {'code': '6.0', 'name': '(-) Despesas Financeiras & Tarifas de Pagamento', 'value': -financial_expenses, 'type': 'negative', 'level': 2},
            {'code': '7.0', 'name': '(=) RESULTADO LÍQUIDO DO PERÍODO', 'value': net_profit, 'type': 'total', 'level': 1, 'margin_pct': net_margin_pct}
        ])

        # Dados do Waterfall Chart
        waterfall_labels = ['Receita Bruta', 'Deduções', 'CMV', 'Lucro Bruto', 'Despesas', 'Resultado Líquido']
        waterfall_values = [
            round(gross_sales, 2),
            round(-deductions, 2),
            round(-float(cmv_total), 2),
            round(gross_profit, 2),
            round(-total_operating_expenses - financial_expenses, 2),
            round(net_profit, 2)
        ]

        return {
            'lines': dre_lines,
            'summary': {
                'gross_sales': round(gross_sales, 2),
                'net_sales': round(net_operating_revenue, 2),
                'cmv': round(float(cmv_total), 2),
                'gross_profit': round(gross_profit, 2),
                'gross_margin_pct': gross_margin_pct,
                'operating_expenses': round(total_operating_expenses, 2),
                'ebitda': round(ebitda, 2),
                'ebitda_margin_pct': ebitda_margin_pct,
                'net_profit': round(net_profit, 2),
                'net_margin_pct': net_margin_pct
            },
            'charts': {
                'waterfall': {
                    'labels': waterfall_labels,
                    'data': waterfall_values
                }
            }
        }


    @staticmethod
    def get_cash_flow_projection(days: int = 30) -> Dict[str, Any]:
        """
        Projeta o Fluxo de Caixa Diário dos próximos N dias cruzando Contas a Receber vs Contas a Pagar.
        """
        today = date.today()
        end_projection = today + timedelta(days=days)

        entries = db.session.query(
            FinancialEntry.due_date,
            FinancialEntry.entry_type,
            func.sum(FinancialEntry.amount).label('total_amount')
        ).filter(
            FinancialEntry.due_date >= today,
            FinancialEntry.due_date <= end_projection,
            FinancialEntry.status.in_(['Pendente', 'Atrasado'])
        ).group_by(FinancialEntry.due_date, FinancialEntry.entry_type).all()

        date_map = {}
        curr = today
        while curr <= end_projection:
            d_str = curr.strftime('%d/%m')
            date_map[curr] = {'date_label': d_str, 'receber': 0.0, 'pagar': 0.0}
            curr += timedelta(days=1)

        for e in entries:
            if e.due_date in date_map:
                if e.entry_type == 'RECEBER':
                    date_map[e.due_date]['receber'] += float(e.total_amount or 0.0)
                elif e.entry_type == 'PAGAR':
                    date_map[e.due_date]['pagar'] += float(e.total_amount or 0.0)

        # Monta séries e saldo acumulado
        chart_labels = []
        chart_receivables = []
        chart_payables = []
        chart_accumulated = []

        running_balance = 0.0
        daily_rows = []

        for d_key in sorted(date_map.keys()):
            row = date_map[d_key]
            rec = round(row['receber'], 2)
            pag = round(row['pagar'], 2)
            net_day = round(rec - pag, 2)
            running_balance += net_day

            chart_labels.append(row['date_label'])
            chart_receivables.append(rec)
            chart_payables.append(pag)
            chart_accumulated.append(round(running_balance, 2))

            daily_rows.append({
                'date': d_key.strftime('%d/%m/%Y'),
                'receivables': rec,
                'payables': pag,
                'net': net_day,
                'accumulated': round(running_balance, 2)
            })

        total_rec = sum(chart_receivables)
        total_pag = sum(chart_payables)
        final_balance = round(total_rec - total_pag, 2)

        return {
            'daily_rows': daily_rows,
            'summary': {
                'total_receivables': round(total_rec, 2),
                'total_payables': round(total_pag, 2),
                'net_projected_balance': final_balance
            },
            'charts': {
                'labels': chart_labels,
                'receivables': chart_receivables,
                'payables': chart_payables,
                'accumulated': chart_accumulated
            }
        }


    # =========================================================================
    # RELATÓRIO 4.4: INADIMPLÊNCIA & AGING LIST (CONTAS A RECEBER)
    # =========================================================================
    @staticmethod
    def get_aging_list_analysis(start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Gera análise de inadimplência e Aging List (faixas de atraso) dos títulos a receber em aberto.
        """
        today = date.today()

        query = db.session.query(FinancialEntry).filter(
            FinancialEntry.entry_type == 'RECEBER',
            FinancialEntry.status.in_(['Pendente', 'Atrasado'])
        )

        if start_date:
            query = query.filter(FinancialEntry.due_date >= start_date)
        if end_date:
            query = query.filter(FinancialEntry.due_date <= end_date)

        entries = query.order_by(FinancialEntry.due_date.asc()).all()

        buckets = {
            'a_vencer': {'label': 'A Vencer (Em dia)', 'amount': 0.0, 'count': 0, 'color': '#10B981'},
            '1_15': {'label': '1 a 15 dias', 'amount': 0.0, 'count': 0, 'color': '#F59E0B'},
            '16_30': {'label': '16 a 30 dias', 'amount': 0.0, 'count': 0, 'color': '#EA580C'},
            '31_60': {'label': '31 a 60 dias', 'amount': 0.0, 'count': 0, 'color': '#DC2626'},
            'mais_60': {'label': 'Mais de 60 dias', 'amount': 0.0, 'count': 0, 'color': '#991B1B'}
        }

        total_open = 0.0
        total_overdue = 0.0
        total_ontime = 0.0
        debtors_map = {}
        entries_list = []

        for e in entries:
            amt = float(e.amount or 0.0)
            total_open += amt
            days_diff = (today - e.due_date).days if e.due_date else 0

            if days_diff <= 0:
                bucket_key = 'a_vencer'
                total_ontime += amt
            elif 1 <= days_diff <= 15:
                bucket_key = '1_15'
                total_overdue += amt
            elif 16 <= days_diff <= 30:
                bucket_key = '16_30'
                total_overdue += amt
            elif 31 <= days_diff <= 60:
                bucket_key = '31_60'
                total_overdue += amt
            else:
                bucket_key = 'mais_60'
                total_overdue += amt

            buckets[bucket_key]['amount'] += amt
            buckets[bucket_key]['count'] += 1

            client = e.entity_name or 'Cliente Não Identificado'
            if client not in debtors_map:
                debtors_map[client] = {
                    'name': client,
                    'total_due': 0.0,
                    'overdue_amount': 0.0,
                    'titles_count': 0,
                    'max_days_overdue': 0
                }
            debtors_map[client]['total_due'] += amt
            debtors_map[client]['titles_count'] += 1
            if days_diff > 0:
                debtors_map[client]['overdue_amount'] += amt
                if days_diff > debtors_map[client]['max_days_overdue']:
                    debtors_map[client]['max_days_overdue'] = days_diff

            entries_list.append({
                'id': e.id,
                'entity_name': client,
                'description': e.description,
                'amount': amt,
                'due_date': e.due_date.strftime('%d/%m/%Y') if e.due_date else '-',
                'days_diff': days_diff,
                'bucket_label': buckets[bucket_key]['label'],
                'bucket_color': buckets[bucket_key]['color'],
                'status': 'Atrasado' if days_diff > 0 else 'A Vencer'
            })

        # Arredonda balanços
        for b in buckets.values():
            b['amount'] = round(b['amount'], 2)

        default_rate = round((total_overdue / total_open * 100), 1) if total_open > 0 else 0.0

        top_debtors = sorted(
            [d for d in debtors_map.values() if d['overdue_amount'] > 0],
            key=lambda x: x['overdue_amount'],
            reverse=True
        )[:15]

        # Gráfico Donut de Aging
        chart_labels = [b['label'] for b in buckets.values()]
        chart_values = [b['amount'] for b in buckets.values()]
        chart_colors = [b['color'] for b in buckets.values()]

        return {
            'buckets': buckets,
            'summary': {
                'total_open': round(total_open, 2),
                'total_ontime': round(total_ontime, 2),
                'total_overdue': round(total_overdue, 2),
                'default_rate': default_rate,
                'total_titles': len(entries)
            },
            'top_debtors': top_debtors,
            'entries': entries_list[:50],
            'chart': {
                'labels': chart_labels,
                'data': chart_values,
                'colors': chart_colors
            }
        }

    # =========================================================================
    # HUB CENTRAL: RESUMO EXECUTIVO DOS 5 PILARES
    # =========================================================================
    @staticmethod
    def get_hub_summary() -> Dict[str, Any]:
        """
        Retorna indicadores-chave resumidos dos 5 pilares para a tela de entrada da Central de Relatórios.
        """
        today = date.today()
        start_30 = today - timedelta(days=30)

        multichannel = StandardReportsEngine.get_multichannel_performance(start_30, today)
        stock_coverage = StandardReportsEngine.get_stock_coverage_and_abc(start_30, today)
        rfm = StandardReportsEngine.get_rfm_matrix(today)
        dre = StandardReportsEngine.get_dre_statement(start_30, today)
        cash_flow = StandardReportsEngine.get_cash_flow_projection(30)

        return {
            'multichannel': multichannel['summary'],
            'stock_coverage': stock_coverage['summary'],
            'rfm': rfm['summary'],
            'dre': dre['summary'],
            'cash_flow': cash_flow['summary']
        }

