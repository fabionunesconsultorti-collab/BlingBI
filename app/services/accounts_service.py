"""
Módulo de Gestão de Contas a Pagar e Contas a Receber para o BlingBI.
Fornece:
1. Consultas analíticas e filtragens padronizadas por tipo, situação, período, categoria e favorecido.
2. Cálculo de métricas e KPIs consolidados (Total a Pagar, Total a Receber, Saldo Projetado, Inadimplência, Alertas).
3. Agrupamento para Calendário Interativo de Vencimentos Diários, Semanais e Mensais.
4. Liquidação e Baixa Direta de Lançamentos pelo BI com estorno e sincronização Bling.
5. Criação e edição de lançamentos avulsos manuais.
"""

import calendar
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, or_, and_, desc, asc
from app.database import db
from app.models.financial import FinancialEntry

logger = logging.getLogger(__name__)


class ServiceResult(dict):
    """
    Estrutura de retorno dual: opera como dicionário e como tupla desempacotável.
    Permite:
        res['success'], res['message'], res['entry']
    E também:
        success, msg, entry = res
        success, msg = res
    """
    def __iter__(self):
        if 'entry' in self:
            return iter((self['success'], self['message'], self['entry']))
        return iter((self['success'], self['message']))


class AccountsService:

    @classmethod
    def get_accounts_data(cls, filters: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """
        Executa a busca filtrada e paginada de lançamentos financeiros.
        """
        filters = filters or {}
        query = db.session.query(FinancialEntry)

        # 1. Filtro por Tipo (PAGAR / RECEBER / TODOS)
        entry_type = (filters.get('entry_type') or filters.get('type') or 'TODOS').upper()
        if entry_type in ('PAGAR', 'RECEBER'):
            query = query.filter(FinancialEntry.entry_type == entry_type)

        # 2. Filtro por Situação (Pendente, Pago, Atrasado, Cancelado, TODOS)
        status = filters.get('status') or 'TODOS'
        today = date.today()
        if status == 'Pendente':
            query = query.filter(FinancialEntry.status == 'Pendente', FinancialEntry.due_date >= today)
        elif status == 'Atrasado':
            query = query.filter(
                or_(
                    FinancialEntry.status == 'Atrasado',
                    and_(FinancialEntry.status == 'Pendente', FinancialEntry.due_date < today)
                )
            )
        elif status in ('Pago', 'Cancelado'):
            query = query.filter(FinancialEntry.status == status)
        elif status == 'EM_ABERTO':
            query = query.filter(FinancialEntry.status.in_(['Pendente', 'Atrasado']))

        # 3. Campo de Data Base (vencimento, emissão ou pagamento)
        date_field_name = filters.get('date_basis') or filters.get('date_field') or 'due_date'
        date_col = FinancialEntry.due_date
        if date_field_name == 'issue_date':
            date_col = FinancialEntry.issue_date
        elif date_field_name == 'payment_date':
            date_col = FinancialEntry.payment_date

        # 4. Filtro por Período
        period = filters.get('period', 'all')
        if period == 'today':
            query = query.filter(date_col == today)
        elif period == 'yesterday':
            query = query.filter(date_col == today - timedelta(days=1))
        elif period == 'tomorrow':
            query = query.filter(date_col == today + timedelta(days=1))
        elif period == 'this_week':
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            query = query.filter(date_col >= start_week, date_col <= end_week)
        elif period in ('next_7_days', 'last_7_days'):
            if period == 'next_7_days':
                query = query.filter(date_col >= today, date_col <= today + timedelta(days=7))
            else:
                query = query.filter(date_col >= today - timedelta(days=7), date_col <= today)
        elif period == 'next_15_days':
            query = query.filter(date_col >= today, date_col <= today + timedelta(days=15))
        elif period in ('this_month', 'month'):
            start_month = today.replace(day=1)
            _, last_day = calendar.monthrange(today.year, today.month)
            end_month = today.replace(day=last_day)
            query = query.filter(date_col >= start_month, date_col <= end_month)
        elif period == 'next_month':
            cal_month = today.month + 1
            cal_year = today.year
            if cal_month > 12:
                cal_month = 1
                cal_year += 1
            start_next = date(cal_year, cal_month, 1)
            _, last_next_day = calendar.monthrange(cal_year, cal_month)
            end_next = date(cal_year, cal_month, last_next_day)
            query = query.filter(date_col >= start_next, date_col <= end_next)
        elif period == 'last_month':
            first_this_month = today.replace(day=1)
            last_day_prev = first_this_month - timedelta(days=1)
            first_prev = last_day_prev.replace(day=1)
            query = query.filter(date_col >= first_prev, date_col <= last_day_prev)
        elif period == 'overdue':
            query = query.filter(FinancialEntry.due_date < today, FinancialEntry.status.in_(['Pendente', 'Atrasado']))
        elif period == 'custom' or (filters.get('start_date') and filters.get('end_date') and period != 'all'):
            s_date = filters.get('start_date')
            e_date = filters.get('end_date')
            if s_date:
                if isinstance(s_date, str):
                    try:
                        s_date = datetime.strptime(s_date[:10], '%Y-%m-%d').date()
                    except Exception:
                        s_date = None
                if s_date:
                    query = query.filter(date_col >= s_date)
            if e_date:
                if isinstance(e_date, str):
                    try:
                        e_date = datetime.strptime(e_date[:10], '%Y-%m-%d').date()
                    except Exception:
                        e_date = None
                if e_date:
                    query = query.filter(date_col <= e_date)

        # 5. Filtro por Categoria
        category = filters.get('category')
        if category and category not in ('ALL', 'all', 'TODOS', 'todos'):
            query = query.filter(FinancialEntry.category == category)

        # 6. Filtro por Meio de Pagamento
        payment_method = filters.get('payment_method')
        if payment_method and payment_method not in ('ALL', 'all', 'TODOS', 'todos'):
            query = query.filter(FinancialEntry.payment_method == payment_method)

        # 7. Busca Textual Geral (descrição, pessoa, id)
        q = filters.get('search') or filters.get('q')
        if q:
            q_clean = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    FinancialEntry.description.ilike(q_clean),
                    FinancialEntry.entity_name.ilike(q_clean),
                    FinancialEntry.category.ilike(q_clean),
                    FinancialEntry.payment_method.ilike(q_clean),
                    FinancialEntry.bling_id.cast(db.String).ilike(q_clean)
                )
            )

        # 8. Ordenação
        sort_by = filters.get('sort_by', 'due_date')
        sort_dir = filters.get('sort_dir', 'asc')

        order_col = FinancialEntry.due_date
        if sort_by == 'amount':
            order_col = FinancialEntry.amount
        elif sort_by == 'entity_name':
            order_col = FinancialEntry.entity_name
        elif sort_by == 'issue_date':
            order_col = FinancialEntry.issue_date
        elif sort_by == 'status':
            order_col = FinancialEntry.status
        elif sort_by == 'entry_type':
            order_col = FinancialEntry.entry_type

        if sort_dir == 'desc':
            query = query.order_by(desc(order_col), desc(FinancialEntry.id))
        else:
            query = query.order_by(asc(order_col), asc(FinancialEntry.id))

        total_count = query.count()
        page = max(1, page)
        per_page = max(1, min(10000, per_page))
        entries = query.offset((page - 1) * per_page).limit(per_page).all()
        total_pages = max(1, (total_count + per_page - 1) // per_page)

        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1,
            'next_num': page + 1
        }

        return {
            'entries': entries,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'pagination': pagination
        }

    @classmethod
    def get_summary_metrics(cls, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calcula as métricas e indicadores de desempenho (KPIs) para o dashboard
        e compõe os alertas de vencimento diários, semanais e mensais.
        """
        today = date.today()

        # Totais Gerais
        tot_rec = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'RECEBER', FinancialEntry.status != 'Cancelado').scalar() or 0.0

        rec_paid = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'RECEBER', FinancialEntry.status == 'Pago').scalar() or 0.0

        rec_pending = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'RECEBER', FinancialEntry.status == 'Pendente', FinancialEntry.due_date >= today).scalar() or 0.0

        rec_overdue = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(
                FinancialEntry.entry_type == 'RECEBER',
                or_(
                    FinancialEntry.status == 'Atrasado',
                    and_(FinancialEntry.status == 'Pendente', FinancialEntry.due_date < today)
                )
            ).scalar() or 0.0

        tot_pay = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'PAGAR', FinancialEntry.status != 'Cancelado').scalar() or 0.0

        pay_paid = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'PAGAR', FinancialEntry.status == 'Pago').scalar() or 0.0

        pay_pending = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'PAGAR', FinancialEntry.status == 'Pendente', FinancialEntry.due_date >= today).scalar() or 0.0

        pay_overdue = db.session.query(func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(
                FinancialEntry.entry_type == 'PAGAR',
                or_(
                    FinancialEntry.status == 'Atrasado',
                    and_(FinancialEntry.status == 'Pendente', FinancialEntry.due_date < today)
                )
            ).scalar() or 0.0

        # Alertas de Vencimento
        # 1. Vencendo HOJE
        due_today_pay_q = db.session.query(func.count(FinancialEntry.id), func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'PAGAR', FinancialEntry.due_date == today, FinancialEntry.status.in_(['Pendente', 'Atrasado']))
        due_today_pay_count, due_today_pay_val = due_today_pay_q.first() or (0, 0.0)

        due_today_rec_q = db.session.query(func.count(FinancialEntry.id), func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'RECEBER', FinancialEntry.due_date == today, FinancialEntry.status.in_(['Pendente', 'Atrasado']))
        due_today_rec_count, due_today_rec_val = due_today_rec_q.first() or (0, 0.0)

        # 2. Vencendo na SEMANA (próximos 7 dias)
        week_end = today + timedelta(days=7)
        due_week_pay_q = db.session.query(func.count(FinancialEntry.id), func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'PAGAR', FinancialEntry.due_date >= today, FinancialEntry.due_date <= week_end, FinancialEntry.status.in_(['Pendente', 'Atrasado']))
        due_week_pay_count, due_week_pay_val = due_week_pay_q.first() or (0, 0.0)

        due_week_rec_q = db.session.query(func.count(FinancialEntry.id), func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'RECEBER', FinancialEntry.due_date >= today, FinancialEntry.due_date <= week_end, FinancialEntry.status.in_(['Pendente', 'Atrasado']))
        due_week_rec_count, due_week_rec_val = due_week_rec_q.first() or (0, 0.0)

        # 3. Vencendo no MÊS corrente
        _, month_last_day = calendar.monthrange(today.year, today.month)
        month_end = today.replace(day=month_last_day)

        due_month_pay_q = db.session.query(func.count(FinancialEntry.id), func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'PAGAR', FinancialEntry.due_date >= today, FinancialEntry.due_date <= month_end, FinancialEntry.status.in_(['Pendente', 'Atrasado']))
        due_month_pay_count, due_month_pay_val = due_month_pay_q.first() or (0, 0.0)

        due_month_rec_q = db.session.query(func.count(FinancialEntry.id), func.coalesce(func.sum(FinancialEntry.amount), 0.0))\
            .filter(FinancialEntry.entry_type == 'RECEBER', FinancialEntry.due_date >= today, FinancialEntry.due_date <= month_end, FinancialEntry.status.in_(['Pendente', 'Atrasado']))
        due_month_rec_count, due_month_rec_val = due_month_rec_q.first() or (0, 0.0)

        # Contagens de Vencidos/Atrasados gerais
        overdue_pay_count = db.session.query(func.count(FinancialEntry.id))\
            .filter(
                FinancialEntry.entry_type == 'PAGAR',
                or_(FinancialEntry.status == 'Atrasado', and_(FinancialEntry.status == 'Pendente', FinancialEntry.due_date < today))
            ).scalar() or 0

        overdue_rec_count = db.session.query(func.count(FinancialEntry.id))\
            .filter(
                FinancialEntry.entry_type == 'RECEBER',
                or_(FinancialEntry.status == 'Atrasado', and_(FinancialEntry.status == 'Pendente', FinancialEntry.due_date < today))
            ).scalar() or 0

        net_projected = tot_rec - tot_pay
        net_realized = rec_paid - pay_paid
        net_pending = (rec_pending + rec_overdue) - (pay_pending + pay_overdue)
        default_rate = (rec_overdue / tot_rec * 100.0) if tot_rec > 0 else 0.0

        count_rec_pending = db.session.query(func.count(FinancialEntry.id))\
            .filter(FinancialEntry.entry_type == 'RECEBER', FinancialEntry.status.in_(['Pendente', 'Atrasado'])).scalar() or 0

        count_pay_pending = db.session.query(func.count(FinancialEntry.id))\
            .filter(FinancialEntry.entry_type == 'PAGAR', FinancialEntry.status.in_(['Pendente', 'Atrasado'])).scalar() or 0

        return {
            # Chaves canônicas para templates e relatórios
            'total_receber_pending': rec_pending + rec_overdue,
            'total_receber_paid': rec_paid,
            'total_receber': tot_rec,
            'count_receber_pending': count_rec_pending,

            'total_pagar_pending': pay_pending + pay_overdue,
            'total_pagar_paid': pay_paid,
            'total_pagar': tot_pay,
            'count_pagar_pending': count_pay_pending,

            'saldo_pending': net_pending,
            'saldo_paid': net_realized,
            'saldo_total': net_projected,

            'total_overdue': rec_overdue + pay_overdue,
            'count_overdue': overdue_rec_count + overdue_pay_count,
            'rate_overdue': round(default_rate, 2),

            'count_today': due_today_pay_count + due_today_rec_count,
            'total_today': float(due_today_pay_val or 0.0) + float(due_today_rec_val or 0.0),

            'count_week': due_week_pay_count + due_week_rec_count,
            'total_week': float(due_week_pay_val or 0.0) + float(due_week_rec_val or 0.0),

            'count_month': due_month_pay_count + due_month_rec_count,
            'total_month': float(due_month_pay_val or 0.0) + float(due_month_rec_val or 0.0),

            # Chaves legadas mantidas para compatibilidade
            'total_receivable': tot_rec,
            'rec_paid': rec_paid,
            'rec_pending': rec_pending,
            'rec_overdue': rec_overdue,
            'total_payable': tot_pay,
            'pay_paid': pay_paid,
            'pay_pending': pay_pending,
            'pay_overdue': pay_overdue,
            'net_projected': net_projected,
            'net_realized': net_realized,
            'net_pending': net_pending,
            'default_rate': round(default_rate, 2),

            'due_today_pay_count': due_today_pay_count,
            'due_today_pay_val': float(due_today_pay_val or 0.0),
            'due_today_rec_count': due_today_rec_count,
            'due_today_rec_val': float(due_today_rec_val or 0.0),
            'due_week_pay_count': due_week_pay_count,
            'due_week_pay_val': float(due_week_pay_val or 0.0),
            'due_week_rec_count': due_week_rec_count,
            'due_week_rec_val': float(due_week_rec_val or 0.0),
            'due_month_pay_count': due_month_pay_count,
            'due_month_pay_val': float(due_month_pay_val or 0.0),
            'due_month_rec_count': due_month_rec_count,
            'due_month_rec_val': float(due_month_rec_val or 0.0),
            'overdue_pay_count': overdue_pay_count,
            'overdue_rec_count': overdue_rec_count,
        }

    @classmethod
    def get_calendar_events(cls, year: Optional[int] = None, month: Optional[int] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Gera a estrutura de grade do calendário para o mês/ano especificado,
        agrupando as contas a pagar e receber por dia de vencimento.
        """
        today = date.today()
        cal_year = year or today.year
        cal_month = month or today.month

        # Garante limites válidos de mês
        if cal_month < 1:
            cal_month = 12
            cal_year -= 1
        elif cal_month > 12:
            cal_month = 1
            cal_year += 1

        _, num_days = calendar.monthrange(cal_year, cal_month)
        first_day_date = date(cal_year, cal_month, 1)
        last_day_date = date(cal_year, cal_month, num_days)

        # Consulta todos os lançamentos do mês
        query = db.session.query(FinancialEntry).filter(
            FinancialEntry.due_date >= first_day_date,
            FinancialEntry.due_date <= last_day_date,
            FinancialEntry.status != 'Cancelado'
        )

        # Aplica filtro de tipo se especificado
        if filters:
            e_type = (filters.get('entry_type') or filters.get('type') or '').upper()
            if e_type in ('PAGAR', 'RECEBER'):
                query = query.filter(FinancialEntry.entry_type == e_type)

        entries = query.order_by(FinancialEntry.due_date.asc(), FinancialEntry.amount.desc()).all()

        # Dicionário indexado por dia
        day_map: Dict[int, Dict[str, Any]] = {}
        for d in range(1, num_days + 1):
            curr_date = date(cal_year, cal_month, d)
            day_map[d] = {
                'day': d,
                'date': curr_date,
                'date_str': curr_date.strftime('%Y-%m-%d'),
                'is_current_month': True,
                'is_today': (curr_date == today),
                'is_past': (curr_date < today),
                'pay_amount': 0.0,
                'pay_count': 0,
                'rec_amount': 0.0,
                'rec_count': 0,
                'has_overdue': False,
                'entries': []
            }

        for e in entries:
            d = e.due_date.day
            if d in day_map:
                if e.entry_type == 'PAGAR':
                    day_map[d]['pay_amount'] += e.amount
                    day_map[d]['pay_count'] += 1
                elif e.entry_type == 'RECEBER':
                    day_map[d]['rec_amount'] += e.amount
                    day_map[d]['rec_count'] += 1

                if e.status in ('Pendente', 'Atrasado') and e.due_date < today:
                    day_map[d]['has_overdue'] = True

                if len(day_map[d]['entries']) < 6:
                    day_map[d]['entries'].append({
                        'id': e.id,
                        'type': e.entry_type,
                        'description': e.description,
                        'amount': e.amount,
                        'status': e.status,
                        'entity': e.entity_name or ''
                    })

        # Monta a matriz de semanas para exibição na grade HTML (Domingo = 0)
        cal = calendar.Calendar(firstweekday=6) # 6 = Domingo
        weeks = []
        for week in cal.monthdayscalendar(cal_year, cal_month):
            week_days = []
            for day_num in week:
                if day_num == 0:
                    week_days.append({
                        'day': '',
                        'is_current_month': False,
                        'is_today': False,
                        'is_past': False,
                        'pay_amount': 0.0,
                        'pay_count': 0,
                        'rec_amount': 0.0,
                        'rec_count': 0,
                        'has_overdue': False,
                        'count_receber': 0,
                        'count_pagar': 0,
                        'count_total': 0,
                        'receber': 0.0,
                        'pagar': 0.0,
                        'entries': []
                    })
                else:
                    d_info = day_map.get(day_num, {})
                    d_info['is_current_month'] = True
                    d_info['count_receber'] = d_info.get('rec_count', 0)
                    d_info['count_pagar'] = d_info.get('pay_count', 0)
                    d_info['count_total'] = d_info.get('rec_count', 0) + d_info.get('pay_count', 0)
                    d_info['receber'] = d_info.get('rec_amount', 0.0)
                    d_info['pagar'] = d_info.get('pay_amount', 0.0)
                    week_days.append(d_info)
            weeks.append(week_days)

        # Meses de navegação
        prev_month = cal_month - 1
        prev_year = cal_year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1

        next_month = cal_month + 1
        next_year = cal_year
        if next_month > 12:
            next_month = 1
            next_year += 1

        month_names_pt = [
            '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
        ]

        tot_m_pay = sum(d['pay_amount'] for d in day_map.values())
        tot_m_rec = sum(d['rec_amount'] for d in day_map.values())

        return {
            'year': cal_year,
            'month': cal_month,
            'month_name': month_names_pt[cal_month],
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'weeks': weeks,
            'total_month_pay': tot_m_pay,
            'total_month_rec': tot_m_rec,
            'month_totals': {
                'receber': tot_m_rec,
                'pagar': tot_m_pay
            },
            'month_start': first_day_date,
            'month_end': last_day_date
        }

    @classmethod
    def settle_entry(cls, entry_id: int, payment_date: Optional[Any] = None, payment_method: Optional[str] = None,
                     notes: Optional[str] = None, discount: Optional[float] = None, fine_fee: Optional[float] = None,
                     amount_paid: Optional[float] = None) -> ServiceResult:
        """
        Liquida/baixa uma conta a pagar ou receber diretamente pelo BI.
        Atualiza o status para 'Pago', carimba a data de pagamento e registra observações.
        Tenta também sincronizar a baixa com o Bling ERP se a integração estiver ativa.
        """
        entry = FinancialEntry.query.get(entry_id)
        if not entry:
            return ServiceResult(success=False, message=f'Lançamento #{entry_id} não encontrado.', entry=None)

        if payment_date:
            if isinstance(payment_date, str):
                try:
                    pay_dt = datetime.strptime(payment_date[:10], '%Y-%m-%d').date()
                except Exception:
                    pay_dt = date.today()
            else:
                pay_dt = payment_date
        else:
            pay_dt = date.today()

        entry.status = 'Pago'
        entry.payment_date = pay_dt
        if payment_method:
            entry.payment_method = payment_method
        if notes:
            current_notes = entry.notes or ''
            entry.notes = f"{current_notes}\n[Baixa em {pay_dt.strftime('%d/%m/%Y')}]: {notes}".strip()

        if discount is not None:
            try:
                entry.discount = float(discount or 0.0)
            except Exception:
                pass
        if fine_fee is not None:
            try:
                entry.fine_fee = float(fine_fee or 0.0)
            except Exception:
                pass

        if amount_paid is not None and float(amount_paid or 0.0) > 0:
            diff = float(amount_paid) - entry.amount
            if diff > 0:
                entry.fine_fee = (entry.fine_fee or 0.0) + diff
            elif diff < 0:
                entry.discount = (entry.discount or 0.0) + abs(diff)

        entry.updated_at = datetime.utcnow()
        db.session.commit()

        # Tentativa graciosa de sincronizar baixa no Bling API v3 se configurado
        bling_msg = ''
        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if client.is_configured() and entry.bling_id and entry.bling_id < 9000000000:
                endpoint = f"/contas/pagar/{entry.bling_id}/baixar" if entry.entry_type == 'PAGAR' else f"/contas/receber/{entry.bling_id}/baixar"
                resp = client.request('POST', endpoint, json={
                    'data': pay_dt.strftime('%Y-%m-%d'),
                    'valor': entry.net_amount
                })
                if resp and resp.status_code in (200, 201):
                    bling_msg = ' (sincronizado no Bling ERP)'
        except Exception as e:
            logger.debug(f"[AccountsService] Aviso ao sincronizar baixa no Bling: {e}")

        return ServiceResult(
            success=True,
            message=f'Lançamento #{entry.id} ({entry.description}) baixado com sucesso!{bling_msg}',
            entry=entry
        )

    @classmethod
    def unsettle_entry(cls, entry_id: int) -> ServiceResult:
        """
        Reverte/estorna a liquidação de um título, retornando para 'Pendente'.
        """
        entry = FinancialEntry.query.get(entry_id)
        if not entry:
            return ServiceResult(success=False, message=f'Lançamento #{entry_id} não encontrado.', entry=None)

        entry.status = 'Pendente'
        entry.payment_date = None
        entry.updated_at = datetime.utcnow()
        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Baixa do lançamento #{entry.id} estornada com sucesso. Título retornado para Pendente.',
            entry=entry
        )

    @classmethod
    def create_entry(cls, data: Dict[str, Any]) -> ServiceResult:
        """
        Cria um novo lançamento avulso diretamente pelo BlingBI.
        """
        entry_type = (data.get('entry_type') or 'PAGAR').upper()
        description = (data.get('description') or '').strip()
        if not description:
            return ServiceResult(success=False, message='A descrição do lançamento é obrigatória.', entry=None)

        try:
            amount = float(data.get('amount') or 0.0)
        except (ValueError, TypeError):
            amount = 0.0
        if amount <= 0:
            return ServiceResult(success=False, message='O valor do lançamento deve ser maior que zero.', entry=None)

        due_date_raw = data.get('due_date')
        if not due_date_raw:
            return ServiceResult(success=False, message='A data de vencimento é obrigatória.', entry=None)

        if isinstance(due_date_raw, str):
            due_dt = datetime.strptime(due_date_raw[:10], '%Y-%m-%d').date()
        else:
            due_dt = due_date_raw

        issue_date_raw = data.get('issue_date')
        if issue_date_raw:
            issue_dt = datetime.strptime(issue_date_raw[:10], '%Y-%m-%d').date() if isinstance(issue_date_raw, str) else issue_date_raw
        else:
            issue_dt = date.today()

        # Gera ID sintético caso não venha do Bling (prefixo 999xxxxxx)
        synthetic_id = int(datetime.utcnow().timestamp() * 1000)
        while FinancialEntry.query.filter_by(bling_id=synthetic_id).first():
            synthetic_id += 1

        status = data.get('status', 'Pendente')
        payment_date = None
        if status == 'Pago':
            p_date_raw = data.get('payment_date')
            payment_date = datetime.strptime(p_date_raw[:10], '%Y-%m-%d').date() if p_date_raw else date.today()

        payee = data.get('payee_payer') or data.get('entity_name') or ('Fornecedor' if entry_type == 'PAGAR' else 'Cliente')

        entry = FinancialEntry(
            bling_id=synthetic_id,
            entry_type=entry_type,
            description=description,
            entity_name=payee,
            category=data.get('category') or 'Operacional',
            amount=amount,
            issue_date=issue_dt,
            due_date=due_dt,
            payment_date=payment_date,
            status=status,
            payment_method=data.get('payment_method') or 'Boleto',
            notes=data.get('notes'),
            discount=float(data.get('discount', 0.0) or 0.0),
            fine_fee=float(data.get('fine_fee', 0.0) or 0.0)
        )
        db.session.add(entry)
        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Novo lançamento de {entry_type} criado com sucesso!',
            entry=entry
        )

    @classmethod
    def update_entry(cls, entry_id: int, data: Dict[str, Any]) -> ServiceResult:
        """
        Atualiza dados de um lançamento existente.
        """
        entry = FinancialEntry.query.get(entry_id)
        if not entry:
            return ServiceResult(success=False, message=f'Lançamento #{entry_id} não encontrado.', entry=None)

        if 'description' in data and data['description']:
            entry.description = data['description'].strip()
        if 'payee_payer' in data:
            entry.entity_name = (data['payee_payer'] or '').strip()
        elif 'entity_name' in data:
            entry.entity_name = (data['entity_name'] or '').strip()
        if 'category' in data and data['category']:
            entry.category = data['category'].strip()
        if 'amount' in data and float(data['amount'] or 0.0) > 0:
            entry.amount = float(data['amount'])
        if 'payment_method' in data:
            entry.payment_method = data['payment_method']
        if 'notes' in data:
            entry.notes = data['notes']
        if 'status' in data:
            entry.status = data['status']

        if 'due_date' in data and data['due_date']:
            raw_d = data['due_date']
            entry.due_date = datetime.strptime(raw_d[:10], '%Y-%m-%d').date() if isinstance(raw_d, str) else raw_d

        if 'issue_date' in data and data['issue_date']:
            raw_i = data['issue_date']
            entry.issue_date = datetime.strptime(raw_i[:10], '%Y-%m-%d').date() if isinstance(raw_i, str) else raw_i

        entry.updated_at = datetime.utcnow()
        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Lançamento #{entry.id} atualizado com sucesso.',
            entry=entry
        )

    @classmethod
    def delete_entry(cls, entry_id: int) -> ServiceResult:
        """
        Exclui permanentemente um lançamento financeiro.
        """
        entry = FinancialEntry.query.get(entry_id)
        if not entry:
            return ServiceResult(success=False, message=f'Lançamento #{entry_id} não encontrado.')

        desc_txt = entry.description
        db.session.delete(entry)
        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Lançamento #{entry_id} ("{desc_txt}") excluído com sucesso.'
        )

    @classmethod
    def get_filter_options(cls) -> Dict[str, List[str]]:
        """
        Retorna as opções disponíveis para preenchimento dos filtros no frontend.
        """
        categories = [r[0] for r in db.session.query(FinancialEntry.category).distinct().filter(FinancialEntry.category != None).all() if r[0]]
        methods = [r[0] for r in db.session.query(FinancialEntry.payment_method).distinct().filter(FinancialEntry.payment_method != None).all() if r[0]]

        default_cats = ['Operacional', 'Fornecedores', 'Impostos', 'Logística', 'Taxas Financeiras', 'Vendas Mercado Livre', 'Vendas Shopee', 'Vendas Site']
        for c in default_cats:
            if c not in categories:
                categories.append(c)

        default_methods = ['Boleto', 'Pix', 'Cartão de Crédito', 'Cartão de Débito', 'Transferência', 'Dinheiro']
        for m in default_methods:
            if m not in methods:
                methods.append(m)

        return {
            'categories': sorted(categories),
            'payment_methods': sorted(methods)
        }
