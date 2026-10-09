"""
Módulo de Inteligência Comercial e Filtros de Clientes & CRM para o BlingBI.
Permite segmentação dinâmica de clientes por:
1. Clientes última compra (período selecionado, mês, trimestre, semestre, ano)
2. Melhores Clientes (por faturamento no período selecionado, mês, trimestre, semestre, ano)
3. Clientes com mais produtos comprados (volume de peças no período selecionado, mês, trimestre, semestre, ano)
4. Clientes que não compram há mais tempo (inatividade / churn no período selecionado, mês, trimestre, semestre, ano)
5. Clientes de consignado (malas condicionais no período selecionado, mês, trimestre, semestre, ano)
"""

from datetime import date, datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import func, or_
from app.database import db
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.fashion import ConditionalBag


class CustomerFilterService:

    @classmethod
    def get_filtered_customers(
        cls,
        filter_type: str = 'best_customers',
        period: str = 'last_30_days',
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        state: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa a agregação analítica da base de clientes cruzando pedidos,
        itens comprados e malas condicionais dentro e fora do período selecionado.
        """
        today = date.today()
        if not start_date or not end_date:
            from app.services.bi_analytics import BiAnalytics
            start_date, end_date = BiAnalytics.parse_date_filter(period)

        # ---------------------------------------------------------------------
        # 1. Agregação de Pedidos no Período Selecionado
        # ---------------------------------------------------------------------
        period_orders_query = db.session.query(
            Order.customer_id,
            func.count(Order.id).label('period_orders'),
            func.sum(Order.total).label('period_spent'),
            func.max(Order.order_date).label('period_last_order')
        ).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido',
            Order.customer_id.isnot(None)
        ).group_by(Order.customer_id).all()

        period_orders_map = {
            row.customer_id: {
                'orders': int(row.period_orders or 0),
                'spent': float(row.period_spent or 0.0),
                'last_order': row.period_last_order
            }
            for row in period_orders_query
        }

        # ---------------------------------------------------------------------
        # 2. Agregação de Itens / Peças Compradas no Período Selecionado
        # ---------------------------------------------------------------------
        period_items_query = db.session.query(
            Order.customer_id,
            func.sum(OrderItem.quantity).label('period_items')
        ).join(OrderItem, Order.id == OrderItem.order_id).filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido',
            Order.customer_id.isnot(None)
        ).group_by(Order.customer_id).all()

        period_items_map = {
            row.customer_id: int(row.period_items or 0)
            for row in period_items_query
        }

        # ---------------------------------------------------------------------
        # 3. Estatísticas Históricas Gerais de Cada Cliente (Lifetime)
        # ---------------------------------------------------------------------
        lifetime_query = db.session.query(
            Order.customer_id,
            func.max(Order.order_date).label('overall_last_order'),
            func.count(Order.id).label('lifetime_orders'),
            func.sum(Order.total).label('lifetime_spent')
        ).filter(
            Order.status == 'Atendido',
            Order.customer_id.isnot(None)
        ).group_by(Order.customer_id).all()

        lifetime_map = {
            row.customer_id: {
                'last_order': row.overall_last_order,
                'lifetime_orders': int(row.lifetime_orders or 0),
                'lifetime_spent': float(row.lifetime_spent or 0.0)
            }
            for row in lifetime_query
        }

        # ---------------------------------------------------------------------
        # 4. Agregação de Malas Condicionais (Consignado) no Período
        # ---------------------------------------------------------------------
        bags_period_query = db.session.query(
            ConditionalBag.customer_id,
            func.count(ConditionalBag.id).label('bags_count'),
            func.sum(ConditionalBag.items_sent).label('items_sent'),
            func.sum(ConditionalBag.items_invoiced).label('items_invoiced'),
            func.sum(ConditionalBag.total_invoiced_value).label('invoiced_val')
        ).filter(
            ConditionalBag.sent_date >= start_date,
            ConditionalBag.sent_date <= end_date,
            ConditionalBag.customer_id.isnot(None)
        ).group_by(ConditionalBag.customer_id).all()

        bags_period_map = {
            row.customer_id: {
                'bags_count': int(row.bags_count or 0),
                'items_sent': int(row.items_sent or 0),
                'items_invoiced': int(row.items_invoiced or 0),
                'invoiced_val': float(row.invoiced_val or 0.0)
            }
            for row in bags_period_query
        }

        # Clientes com pedidos de método Consignado no período
        consign_orders_query = db.session.query(
            Order.customer_id,
            func.count(Order.id).label('consign_orders_count'),
            func.sum(Order.total).label('consign_orders_spent')
        ).filter(
            or_(
                func.lower(Order.payment_method).like('%consignad%'),
                func.lower(Order.notes).like('%consignad%'),
                func.lower(Order.channel).like('%consignad%')
            ),
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.customer_id.isnot(None)
        ).group_by(Order.customer_id).all()

        consign_orders_map = {
            row.customer_id: {
                'orders': int(row.consign_orders_count or 0),
                'spent': float(row.consign_orders_spent or 0.0)
            }
            for row in consign_orders_query
        }

        # ---------------------------------------------------------------------
        # 5. Obtenção de Todos os Clientes Cadastrados
        # ---------------------------------------------------------------------
        all_customers = Customer.query.all()
        available_states = sorted(list(set(c.state for c in all_customers if c.state)))

        customer_list: List[Dict[str, Any]] = []

        for cust in all_customers:
            cid = cust.id
            p_data = period_orders_map.get(cid, {'orders': 0, 'spent': 0.0, 'last_order': None})
            p_items = period_items_map.get(cid, 0)
            lt_data = lifetime_map.get(cid, {'last_order': None, 'lifetime_orders': 0, 'lifetime_spent': 0.0})
            b_data = bags_period_map.get(cid, {'bags_count': 0, 'items_sent': 0, 'items_invoiced': 0, 'invoiced_val': 0.0})
            c_ord_data = consign_orders_map.get(cid, {'orders': 0, 'spent': 0.0})

            # Data de última compra global
            last_order_dt = lt_data['last_order']
            if last_order_dt:
                days_since_last = (today - last_order_dt).days
                last_order_str = last_order_dt.strftime('%d/%m/%Y')
                last_order_iso = last_order_dt.strftime('%Y-%m-%d')
            else:
                days_since_last = None
                last_order_str = '-'
                last_order_iso = ''

            # Status de inatividade
            if days_since_last is None:
                inactivity_label = 'Sem Compras'
                inactivity_badge = 'secondary'
            elif days_since_last <= 30:
                inactivity_label = 'Ativo Recente'
                inactivity_badge = 'success'
            elif days_since_last <= 90:
                inactivity_label = 'Atenção (30-90d)'
                inactivity_badge = 'warning'
            elif days_since_last <= 180:
                inactivity_label = 'Inativo (90-180d)'
                inactivity_badge = 'danger'
            else:
                inactivity_label = 'Churn (>180d)'
                inactivity_badge = 'dark'

            orders_cnt = p_data['orders']
            spent_val = round(p_data['spent'], 2)
            avg_ticket = round(spent_val / orders_cnt, 2) if orders_cnt > 0 else 0.0
            avg_item_price = round(spent_val / p_items, 2) if p_items > 0 else 0.0
            pieces_per_order = round(p_items / orders_cnt, 1) if orders_cnt > 0 else 0.0

            # Consignado
            bags_count = b_data['bags_count'] + c_ord_data['orders']
            bags_sent = b_data['items_sent']
            bags_invoiced = b_data['items_invoiced']
            bags_invoiced_val = round(b_data['invoiced_val'] + c_ord_data['spent'], 2)
            bags_conv = round((bags_invoiced / bags_sent * 100), 1) if bags_sent > 0 else 0.0
            has_consign = (bags_count > 0 or bags_sent > 0 or bags_invoiced_val > 0)

            # Sanitização do documento para busca
            doc_raw = cust.document or ''
            doc_clean = "".join(ch for ch in doc_raw if ch.isalnum())
            phone_clean = "".join(ch for ch in (cust.phone or '') if ch.isdigit())

            customer_list.append({
                'id': cust.id,
                'bling_id': cust.bling_id,
                'name': cust.name,
                'document': doc_raw or 'Não informado',
                'document_clean': doc_clean,
                'person_type': cust.person_type or 'F',
                'phone': cust.phone or '',
                'phone_clean': phone_clean,
                'email': cust.email or '',
                'city': cust.city or '',
                'state': cust.state or '',
                'preferred_size': cust.preferred_size or 'M',
                'preferred_style': cust.preferred_style or 'Casual',

                # Métricas do Período
                'period_orders': orders_cnt,
                'period_spent': spent_val,
                'period_items': p_items,
                'period_avg_ticket': avg_ticket,
                'period_avg_item_price': avg_item_price,
                'period_pieces_per_order': pieces_per_order,

                # Última compra & Inatividade
                'last_order_date': last_order_str,
                'last_order_iso': last_order_iso,
                'days_since_last': days_since_last,
                'inactivity_label': inactivity_label,
                'inactivity_badge': inactivity_badge,

                # Histórico Geral
                'lifetime_orders': lt_data['lifetime_orders'],
                'lifetime_spent': round(lt_data['lifetime_spent'], 2),

                # Consignado / Malas
                'has_consignment': has_consign,
                'bags_count': bags_count,
                'bags_items_sent': bags_sent,
                'bags_items_invoiced': bags_invoiced,
                'bags_conversion_rate': bags_conv,
                'bags_invoiced_value': bags_invoiced_val
            })

        # ---------------------------------------------------------------------
        # 6. Aplicação do Filtro de Atributo Estratégico
        # ---------------------------------------------------------------------
        filter_type = filter_type or 'best_customers'

        if filter_type == 'last_purchase':
            # Clientes cuja última compra ocorreu no período selecionado
            filtered = [
                c for c in customer_list
                if c['last_order_iso'] and (start_date.strftime('%Y-%m-%d') <= c['last_order_iso'] <= end_date.strftime('%Y-%m-%d'))
            ]
            default_sort = 'recent_desc'

        elif filter_type == 'best_customers':
            # Clientes com maior faturamento no período
            filtered = [c for c in customer_list if c['period_spent'] > 0]
            default_sort = 'spent_desc'

        elif filter_type == 'most_products':
            # Clientes com mais peças/produtos comprados no período
            filtered = [c for c in customer_list if c['period_items'] > 0]
            default_sort = 'items_desc'

        elif filter_type == 'longest_inactive':
            # Clientes que não compram há mais tempo (sem compras no período ou com última compra antes do período)
            # Ordenados pelos que estão há mais dias sem comprar
            filtered = [
                c for c in customer_list
                if c['period_orders'] == 0 or (c['last_order_iso'] and c['last_order_iso'] < start_date.strftime('%Y-%m-%d'))
            ]
            default_sort = 'inactive_desc'

        elif filter_type == 'consignment':
            # Clientes de consignado no período
            filtered = [c for c in customer_list if c['has_consignment']]
            default_sort = 'consign_val_desc'

        else: # 'all' ou fallback
            filtered = list(customer_list)
            default_sort = 'spent_desc'

        # ---------------------------------------------------------------------
        # 7. Filtros Complementares: Busca Textual e Estado
        # ---------------------------------------------------------------------
        if state and state != 'all':
            filtered = [c for c in filtered if c['state'] == state]

        if search and search.strip():
            s = search.strip().lower()
            s_digits = "".join(ch for ch in s if ch.isdigit())
            res = []
            for c in filtered:
                match = (
                    s in c['name'].lower() or
                    s in c['city'].lower() or
                    s in c['document'].lower() or
                    s in c['email'].lower()
                )
                if not match and s_digits and len(s_digits) >= 3:
                    match = (
                        s_digits in c['document_clean'] or
                        s_digits in c['phone_clean']
                    )
                if match:
                    res.append(c)
            filtered = res

        # ---------------------------------------------------------------------
        # 8. Ordenação dos Resultados
        # ---------------------------------------------------------------------
        active_sort = sort_by or default_sort

        if active_sort == 'spent_desc':
            filtered.sort(key=lambda x: (x['period_spent'], x['lifetime_spent']), reverse=True)
        elif active_sort == 'spent_asc':
            filtered.sort(key=lambda x: x['period_spent'])
        elif active_sort == 'items_desc':
            filtered.sort(key=lambda x: (x['period_items'], x['period_spent']), reverse=True)
        elif active_sort == 'items_asc':
            filtered.sort(key=lambda x: x['period_items'])
        elif active_sort == 'recent_desc':
            filtered.sort(key=lambda x: (x['last_order_iso'] or '1970-01-01'), reverse=True)
        elif active_sort == 'inactive_desc':
            # Clientes com mais dias sem comprar primeiro (None = nunca comprou vem depois ou com valor alto)
            filtered.sort(key=lambda x: (x['days_since_last'] is not None, x['days_since_last'] or -1), reverse=True)
        elif active_sort == 'orders_desc':
            filtered.sort(key=lambda x: (x['period_orders'], x['period_spent']), reverse=True)
        elif active_sort == 'consign_val_desc':
            filtered.sort(key=lambda x: (x['bags_invoiced_value'], x['bags_items_sent']), reverse=True)
        elif active_sort == 'name_asc':
            filtered.sort(key=lambda x: x['name'].lower())

        # ---------------------------------------------------------------------
        # 9. Cálculo dos KPIs e Resumo do Grupo Filtrado
        # ---------------------------------------------------------------------
        total_matching = len(filtered)
        group_revenue = round(sum(c['period_spent'] for c in filtered), 2)
        group_items = sum(c['period_items'] for c in filtered)
        group_orders = sum(c['period_orders'] for c in filtered)
        group_avg_ticket = round(group_revenue / group_orders, 2) if group_orders > 0 else 0.0

        recurring_in_group = sum(1 for c in filtered if c['period_orders'] > 1)
        recurrence_rate = round((recurring_in_group / total_matching * 100), 1) if total_matching > 0 else 0.0

        consign_in_group = sum(1 for c in filtered if c['has_consignment'])

        # Média de dias sem comprar (apenas para quem tem registro)
        inactivity_days_list = [c['days_since_last'] for c in filtered if c['days_since_last'] is not None]
        avg_inactivity_days = round(sum(inactivity_days_list) / len(inactivity_days_list), 1) if inactivity_days_list else 0.0

        # Rótulos legíveis para apresentação
        filter_labels = {
            'last_purchase': 'Clientes Última Compra',
            'best_customers': 'Melhores Clientes (Maior Faturamento)',
            'most_products': 'Clientes com Mais Produtos Comprados',
            'longest_inactive': 'Clientes que Não Compram Há Mais Tempo',
            'consignment': 'Clientes de Consignado (Malas Condicionais)',
            'all': 'Todos os Clientes'
        }

        period_labels = {
            'this_month': 'Este Mês',
            'month': 'Últimos 30 Dias (Mês)',
            'last_30_days': 'Últimos 30 Dias (Mês)',
            'quarter': 'Últimos 90 Dias (Trimestre)',
            'last_90_days': 'Últimos 90 Dias (Trimestre)',
            'semester': 'Últimos 180 Dias (Semestre)',
            'last_180_days': 'Últimos 180 Dias (Semestre)',
            'year': 'Últimos 365 Dias (Ano)',
            'last_365_days': 'Últimos 365 Dias (Ano)',
            'custom': f'Período Customizado ({start_date.strftime("%d/%m/%Y")} a {end_date.strftime("%d/%m/%Y")})',
            'all': 'Histórico Completo'
        }

        filter_options = [
            {
                'id': 'best_customers',
                'label': 'Melhores Clientes',
                'icon': 'star',
                'description': 'Maior volume de faturamento no período'
            },
            {
                'id': 'most_products',
                'label': 'Mais Produtos Comprados',
                'icon': 'shopping-bag',
                'description': 'Maior quantidade de peças/itens comprados'
            },
            {
                'id': 'last_purchase',
                'label': 'Última Compra',
                'icon': 'clock',
                'description': 'Compraram recentemente dentro do período'
            },
            {
                'id': 'longest_inactive',
                'label': 'Não Compram Há Mais Tempo',
                'icon': 'user-x',
                'description': 'Inatividade e risco de churn'
            },
            {
                'id': 'consignment',
                'label': 'Clientes de Consignado',
                'icon': 'archive',
                'description': 'Malas condicionais no período'
            },
            {
                'id': 'all',
                'label': 'Todos os Clientes',
                'icon': 'users',
                'description': 'Visão completa da carteira'
            }
        ]

        return {
            'customers': filtered,
            'summary': {
                'total_customers': total_matching,
                'total_revenue': group_revenue,
                'total_items': group_items,
                'total_orders': group_orders,
                'avg_ticket': group_avg_ticket,
                'recurrence_rate': recurrence_rate,
                'consign_customers_count': consign_in_group,
                'avg_inactivity_days': avg_inactivity_days,
                'total_base_count': len(all_customers)
            },
            'filter_meta': {
                'filter_type': filter_type,
                'filter_label': filter_labels.get(filter_type, 'Clientes'),
                'period': period,
                'period_label': period_labels.get(period, f'{start_date.strftime("%d/%m/%Y")} a {end_date.strftime("%d/%m/%Y")}'),
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'search': search or '',
                'state': state or 'all',
                'sort_by': active_sort
            },
            'available_states': available_states,
            'available_filter_types': filter_options
        }
