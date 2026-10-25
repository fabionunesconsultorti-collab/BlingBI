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

        # 3. Campo de Data Base (vencimento, emissão, competência ou pagamento)
        date_field_name = filters.get('date_basis') or filters.get('date_field') or 'due_date'
        date_col = FinancialEntry.due_date
        if date_field_name == 'issue_date':
            date_col = FinancialEntry.issue_date
        elif date_field_name == 'payment_date':
            date_col = FinancialEntry.payment_date
        elif date_field_name == 'competence_date':
            date_col = FinancialEntry.competence_date

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
        elif sort_by == 'competence_date':
            order_col = FinancialEntry.competence_date
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
                     amount_paid: Optional[float] = None, bling_payment_method_id: Optional[int] = None) -> ServiceResult:
        """
        Liquida/baixa uma conta a pagar ou receber diretamente pelo BI.
        Atualiza o status para 'Pago', carimba a data de pagamento e registra observações.
        Espelha fielmente a baixa no Bling ERP através da API v3 e registra o sync_status.
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
        if bling_payment_method_id:
            try:
                entry.bling_payment_method_id = int(bling_payment_method_id)
            except Exception:
                pass

        if notes and str(notes).strip():
            clean_notes = str(notes).strip()
            current_notes = (entry.notes or '').strip()
            if clean_notes != current_notes and "[Baixa em" not in clean_notes:
                entry.notes = f"{current_notes}\n[Baixa em {pay_dt.strftime('%d/%m/%Y')}]: {clean_notes}".strip()
            elif not current_notes:
                entry.notes = clean_notes

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

        # Espelhamento da baixa no Bling ERP (API v3)
        bling_msg = ''
        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if client.is_configured() and entry.bling_id and entry.bling_id < 9000000000:
                payload = {
                    'data': pay_dt.strftime('%Y-%m-%d'),
                    'dataPagamento': pay_dt.strftime('%Y-%m-%d'),
                    'valor': float(entry.net_amount),
                    'valorPago': float(entry.net_amount),
                    'valorRecebido': float(entry.net_amount),
                    'historico': notes or f"Baixa via BlingBI em {pay_dt.strftime('%d/%m/%Y')}"
                }
                if entry.bling_payment_method_id:
                    payload['idFormaPagamento'] = int(entry.bling_payment_method_id)
                    payload['formaPagamento'] = {'id': int(entry.bling_payment_method_id)}
                if entry.discount and entry.discount > 0:
                    payload['desconto'] = float(entry.discount)
                if entry.fine_fee and entry.fine_fee > 0:
                    payload['juros'] = float(entry.fine_fee)

                if entry.entry_type == 'PAGAR':
                    ok, msg, _ = client.settle_payable(entry.bling_id, payload)
                else:
                    ok, msg, _ = client.settle_receivable(entry.bling_id, payload)

                if ok:
                    entry.sync_status = 'synced'
                    entry.last_sync_at = datetime.utcnow()
                    entry.sync_error_msg = None
                    bling_msg = ' (espelhado no Bling ERP com sucesso)'
                else:
                    entry.sync_status = 'sync_error'
                    entry.sync_error_msg = msg
                    bling_msg = f' (Aviso Bling: {msg})'
            else:
                if not entry.bling_id or entry.bling_id >= 9000000000:
                    entry.sync_status = 'local_only'
        except Exception as e:
            logger.warning(f"[AccountsService] Erro ao sincronizar baixa no Bling: {e}")
            entry.sync_status = 'sync_error'
            entry.sync_error_msg = str(e)
            bling_msg = f' (Erro Bling: {str(e)})'

        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Lançamento #{entry.id} ({entry.description}) baixado com sucesso!{bling_msg}',
            entry=entry
        )

    @classmethod
    def unsettle_entry(cls, entry_id: int) -> ServiceResult:
        """
        Reverte/estorna a liquidação de um título, retornando para 'Pendente'.
        Restabelece a situação para em aberto no Bling ERP via API.
        """
        entry = FinancialEntry.query.get(entry_id)
        if not entry:
            return ServiceResult(success=False, message=f'Lançamento #{entry_id} não encontrado.', entry=None)

        entry.status = 'Pendente'
        entry.payment_date = None
        entry.updated_at = datetime.utcnow()

        bling_msg = ''
        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if client.is_configured() and entry.bling_id and entry.bling_id < 9000000000:
                ok, msg = client.unsettle_account(entry.entry_type, entry.bling_id)
                if ok:
                    entry.sync_status = 'synced'
                    entry.last_sync_at = datetime.utcnow()
                    entry.sync_error_msg = None
                    bling_msg = ' (estorno espelhado no Bling ERP)'
                else:
                    entry.sync_status = 'sync_error'
                    entry.sync_error_msg = msg
                    bling_msg = f' (Aviso Bling: {msg})'
            else:
                if not entry.bling_id or entry.bling_id >= 9000000000:
                    entry.sync_status = 'local_only'
        except Exception as e:
            logger.warning(f"[AccountsService] Erro ao estornar no Bling: {e}")
            entry.sync_status = 'sync_error'
            entry.sync_error_msg = str(e)
            bling_msg = f' (Erro Bling: {str(e)})'

        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Baixa do lançamento #{entry.id} estornada com sucesso. Título retornado para Pendente.{bling_msg}',
            entry=entry
        )

    @classmethod
    def create_entry(cls, data: Dict[str, Any]) -> ServiceResult:
        """
        Cria um novo lançamento avulso diretamente pelo BlingBI e espelha no Bling ERP via API v3.
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

        # Evita criar novo título se for edição ou se já existir lançamento correspondente
        existing = None
        if data.get('entry_id'):
            try:
                existing = db.session.get(FinancialEntry, int(data['entry_id']))
            except Exception:
                pass

        if not existing and data.get('bling_id'):
            try:
                b_val = int(data['bling_id'])
                if b_val and b_val < 9000000000:
                    existing = FinancialEntry.query.filter_by(bling_id=b_val, entry_type=entry_type).first()
            except Exception:
                pass

        if not existing:
            # Checa duplicidade por chave natural (tipo, descrição, valor e vencimento)
            existing = FinancialEntry.query.filter(
                FinancialEntry.entry_type == entry_type,
                FinancialEntry.description == description,
                FinancialEntry.amount == amount,
                FinancialEntry.due_date == due_dt
            ).order_by(FinancialEntry.id.desc()).first()

        if existing:
            return cls.update_entry(existing.id, data)

        issue_date_raw = data.get('issue_date')
        if issue_date_raw:
            issue_dt = datetime.strptime(issue_date_raw[:10], '%Y-%m-%d').date() if isinstance(issue_date_raw, str) else issue_date_raw
        else:
            issue_dt = date.today()

        status = data.get('status', 'Pendente')
        payment_date = None
        if status == 'Pago':
            p_date_raw = data.get('payment_date')
            payment_date = datetime.strptime(p_date_raw[:10], '%Y-%m-%d').date() if p_date_raw else date.today()

        payee = data.get('payee_payer') or data.get('entity_name') or ('Fornecedor' if entry_type == 'PAGAR' else 'Cliente')

        # Vínculos adicionais com IDs do Bling
        bling_contact_id = data.get('bling_contact_id')
        if bling_contact_id:
            try:
                bling_contact_id = int(bling_contact_id)
            except Exception:
                bling_contact_id = None

        bling_category_id = data.get('bling_category_id')
        if bling_category_id:
            try:
                bling_category_id = int(bling_category_id)
            except Exception:
                bling_category_id = None

        bling_pm_id = data.get('bling_payment_method_id')
        if bling_pm_id:
            try:
                bling_pm_id = int(bling_pm_id)
            except Exception:
                bling_pm_id = None

        # Data de competência: se não informada, assume a data de emissão ou vencimento
        competence_date_raw = data.get('competence_date')
        if competence_date_raw:
            comp_dt = datetime.strptime(competence_date_raw[:10], '%Y-%m-%d').date() if isinstance(competence_date_raw, str) else competence_date_raw
        else:
            comp_dt = issue_dt or due_dt or date.today()

        # Tentativa de criar no Bling ERP via API v3
        bling_id = None
        sync_status = 'local_only'
        sync_error_msg = None
        last_sync_at = None
        bling_msg = ''

        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if client.is_configured():
                if not bling_contact_id and payee:
                    try:
                        contacts = client.get_contacts(limit=100)
                        for ct in contacts:
                            if ct.get('nome', '').strip().lower() == payee.strip().lower():
                                bling_contact_id = int(ct['id'])
                                break
                    except Exception:
                        pass

                payload = {
                    'vencimento': due_dt.strftime('%Y-%m-%d'),
                    'valor': float(amount),
                    'historico': description,
                    'dataEmissao': issue_dt.strftime('%Y-%m-%d'),
                    'competencia': comp_dt.strftime('%Y-%m-%d'),
                    'observacoes': data.get('notes') or ''
                }
                if bling_contact_id:
                    payload['contato'] = {'id': bling_contact_id}
                if bling_category_id:
                    payload['categoria'] = {'id': bling_category_id}
                if bling_pm_id:
                    payload['formaPagamento'] = {'id': bling_pm_id}

                if entry_type == 'PAGAR':
                    ok, msg, resp_data = client.create_payable(payload)
                else:
                    ok, msg, resp_data = client.create_receivable(payload)

                if ok and resp_data.get('id'):
                    bling_id = int(resp_data['id'])
                    sync_status = 'synced'
                    last_sync_at = datetime.utcnow()
                    bling_msg = f' (espelhado no Bling ERP #{bling_id})'
                else:
                    sync_status = 'sync_error'
                    sync_error_msg = msg
                    bling_msg = f' (Aviso Bling: {msg})'
        except Exception as e:
            logger.warning(f"[AccountsService] Erro ao cadastrar no Bling: {e}")
            sync_status = 'sync_error'
            sync_error_msg = str(e)
            bling_msg = f' (Erro Bling: {str(e)})'

        # Se não gerou ID oficial no Bling, gera ID sintético temporário
        if not bling_id:
            synthetic_id = int(datetime.utcnow().timestamp() * 1000)
            while FinancialEntry.query.filter_by(bling_id=synthetic_id).first():
                synthetic_id += 1
            bling_id = synthetic_id

        entry = FinancialEntry(
            bling_id=bling_id,
            entry_type=entry_type,
            description=description,
            entity_name=payee,
            category=data.get('category') or 'Operacional',
            amount=amount,
            issue_date=issue_dt,
            due_date=due_dt,
            competence_date=comp_dt,
            payment_date=payment_date,
            status=status,
            payment_method=data.get('payment_method') or 'Boleto',
            notes=data.get('notes'),
            discount=float(data.get('discount', 0.0) or 0.0),
            fine_fee=float(data.get('fine_fee', 0.0) or 0.0),
            bling_contact_id=bling_contact_id,
            bling_category_id=bling_category_id,
            bling_payment_method_id=bling_pm_id,
            sync_status=sync_status,
            last_sync_at=last_sync_at,
            sync_error_msg=sync_error_msg
        )
        db.session.add(entry)
        db.session.commit()

        # Se criado já liquidado e tem ID oficial no Bling, efetua baixa
        if status == 'Pago' and entry.bling_id < 9000000000:
            cls.settle_entry(entry.id, payment_date=payment_date, payment_method=entry.payment_method, notes=None)

        return ServiceResult(
            success=True,
            message=f'Novo lançamento de {entry_type} criado com sucesso!{bling_msg}',
            entry=entry
        )

    @classmethod
    def update_entry(cls, entry_id: int, data: Dict[str, Any]) -> ServiceResult:
        """
        Atualiza dados de um lançamento existente e espelha no Bling ERP.
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
        prev_status = entry.status
        new_status = data.get('status')
        if new_status:
            entry.status = new_status
            if new_status == 'Pago':
                raw_p = data.get('payment_date')
                if raw_p:
                    entry.payment_date = datetime.strptime(raw_p[:10], '%Y-%m-%d').date() if isinstance(raw_p, str) else raw_p
                elif not entry.payment_date:
                    entry.payment_date = date.today()

        if 'bling_contact_id' in data and data['bling_contact_id']:
            try:
                entry.bling_contact_id = int(data['bling_contact_id'])
            except Exception:
                pass
        if 'bling_category_id' in data and data['bling_category_id']:
            try:
                entry.bling_category_id = int(data['bling_category_id'])
            except Exception:
                pass
        if 'bling_payment_method_id' in data and data['bling_payment_method_id']:
            try:
                entry.bling_payment_method_id = int(data['bling_payment_method_id'])
            except Exception:
                pass

        if 'due_date' in data and data['due_date']:
            raw_d = data['due_date']
            entry.due_date = datetime.strptime(raw_d[:10], '%Y-%m-%d').date() if isinstance(raw_d, str) else raw_d

        if 'issue_date' in data and data['issue_date']:
            raw_i = data['issue_date']
            entry.issue_date = datetime.strptime(raw_i[:10], '%Y-%m-%d').date() if isinstance(raw_i, str) else raw_i

        if 'competence_date' in data and data['competence_date']:
            raw_c = data['competence_date']
            entry.competence_date = datetime.strptime(raw_c[:10], '%Y-%m-%d').date() if isinstance(raw_c, str) else raw_c

        entry.updated_at = datetime.utcnow()

        # Espelhamento no Bling ERP
        bling_msg = ''
        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if client.is_configured():
                # Caso o título ainda não tenha ID oficial no Bling, sincroniza criação primeiro
                if not entry.bling_id or entry.bling_id >= 9000000000:
                    cls.sync_single_entry(entry.id)
                elif entry.bling_id < 9000000000:
                    issue_val = entry.issue_date or date.today()
                    comp_val = getattr(entry, 'competence_date', None) or entry.issue_date or entry.due_date or date.today()

                    if not entry.bling_contact_id and entry.entity_name:
                        try:
                            contacts = client.get_contacts(limit=100)
                            for ct in contacts:
                                if ct.get('nome', '').strip().lower() == entry.entity_name.strip().lower():
                                    entry.bling_contact_id = int(ct['id'])
                                    break
                        except Exception:
                            pass

                    payload = {
                        'vencimento': entry.due_date.strftime('%Y-%m-%d'),
                        'valor': float(entry.amount),
                        'historico': entry.description,
                        'data': issue_val.strftime('%Y-%m-%d'),
                        'dataEmissao': issue_val.strftime('%Y-%m-%d'),
                        'competencia': comp_val.strftime('%Y-%m-%d'),
                        'observacoes': entry.notes or ''
                    }
                    if entry.bling_contact_id:
                        payload['contato'] = {'id': int(entry.bling_contact_id)}
                    if entry.bling_category_id:
                        payload['categoria'] = {'id': int(entry.bling_category_id)}
                    if entry.bling_payment_method_id:
                        payload['formaPagamento'] = {'id': int(entry.bling_payment_method_id)}

                    if entry.entry_type == 'PAGAR':
                        ok, msg, _ = client.update_payable(entry.bling_id, payload)
                    else:
                        ok, msg, _ = client.update_receivable(entry.bling_id, payload)

                    if ok:
                        entry.sync_status = 'synced'
                        entry.last_sync_at = datetime.utcnow()
                        entry.sync_error_msg = None
                        bling_msg = ' (alterações espelhadas no Bling)'
                    else:
                        entry.sync_status = 'sync_error'
                        entry.sync_error_msg = msg
                        bling_msg = f' (Aviso Bling: {msg})'

                # Se o status foi alterado para Pago (fechamento), aciona baixa
                if entry.status == 'Pago':
                    cls.settle_entry(entry.id, payment_date=entry.payment_date, payment_method=entry.payment_method, notes=None)
                elif entry.status in ('Pendente', 'Atrasado') and prev_status == 'Pago':
                    cls.unsettle_entry(entry.id)
        except Exception as e:
            logger.warning(f"[AccountsService] Erro ao atualizar no Bling: {e}")
            entry.sync_status = 'sync_error'
            entry.sync_error_msg = str(e)
            bling_msg = f' (Erro Bling: {str(e)})'

        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Lançamento #{entry.id} atualizado com sucesso.{bling_msg}',
            entry=entry
        )

    @classmethod
    def delete_entry(cls, entry_id: int) -> ServiceResult:
        """
        Exclui permanentemente um lançamento financeiro no BI e no Bling ERP.
        """
        entry = FinancialEntry.query.get(entry_id)
        if not entry:
            return ServiceResult(success=False, message=f'Lançamento #{entry_id} não encontrado.')

        desc_txt = entry.description
        bling_id = entry.bling_id
        entry_type = entry.entry_type

        # Se existir no Bling, tenta excluir da API v3
        bling_msg = ''
        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if client.is_configured() and bling_id and bling_id < 9000000000:
                if entry_type == 'PAGAR':
                    ok, msg = client.delete_payable(bling_id)
                else:
                    ok, msg = client.delete_receivable(bling_id)
                if ok:
                    bling_msg = ' (também excluído do Bling ERP)'
                else:
                    bling_msg = f' (Aviso Bling: {msg})'
        except Exception as e:
            logger.warning(f"[AccountsService] Erro ao excluir no Bling: {e}")

        db.session.delete(entry)
        db.session.commit()

        return ServiceResult(
            success=True,
            message=f'Lançamento #{entry_id} ("{desc_txt}") excluído com sucesso.{bling_msg}'
        )

    @classmethod
    def sync_single_entry(cls, entry_id: int) -> ServiceResult:
        """
        Força a sincronização / retentativa de um título com o Bling ERP.
        Se ainda não existe no Bling (ID sintético >= 9000000000), cria o título na API e substitui pelo ID oficial.
        Se já existe, envia as atualizações pendentes ou a baixa.
        """
        entry = db.session.get(FinancialEntry, entry_id)
        if not entry:
            return ServiceResult(success=False, message=f'Lançamento #{entry_id} não encontrado.', entry=None)

        if not entry.due_date:
            return ServiceResult(success=False, message='O lançamento precisa ter uma data de vencimento para sincronizar com o Bling.', entry=entry)

        try:
            val = float(entry.amount or 0.0)
            if val <= 0:
                return ServiceResult(success=False, message='O valor do lançamento deve ser maior que zero para sincronizar com o Bling.', entry=entry)
        except (ValueError, TypeError):
            return ServiceResult(success=False, message='Valor inválido para sincronização.', entry=entry)

        from app.services.bling_api import BlingApiClient
        client = BlingApiClient()
        if not client.is_configured():
            return ServiceResult(success=False, message='Integração com o Bling ERP não está configurada ou conectada. Acesse Configurações > Integração Bling.', entry=entry)

        try:
            # Caso 1: Lançamento local que ainda não foi criado no Bling
            if not entry.bling_id or entry.bling_id >= 9000000000:
                if not entry.bling_contact_id and entry.entity_name:
                    try:
                        contacts = client.get_contacts(limit=100)
                        for ct in contacts:
                            if ct.get('nome', '').strip().lower() == entry.entity_name.strip().lower():
                                entry.bling_contact_id = int(ct['id'])
                                db.session.commit()
                                break
                    except Exception:
                        pass

                issue_val = entry.issue_date or date.today()
                comp_val = getattr(entry, 'competence_date', None) or entry.issue_date or entry.due_date or date.today()
                payload = {
                    'vencimento': entry.due_date.strftime('%Y-%m-%d'),
                    'valor': float(entry.amount),
                    'historico': entry.description,
                    'dataEmissao': issue_val.strftime('%Y-%m-%d'),
                    'competencia': comp_val.strftime('%Y-%m-%d'),
                    'observacoes': entry.notes or ''
                }
                if entry.bling_contact_id:
                    payload['contato'] = {'id': entry.bling_contact_id}
                if entry.bling_category_id:
                    payload['categoria'] = {'id': entry.bling_category_id}
                if entry.bling_payment_method_id:
                    payload['formaPagamento'] = {'id': entry.bling_payment_method_id}

                if entry.entry_type == 'PAGAR':
                    ok, msg, resp_data = client.create_payable(payload)
                else:
                    ok, msg, resp_data = client.create_receivable(payload)

                if ok and resp_data.get('id'):
                    entry.bling_id = int(resp_data['id'])
                    entry.sync_status = 'synced'
                    entry.last_sync_at = datetime.utcnow()
                    entry.sync_error_msg = None
                    db.session.commit()

                    # Se já estava marcado como Pago, liquida no Bling agora
                    if entry.status == 'Pago':
                        cls.settle_entry(entry.id, payment_date=entry.payment_date, payment_method=entry.payment_method, notes=None)

                    return ServiceResult(
                        success=True,
                        message=f'Lançamento #{entry.id} sincronizado com sucesso no Bling ERP! (ID oficial #{entry.bling_id})',
                        entry=entry
                    )
                else:
                    entry.sync_status = 'sync_error'
                    entry.sync_error_msg = msg
                    db.session.commit()
                    return ServiceResult(success=False, message=f'Falha ao sincronizar com o Bling: {msg}', entry=entry)

            # Caso 2: Título já possui ID oficial no Bling
            if entry.status == 'Pago':
                return cls.settle_entry(entry.id, payment_date=entry.payment_date, payment_method=entry.payment_method, notes=None)
            else:
                issue_val = entry.issue_date or date.today()
                comp_val = getattr(entry, 'competence_date', None) or entry.issue_date or entry.due_date or date.today()
                payload = {
                    'vencimento': entry.due_date.strftime('%Y-%m-%d'),
                    'valor': float(entry.amount),
                    'historico': entry.description,
                    'dataEmissao': issue_val.strftime('%Y-%m-%d'),
                    'competencia': comp_val.strftime('%Y-%m-%d'),
                    'observacoes': entry.notes or ''
                }
                if entry.bling_contact_id:
                    payload['contato'] = {'id': entry.bling_contact_id}
                if entry.bling_category_id:
                    payload['categoria'] = {'id': entry.bling_category_id}
                if entry.bling_payment_method_id:
                    payload['formaPagamento'] = {'id': entry.bling_payment_method_id}

                if entry.entry_type == 'PAGAR':
                    ok, msg, _ = client.update_payable(entry.bling_id, payload)
                else:
                    ok, msg, _ = client.update_receivable(entry.bling_id, payload)

                if ok:
                    entry.sync_status = 'synced'
                    entry.last_sync_at = datetime.utcnow()
                    entry.sync_error_msg = None
                    db.session.commit()
                    return ServiceResult(success=True, message=f'Lançamento #{entry.id} atualizado no Bling ERP com sucesso!', entry=entry)
                else:
                    entry.sync_status = 'sync_error'
                    entry.sync_error_msg = msg
                    db.session.commit()
                    return ServiceResult(success=False, message=f'Falha ao atualizar no Bling: {msg}', entry=entry)

        except Exception as e:
            logger.error(f"[AccountsService] Exceção ao sincronizar lançamento {entry_id}: {e}")
            entry.sync_status = 'sync_error'
            entry.sync_error_msg = str(e)
            db.session.commit()
            return ServiceResult(success=False, message=f'Erro interno ao sincronizar: {str(e)}', entry=entry)

    @classmethod
    def get_filter_options(cls) -> Dict[str, Any]:
        """
        Retorna as opções disponíveis para preenchimento dos filtros e modais no frontend.
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

        # Consulta opções dinâmicas da API do Bling se conectada
        bling_options = cls.get_auxiliary_options()

        return {
            'categories': sorted(categories),
            'payment_methods': sorted(methods),
            'bling_payment_methods': bling_options.get('payment_methods', []),
            'bling_categories': bling_options.get('categories', []),
            'bling_contacts': bling_options.get('contacts', [])
        }

    @classmethod
    def get_auxiliary_options(cls) -> Dict[str, Any]:
        """
        Retorna listas estruturadas de formas de pagamento, categorias e contatos obtidos
        diretamente da API v3 do Bling ou da base local.
        """
        from app.services.bling_api import BlingApiClient
        client = BlingApiClient()
        
        bling_methods = []
        bling_categories = []
        bling_contacts = []
        
        if client.is_configured():
            try:
                raw_methods = client.get_payment_methods()
                for m in raw_methods:
                    if m.get('id') and m.get('descricao'):
                        bling_methods.append({
                            'id': m['id'],
                            'name': m['descricao']
                        })
            except Exception as e:
                logger.debug(f"[AccountsService] Aviso ao buscar formas de pagamento Bling: {e}")

            try:
                raw_cats = client.get_revenue_expense_categories()
                for c in raw_cats:
                    if c.get('id') and c.get('descricao'):
                        bling_categories.append({
                            'id': c['id'],
                            'name': c['descricao'],
                            'type': c.get('tipo')
                        })
            except Exception as e:
                logger.debug(f"[AccountsService] Aviso ao buscar categorias Bling: {e}")

            try:
                raw_contacts = client.get_contacts(limit=100)
                for ct in raw_contacts:
                    if ct.get('id') and ct.get('nome'):
                        bling_contacts.append({
                            'id': ct['id'],
                            'name': ct['nome']
                        })
            except Exception as e:
                logger.debug(f"[AccountsService] Aviso ao buscar contatos Bling: {e}")

        if not bling_methods:
            default_methods = ['Boleto', 'Pix', 'Cartão de Crédito', 'Cartão de Débito', 'Transferência', 'Dinheiro']
            bling_methods = [{'id': None, 'name': m} for m in default_methods]

        if not bling_categories:
            default_cats = ['Operacional', 'Fornecedores', 'Impostos', 'Logística', 'Taxas Financeiras', 'Vendas Mercado Livre', 'Vendas Shopee', 'Vendas Site']
            bling_categories = [{'id': None, 'name': c, 'type': None} for c in default_cats]

        return {
            'payment_methods': bling_methods,
            'categories': bling_categories,
            'contacts': bling_contacts
        }

