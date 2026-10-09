from flask import Blueprint, render_template, request, send_file
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.exporter import BiExporter
from app.services.cash_statement import CashStatementService
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
