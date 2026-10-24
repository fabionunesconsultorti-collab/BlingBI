from flask import Blueprint, render_template, request, send_file, jsonify, redirect, url_for, flash
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.exporter import BiExporter
from app.services.cash_statement import CashStatementService
from app.services.accounts_service import AccountsService
from app.core.feature_registry import requires_feature
from datetime import datetime, date

bp = Blueprint('finance', __name__, url_prefix='/finance')

# -----------------------------------------------------------------------------
# 4.1 VISÃO GERAL FINANCEIRA & FLUXO REALIZADO
# -----------------------------------------------------------------------------
@bp.route('/')
@requires_feature('finance.overview')
def index():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_finance_analytics(start_date, end_date)

    return render_template(
        'finance/index.html',
        analytics=analytics,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        active_tab='overview'
    )

# -----------------------------------------------------------------------------
# 4.2 DRE GERENCIAL (DEMONSTRATIVO DO RESULTADO DO EXERCÍCIO)
# -----------------------------------------------------------------------------
@bp.route('/dre')
@requires_feature('finance.dre')
def dre():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_dre_statement(start_date, end_date)

    return render_template(
        'finance/dre.html',
        report_data=report_data,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        active_tab='dre'
    )

# -----------------------------------------------------------------------------
# 4.3 PROJEÇÃO DO FLUXO DE CAIXA
# -----------------------------------------------------------------------------
@bp.route('/cash-flow')
@requires_feature('finance.cash_flow')
def cash_flow():
    days = request.args.get('days', default=30, type=int)
    report_data = StandardReportsEngine.get_cash_flow_projection(days=days)

    return render_template(
        'finance/cash_flow.html',
        report_data=report_data,
        days=days,
        active_tab='cash_flow'
    )

# -----------------------------------------------------------------------------
# 4.4 INADIMPLÊNCIA & AGING LIST (CONTAS A RECEBER)
# -----------------------------------------------------------------------------
@bp.route('/aging')
@requires_feature('finance.aging')
def aging():
    period = request.args.get('period', 'all')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date = None
    end_date = None
    if period != 'all':
        start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)

    report_data = StandardReportsEngine.get_aging_list_analysis(start_date, end_date)

    return render_template(
        'finance/aging.html',
        report_data=report_data,
        period=period,
        active_tab='aging'
    )

# -----------------------------------------------------------------------------
# EXPORTAÇÕES (EXCEL / PDF)
# -----------------------------------------------------------------------------
@bp.route('/dre/export/excel')
def export_dre_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_dre_statement(start_date, end_date)

    excel_stream = BiExporter.export_dre_to_excel(report_data['lines'], report_data['summary'], start_date, end_date)
    return send_file(
        excel_stream,
        as_attachment=True,
        download_name=f"DRE_Gerencial_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.route('/dre/export/pdf')
def export_dre_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_dre_statement(start_date, end_date)

    pdf_stream = BiExporter.export_dre_to_pdf(report_data['lines'], report_data['summary'], start_date, end_date)
    return send_file(
        pdf_stream,
        as_attachment=True,
        download_name=f"DRE_Gerencial_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
        mimetype="application/pdf"
    )

# -----------------------------------------------------------------------------
# 4.5 FECHAMENTO DE CAIXA & EXTRATO DE MOVIMENTAÇÃO FINANCEIRA
# -----------------------------------------------------------------------------
@bp.route('/cash-statement')
@bp.route('/fechamento-caixa')
@bp.route('/extrato')
@requires_feature('finance.cash_statement')
def cash_statement():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    m_type = request.args.get('type', 'all')
    p_method = request.args.get('method', 'all')
    search = request.args.get('q')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    statement_data = CashStatementService.get_cash_statement(
        start_date=start_date,
        end_date=end_date,
        movement_type=m_type,
        payment_method=p_method,
        search=search
    )

    return render_template(
        'finance/cash_statement.html',
        statement=statement_data,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        m_type=m_type,
        p_method=p_method,
        search=search or '',
        active_tab='cash_statement'
    )

@bp.route('/cash-statement/export/excel')
def export_cash_statement_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    m_type = request.args.get('type', 'all')
    p_method = request.args.get('method', 'all')
    search = request.args.get('q')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    statement_data = CashStatementService.get_cash_statement(
        start_date=start_date,
        end_date=end_date,
        movement_type=m_type,
        payment_method=p_method,
        search=search
    )

    excel_stream = BiExporter.export_cash_statement_to_excel(
        movements=statement_data['movements'],
        summary=statement_data['summary'],
        daily_closings=statement_data['daily_closings'],
        start_date=start_date,
        end_date=end_date
    )
    return send_file(
        excel_stream,
        as_attachment=True,
        download_name=f"BlingBI_Fechamento_Caixa_Extrato_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.route('/cash-statement/export/pdf')
def export_cash_statement_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    m_type = request.args.get('type', 'all')
    p_method = request.args.get('method', 'all')
    search = request.args.get('q')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    statement_data = CashStatementService.get_cash_statement(
        start_date=start_date,
        end_date=end_date,
        movement_type=m_type,
        payment_method=p_method,
        search=search
    )

    pdf_stream = BiExporter.export_cash_statement_to_pdf(
        movements=statement_data['movements'],
        summary=statement_data['summary'],
        daily_closings=statement_data['daily_closings'],
        start_date=start_date,
        end_date=end_date
    )
    return send_file(
        pdf_stream,
        as_attachment=True,
        download_name=f"BlingBI_Fechamento_Caixa_Extrato_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
        mimetype="application/pdf"
    )

@bp.route('/cash-statement/entry', methods=['POST'])
def add_cash_movement_entry():
    from flask import redirect, url_for, flash
    entry_type = request.form.get('entry_type', 'PAGAR')
    description = request.form.get('description', '').strip()
    amount_str = request.form.get('amount', '0').replace(',', '.')
    entity_name = request.form.get('entity_name', 'Caixa Loja')
    category = request.form.get('category', 'Sangria')
    payment_method = request.form.get('payment_method', 'Dinheiro')
    dt_str = request.form.get('date')

    try:
        amount = float(amount_str)
        m_date = datetime.strptime(dt_str, '%Y-%m-%d').date() if dt_str else date.today()
        CashStatementService.add_cash_movement(
            entry_type=entry_type,
            description=description or 'Sangria / Movimentação de Caixa',
            amount=amount,
            entity_name=entity_name,
            category=category,
            payment_method=payment_method,
            movement_date=m_date
        )
        flash('Movimentação registrada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao registrar movimentação: {e}', 'danger')

    return redirect(url_for('finance.cash_statement'))


# -----------------------------------------------------------------------------
# 4.6 CONTAS A PAGAR & CONTAS A RECEBER (LANÇAMENTOS, CALENDÁRIO & BAIXAS)
# -----------------------------------------------------------------------------
@bp.route('/accounts')
@requires_feature('finance.accounts')
def accounts():
    entry_type = request.args.get('entry_type', 'TODOS')
    status = request.args.get('status', 'TODOS')
    period = request.args.get('period', 'all')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    date_basis = request.args.get('date_basis', 'due_date')
    category = request.args.get('category', 'all')
    payment_method = request.args.get('payment_method', 'all')
    search = request.args.get('q', '').strip()
    view = request.args.get('view', 'list')
    cal_year = request.args.get('cal_year', type=int)
    cal_month = request.args.get('cal_month', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    # Resolução de intervalo de datas
    start_date, end_date = None, None
    if period and period != 'all':
        start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    elif start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except Exception:
            start_date, end_date = None, None

    filters = {
        'entry_type': entry_type,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'date_basis': date_basis,
        'category': category,
        'payment_method': payment_method,
        'search': search,
        'period': period
    }

    accounts_data = AccountsService.get_accounts_data(filters=filters, page=page, per_page=per_page)
    summary = AccountsService.get_summary_metrics(filters=filters)
    calendar_data = AccountsService.get_calendar_events(year=cal_year, month=cal_month, filters=filters)
    options = AccountsService.get_filter_options()

    return render_template(
        'finance/accounts.html',
        entries=accounts_data['entries'],
        pagination=accounts_data['pagination'],
        summary=summary,
        calendar_data=calendar_data,
        options=options,
        filters=filters,
        current_view=view,
        active_tab='accounts'
    )

@bp.route('/accounts/settle/<int:entry_id>', methods=['POST'])
def settle_account_entry(entry_id):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form.to_dict()

    p_date = data.get('payment_date')
    p_method = data.get('payment_method')
    notes = data.get('notes')
    discount = data.get('discount')
    fine_fee = data.get('fine_fee')
    bling_pm_id = data.get('bling_payment_method_id')

    success, msg, entry = AccountsService.settle_entry(
        entry_id=entry_id,
        payment_date=p_date,
        payment_method=p_method,
        notes=notes,
        discount=discount,
        fine_fee=fine_fee,
        bling_payment_method_id=bling_pm_id
    )

    if is_json:
        return jsonify({'success': success, 'message': msg, 'entry': entry.to_dict() if entry else None})
    
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('finance.accounts'))

@bp.route('/accounts/unsettle/<int:entry_id>', methods=['POST'])
def unsettle_account_entry(entry_id):
    is_json = request.is_json
    success, msg, entry = AccountsService.unsettle_entry(entry_id)

    if is_json:
        return jsonify({'success': success, 'message': msg, 'entry': entry.to_dict() if entry else None})

    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('finance.accounts'))

@bp.route('/accounts/create', methods=['POST'])
def create_account_entry():
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form.to_dict()

    success, msg, entry = AccountsService.create_entry(data)

    if is_json:
        return jsonify({'success': success, 'message': msg, 'entry': entry.to_dict() if entry else None})

    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('finance.accounts'))

@bp.route('/accounts/update/<int:entry_id>', methods=['POST'])
def update_account_entry(entry_id):
    is_json = request.is_json
    data = request.get_json(silent=True) or request.form.to_dict()

    success, msg, entry = AccountsService.update_entry(entry_id, data)

    if is_json:
        return jsonify({'success': success, 'message': msg, 'entry': entry.to_dict() if entry else None})

    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('finance.accounts'))

@bp.route('/accounts/delete/<int:entry_id>', methods=['POST'])
def delete_account_entry(entry_id):
    is_json = request.is_json
    success, msg = AccountsService.delete_entry(entry_id)

    if is_json:
        return jsonify({'success': success, 'message': msg})

    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('finance.accounts'))

@bp.route('/accounts/sync-entry/<int:entry_id>', methods=['POST'])
def sync_single_account_entry(entry_id):
    """Retenta ou força a sincronização de um lançamento com o Bling ERP."""
    is_json = request.is_json
    success, msg, entry = AccountsService.sync_single_entry(entry_id)

    if is_json:
        return jsonify({'success': success, 'message': msg, 'entry': entry.to_dict() if entry else None})

    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('finance.accounts'))

@bp.route('/accounts/auxiliary-options')
def get_accounts_auxiliary_options():
    """Retorna JSON das formas de pagamento e categorias ativas no Bling para preenchimento de modais."""
    options = AccountsService.get_auxiliary_options()
    return jsonify(options)


@bp.route('/accounts/export/excel')
def export_accounts_excel():
    entry_type = request.args.get('entry_type', 'TODOS')
    status = request.args.get('status', 'TODOS')
    period = request.args.get('period', 'all')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    date_basis = request.args.get('date_basis', 'due_date')
    category = request.args.get('category', 'all')
    payment_method = request.args.get('payment_method', 'all')
    search = request.args.get('q', '').strip()

    start_date, end_date = None, None
    if period and period != 'all':
        start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    elif start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except Exception:
            start_date, end_date = None, None

    filters = {
        'entry_type': entry_type,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'date_basis': date_basis,
        'category': category,
        'payment_method': payment_method,
        'search': search,
        'period': period
    }

    accounts_data = AccountsService.get_accounts_data(filters=filters, page=1, per_page=10000)
    summary = AccountsService.get_summary_metrics(filters=filters)

    excel_stream = BiExporter.export_accounts_to_excel(
        entries=accounts_data['entries'],
        summary=summary,
        filters=filters
    )

    return send_file(
        excel_stream,
        as_attachment=True,
        download_name=f"BlingBI_Contas_Pagar_Receber_{date.today().strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.route('/accounts/export/pdf')
def export_accounts_pdf():
    entry_type = request.args.get('entry_type', 'TODOS')
    status = request.args.get('status', 'TODOS')
    period = request.args.get('period', 'all')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    date_basis = request.args.get('date_basis', 'due_date')
    category = request.args.get('category', 'all')
    payment_method = request.args.get('payment_method', 'all')
    search = request.args.get('q', '').strip()

    start_date, end_date = None, None
    if period and period != 'all':
        start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    elif start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except Exception:
            start_date, end_date = None, None

    filters = {
        'entry_type': entry_type,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'date_basis': date_basis,
        'category': category,
        'payment_method': payment_method,
        'search': search,
        'period': period
    }

    accounts_data = AccountsService.get_accounts_data(filters=filters, page=1, per_page=200)
    summary = AccountsService.get_summary_metrics(filters=filters)

    pdf_stream = BiExporter.export_accounts_to_pdf(
        entries=accounts_data['entries'],
        summary=summary,
        filters=filters
    )

    return send_file(
        pdf_stream,
        as_attachment=True,
        download_name=f"BlingBI_Contas_Pagar_Receber_{date.today().strftime('%Y%m%d')}.pdf",
        mimetype="application/pdf"
    )

@bp.route('/accounts/sync', methods=['POST'])
def sync_accounts():
    from app.services.sync_service import SyncService
    success = False
    msg = ""
    try:
        success, msg = SyncService.sync_selected(options={
            'customers': False,
            'products': False,
            'orders': False,
            'receivables': True,
            'payables': True
        })
        if success:
            flash("Sincronização de Contas a Pagar e Receber concluída com sucesso!", "success")
        else:
            flash(f"Aviso durante a sincronização: {msg}", "warning")
    except Exception as e:
        msg = str(e)
        flash(f"Erro ao sincronizar com Bling: {str(e)}", "danger")

    if request.is_json:
        return jsonify({'success': success, 'message': msg})
    return redirect(url_for('finance.accounts'))

