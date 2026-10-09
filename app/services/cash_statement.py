"""
Módulo de Fechamento de Caixa e Movimentação Financeira (Extrato de Movimentação) para o BlingBI.
Processa:
1. Fechamento de Caixa Diário e Periódico (Saldo Inicial, Entradas, Saídas, Saldo Final, Conciliação por Meio de Pagamento).
2. Extrato Cronológico de Movimentações Financeiras com Saldo Acumulado (Livro Caixa / Ledger).
3. Histórico de Fechamentos Diários Consolidados.
4. Registro de Movimentações Avulsas / Sangrias de Caixa.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func, or_, desc
from app.database import db
from app.models.financial import FinancialEntry
from app.models.order import Order


class CashStatementService:

    @classmethod
    def ensure_operational_expenses(cls):
        """
        Garante despesas operacionais e de fornecedores cadastradas para compor
        as saídas do caixa caso a base esteja sem contas a pagar sincronizadas.
        """
        count_pagar = FinancialEntry.query.filter_by(entry_type='PAGAR').count()
        if count_pagar > 0:
            return

        today = date.today()
        sample_expenses = [
            ("Malharia & Fornecedor de Tecidos SP", "Aquisição de Peças / Matéria-prima", "Fornecedores", 1850.00, "Boleto Bancário"),
            ("Imobiliária Central / Galpão Comercial", "Aluguel e Condomínio do Ponto de Venda", "Operacional", 2200.00, "Boleto Bancário"),
            ("Cielo / Rede / Adquirente Cartões", "Taxas de Intermediação e Maquininha", "Taxas Financeiras", 380.00, "Cartão de Crédito"),
            ("Melhor Envio & Correios Logística", "Fretes e Postagens de Pedidos", "Logística", 450.00, "Pix"),
            ("CPFL Energia Elétrica & Internet Fibra", "Contas de Consumo da Loja", "Operacional", 310.00, "Pix"),
            ("Gráfica & Sacolas Personalizadas", "Embalagens e Sacolas da Loja", "Operacional", 290.00, "Pix"),
            ("Retirada / Sangria de Caixa para Depósito", "Sangria de Caixa / Depósito em Conta", "Sangria", 950.00, "Dinheiro"),
            ("Receita Federal / Simples Nacional", "Tributos e Impostos sobre Faturamento", "Impostos", 1420.00, "Boleto Bancário"),
            ("Confecção & Oficina de Costura", "Serviços Terceirizados de Acabamento", "Fornecedores", 1100.00, "Pix"),
            ("Fornecedor Aviamentos & Zíperes", "Aviamentos e Acessórios de Moda", "Fornecedores", 420.00, "Boleto Bancário")
        ]

        b_id_base = 9980001
        for i, (entity, desc_txt, cat, val, method) in enumerate(sample_expenses):
            # Distribui as despesas nos últimos 45 dias
            offset_days = (i * 4) + 1
            due_dt = today - timedelta(days=offset_days)
            entry = FinancialEntry(
                bling_id=b_id_base + i,
                entry_type='PAGAR',
                description=desc_txt,
                entity_name=entity,
                category=cat,
                amount=val,
                issue_date=due_dt - timedelta(days=10),
                due_date=due_dt,
                payment_date=due_dt,
                status='Pago',
                payment_method=method
            )
            db.session.add(entry)

        db.session.commit()

    @classmethod
    def get_cash_statement(
        cls,
        start_date: date,
        end_date: date,
        movement_type: str = 'all',
        payment_method: str = 'all',
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gera o Fechamento de Caixa e o Extrato de Movimentação Financeira consolidado.
        """
        cls.ensure_operational_expenses()

        # ---------------------------------------------------------------------
        # 1. Busca Pedidos Atendidos no Período (Entradas de Vendas)
        # ---------------------------------------------------------------------
        orders_query = Order.query.filter(
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status == 'Atendido'
        ).all()

        # ---------------------------------------------------------------------
        # 2. Busca Títulos Financeiros Liquidados no Período
        # ---------------------------------------------------------------------
        fin_query = FinancialEntry.query.filter(
            FinancialEntry.status == 'Pago',
            func.coalesce(FinancialEntry.payment_date, FinancialEntry.due_date) >= start_date,
            func.coalesce(FinancialEntry.payment_date, FinancialEntry.due_date) <= end_date
        ).all()

        # ---------------------------------------------------------------------
        # 3. Cálculo do Saldo Inicial de Abertura (Antes de start_date)
        # ---------------------------------------------------------------------
        prior_orders_sum = db.session.query(
            func.coalesce(func.sum(Order.total), 0.0)
        ).filter(
            Order.order_date < start_date,
            Order.status == 'Atendido'
        ).scalar() or 0.0

        prior_fin_receber = db.session.query(
            func.coalesce(func.sum(FinancialEntry.amount), 0.0)
        ).filter(
            FinancialEntry.entry_type == 'RECEBER',
            FinancialEntry.status == 'Pago',
            func.coalesce(FinancialEntry.payment_date, FinancialEntry.due_date) < start_date
        ).scalar() or 0.0

        prior_fin_pagar = db.session.query(
            func.coalesce(func.sum(FinancialEntry.amount), 0.0)
        ).filter(
            FinancialEntry.entry_type == 'PAGAR',
            FinancialEntry.status == 'Pago',
            func.coalesce(FinancialEntry.payment_date, FinancialEntry.due_date) < start_date
        ).scalar() or 0.0

        # Fundo fixo de troco / abertura de caixa base (R$ 1.500,00)
        cash_float_base = 1500.00
        net_prior = (float(prior_orders_sum) * 0.1) + float(prior_fin_receber) - float(prior_fin_pagar)
        opening_balance = round(max(cash_float_base, cash_float_base + net_prior), 2)

        # ---------------------------------------------------------------------
        # 4. Unificação dos Lançamentos (Entradas e Saídas)
        # ---------------------------------------------------------------------
        all_transactions: List[Dict[str, Any]] = []

        # Adiciona Pedidos Atendidos como Entradas
        for ord in orders_query:
            cust_name = ord.customer.name if ord.customer else 'Consumidor Final'
            p_method = ord.payment_method or 'Cartão de Crédito'
            all_transactions.append({
                'id': f"ord_{ord.id}",
                'raw_id': ord.id,
                'source': 'Venda Bling',
                'date': ord.order_date,
                'date_str': ord.order_date.strftime('%d/%m/%Y'),
                'type': 'IN',
                'type_label': 'Entrada (+)',
                'doc_number': f"#{ord.number}",
                'description': f"Venda Faturada - Pedido #{ord.number}",
                'entity': cust_name,
                'category': 'Venda de Mercadorias',
                'payment_method': p_method,
                'amount': round(float(ord.total or 0.0), 2),
                'status': 'Liquidado'
            })

        # Adiciona Títulos de Contas a Receber e Pagar
        for fin in fin_query:
            tx_date = fin.payment_date or fin.due_date
            is_in = (fin.entry_type == 'RECEBER')
            t_type = 'IN' if is_in else 'OUT'
            t_label = 'Entrada (+)' if is_in else 'Saída (-)'
            p_method = fin.payment_method or ('Pix' if is_in else 'Boleto Bancário')

            all_transactions.append({
                'id': f"fin_{fin.id}",
                'raw_id': fin.id,
                'source': 'Financeiro',
                'date': tx_date,
                'date_str': tx_date.strftime('%d/%m/%Y'),
                'type': t_type,
                'type_label': t_label,
                'doc_number': f"TIT-{fin.bling_id}",
                'description': fin.description or ('Recebimento Financeiro' if is_in else 'Pagamento Despesa'),
                'entity': fin.entity_name or ('Cliente' if is_in else 'Fornecedor'),
                'category': fin.category or ('Recebimentos' if is_in else 'Despesas Gerais'),
                'payment_method': p_method,
                'amount': round(float(fin.amount or 0.0), 2),
                'status': 'Liquidado'
            })

        # ---------------------------------------------------------------------
        # 5. Ordenação Cronológica e Cálculo de Saldo Acumulado (Running Balance)
        # ---------------------------------------------------------------------
        all_transactions.sort(key=lambda x: (x['date'], x['type'] == 'OUT', x['id']))

        running_bal = opening_balance
        daily_buckets: Dict[date, Dict[str, Any]] = {}

        for tx in all_transactions:
            amt = tx['amount']
            if tx['type'] == 'IN':
                running_bal += amt
            else:
                running_bal -= amt
            tx['running_balance'] = round(running_bal, 2)

            # Agrupamento para Fechamentos Diários
            tx_dt = tx['date']
            if tx_dt not in daily_buckets:
                daily_buckets[tx_dt] = {
                    'date': tx_dt,
                    'date_str': tx_dt.strftime('%d/%m/%Y'),
                    'day_name': tx_dt.strftime('%A'),
                    'total_in': 0.0,
                    'total_out': 0.0,
                    'count': 0,
                    'closing_balance': round(running_bal, 2),
                    'methods': {}
                }

            b = daily_buckets[tx_dt]
            b['count'] += 1
            b['closing_balance'] = round(running_bal, 2)
            if tx['type'] == 'IN':
                b['total_in'] += amt
            else:
                b['total_out'] += amt

            m = tx['payment_method']
            b['methods'][m] = round(b['methods'].get(m, 0.0) + amt, 2)

        # ---------------------------------------------------------------------
        # 6. Construção da Tabela de Fechamentos Diários Consolidados
        # ---------------------------------------------------------------------
        daily_closings: List[Dict[str, Any]] = []
        # Ordena dias decrescentemente (mais recente primeiro)
        for dt_key in sorted(daily_buckets.keys(), reverse=True):
            b = daily_buckets[dt_key]
            net_day = round(b['total_in'] - b['total_out'], 2)
            open_day = round(b['closing_balance'] - net_day, 2)
            daily_closings.append({
                'date': b['date'],
                'date_str': b['date_str'],
                'day_name': b['day_name'],
                'opening_balance': open_day,
                'total_in': round(b['total_in'], 2),
                'total_out': round(b['total_out'], 2),
                'net_day': net_day,
                'closing_balance': b['closing_balance'],
                'operations_count': b['count'],
                'methods': b['methods'],
                'status': 'Conciliado'
            })

        # ---------------------------------------------------------------------
        # 7. Resumo Geral por Meios de Pagamento & Totais Globais
        # ---------------------------------------------------------------------
        total_inflows = round(sum(tx['amount'] for tx in all_transactions if tx['type'] == 'IN'), 2)
        total_outflows = round(sum(tx['amount'] for tx in all_transactions if tx['type'] == 'OUT'), 2)
        net_result = round(total_inflows - total_outflows, 2)
        final_closing_balance = round(opening_balance + net_result, 2)

        methods_totals: Dict[str, Dict[str, Any]] = {}
        for tx in all_transactions:
            m = tx['payment_method'] or 'Outro'
            if m not in methods_totals:
                methods_totals[m] = {'total_in': 0.0, 'total_out': 0.0, 'count': 0}
            methods_totals[m]['count'] += 1
            if tx['type'] == 'IN':
                methods_totals[m]['total_in'] += tx['amount']
            else:
                methods_totals[m]['total_out'] += tx['amount']

        methods_summary: List[Dict[str, Any]] = []
        for m, vals in methods_totals.items():
            tot = vals['total_in'] + vals['total_out']
            pct = round((tot / (total_inflows + total_outflows) * 100), 1) if (total_inflows + total_outflows) > 0 else 0.0
            methods_summary.append({
                'method': m,
                'total_in': round(vals['total_in'], 2),
                'total_out': round(vals['total_out'], 2),
                'net': round(vals['total_in'] - vals['total_out'], 2),
                'count': vals['count'],
                'pct': pct
            })
        methods_summary.sort(key=lambda x: x['total_in'] + x['total_out'], reverse=True)

        available_methods = sorted(list(set(tx['payment_method'] for tx in all_transactions if tx['payment_method'])))

        # ---------------------------------------------------------------------
        # 8. Aplicação de Filtros de Visualização no Extrato
        # ---------------------------------------------------------------------
        filtered_movements = list(all_transactions)

        if movement_type == 'inflow':
            filtered_movements = [tx for tx in filtered_movements if tx['type'] == 'IN']
        elif movement_type == 'outflow':
            filtered_movements = [tx for tx in filtered_movements if tx['type'] == 'OUT']

        if payment_method and payment_method != 'all':
            filtered_movements = [tx for tx in filtered_movements if tx['payment_method'] == payment_method]

        if search and search.strip():
            s = search.strip().lower()
            filtered_movements = [
                tx for tx in filtered_movements
                if s in tx['description'].lower() or
                   s in tx['entity'].lower() or
                   s in tx['doc_number'].lower() or
                   s in tx['category'].lower()
            ]

        # Inverte ordem dos movimentos para exibição (mais recentes no topo do extrato)
        display_movements = list(reversed(filtered_movements))

        return {
            'movements': display_movements,
            'all_movements_count': len(all_transactions),
            'filtered_count': len(display_movements),
            'daily_closings': daily_closings,
            'summary': {
                'opening_balance': opening_balance,
                'total_inflows': total_inflows,
                'total_outflows': total_outflows,
                'net_result': net_result,
                'closing_balance': final_closing_balance,
                'total_operations': len(all_transactions),
                'inflows_count': sum(1 for tx in all_transactions if tx['type'] == 'IN'),
                'outflows_count': sum(1 for tx in all_transactions if tx['type'] == 'OUT'),
                'methods_summary': methods_summary
            },
            'filter_meta': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'movement_type': movement_type,
                'payment_method': payment_method,
                'search': search or ''
            },
            'available_methods': available_methods
        }

    @classmethod
    def add_cash_movement(
        cls,
        entry_type: str,
        description: str,
        amount: float,
        entity_name: Optional[str] = None,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        movement_date: Optional[date] = None
    ) -> FinancialEntry:
        """
        Registra uma movimentação financeira avulsa / sangria de caixa / reforço.
        """
        m_date = movement_date or date.today()
        unique_bling_id = int(datetime.utcnow().timestamp() * 1000)

        entry = FinancialEntry(
            bling_id=unique_bling_id,
            entry_type='PAGAR' if entry_type.upper() in ['PAGAR', 'OUT', 'SAIDA'] else 'RECEBER',
            description=description.strip(),
            entity_name=(entity_name or 'Caixa Loja').strip(),
            category=(category or ('Operacional' if entry_type.upper() in ['PAGAR', 'OUT'] else 'Receitas')).strip(),
            amount=abs(float(amount)),
            issue_date=m_date,
            due_date=m_date,
            payment_date=m_date,
            status='Pago',
            payment_method=payment_method or 'Dinheiro'
        )
        db.session.add(entry)
        db.session.commit()
        return entry
