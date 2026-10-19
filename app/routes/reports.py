from flask import Blueprint, render_template, request, send_file, jsonify, flash, redirect, url_for
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.exporter import BiExporter
from app.reports.registry import report_registry
from app.reports.package_manager import ReportPackageManager
from app.core.feature_registry import FeatureRegistry

bp = Blueprint('reports', __name__, url_prefix='/reports')

# =============================================================================
# HUB CENTRAL: CATÁLOGO DINÂMICO DE RELATÓRIOS CADASTRADOS
# =============================================================================
@bp.route('/')
@bp.route('/hub')
def hub():
    """Catálogo unificado de relatórios estratégicos com auto-descoberta e gestão de módulos."""
    summary_data = StandardReportsEngine.get_hub_summary()
    all_reports = report_registry.get_all()

    # Filtra relatórios pelo segmento da empresa (a menos que seja o admgeral fora de impersonate)
    from flask import session
    allowed_reports = session.get('allowed_reports')
    if allowed_reports is not None and (not session.get('is_admin') or session.get('impersonate_user_id')):
        all_reports = [r for r in all_reports if r.id in allowed_reports]

    categories = report_registry.get_categories()
    features_grouped = FeatureRegistry.get_catalog_grouped()
    all_features_list = FeatureRegistry.get_all_features()
    features_count = len(all_features_list)
    active_features_count = sum(1 for f in all_features_list if f['is_enabled'])
    
    # Filtros de tela
    selected_category = request.args.get('category', 'all')
    search_query = request.args.get('q', '').strip().lower()

    filtered_reports = all_reports
    if selected_category and selected_category != 'all':
        filtered_reports = [r for r in filtered_reports if r.category.lower() == selected_category.lower()]
    if search_query:
        filtered_reports = [
            r for r in filtered_reports 
            if search_query in r.name.lower() or search_query in r.description.lower() or any(search_query in t.lower() for t in r.metadata.tags)
        ]

    return render_template(
        'reports/hub.html',
        summary=summary_data,
        reports=filtered_reports,
        all_reports=all_reports,
        categories=categories,
        selected_category=selected_category,
        search_query=search_query,
        features_grouped=features_grouped,
        features_count=features_count,
        active_features_count=active_features_count
    )


# =============================================================================
# ROTAS DINÂMICAS PARA QUALQUER MÓDULO DE RELATÓRIO
# =============================================================================
@bp.route('/view/<report_id>')
def view_report(report_id):
    """Visualizador dinâmico de qualquer relatório registrado."""
    from flask import session
    allowed_reports = session.get('allowed_reports')
    if allowed_reports is not None and (not session.get('is_admin') or session.get('impersonate_user_id')):
        if report_id not in allowed_reports:
            flash("Este relatório não está disponível para o segmento cadastrado da sua empresa.", "warning")
            return redirect(url_for('reports.hub'))

    module = report_registry.get(report_id)
    if not module:
        flash(f"Relatório '{report_id}' não encontrado no catálogo.", "warning")
        return redirect(url_for('reports.hub'))
    if not module.is_enabled:
        flash(f"O relatório '{module.name}' está desativado pelo operador.", "warning")
        return redirect(url_for('reports.hub'))
    return module.render(request.args)

@bp.route('/export/<report_id>/excel')
def export_report_excel(report_id):
    """Exportação genérica em Excel de qualquer relatório."""
    module = report_registry.get(report_id)
    if not module:
        flash(f"Relatório '{report_id}' não encontrado.", "warning")
        return redirect(url_for('reports.hub'))
    try:
        stream, filename = module.export_excel(request.args)
        return send_file(
            stream,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except NotImplementedError:
        flash(f"O relatório '{module.name}' não possui suporte a exportação em Excel.", "warning")
        return redirect(url_for('reports.view_report', report_id=report_id))

@bp.route('/export/<report_id>/pdf')
def export_report_pdf(report_id):
    """Exportação genérica em PDF de qualquer relatório."""
    module = report_registry.get(report_id)
    if not module:
        flash(f"Relatório '{report_id}' não encontrado.", "warning")
        return redirect(url_for('reports.hub'))
    try:
        stream, filename = module.export_pdf(request.args)
        return send_file(
            stream,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except NotImplementedError:
        flash(f"O relatório '{module.name}' não possui suporte a exportação em PDF.", "warning")
        return redirect(url_for('reports.view_report', report_id=report_id))

@bp.route('/manage/toggle/<report_id>', methods=['POST'])
def toggle_report(report_id):
    """Ativa ou desativa um módulo de relatório."""
    module = report_registry.get(report_id)
    if not module:
        return jsonify({'success': False, 'message': 'Relatório não encontrado.'}), 404
    new_state = not module.is_enabled
    module.set_enabled(new_state)
    return jsonify({
        'success': True,
        'enabled': new_state,
        'message': f"Relatório '{module.name}' {'ativado' if new_state else 'desativado'} com sucesso."
    })

@bp.route('/manage/features/toggle', methods=['POST'])
@bp.route('/api/features/toggle', methods=['POST'])
def toggle_feature():
    """Ativa ou desativa qualquer aba, widget ou gráfico do sistema sob demanda."""
    data = request.get_json(silent=True) or request.form
    key = data.get('key')
    if not key:
        return jsonify({'success': False, 'message': 'Chave da funcionalidade não fornecida.'}), 400

    new_state = FeatureRegistry.toggle(key)
    if new_state is None:
        return jsonify({'success': False, 'message': f"Funcionalidade '{key}' não encontrada no catálogo."}), 404

    return jsonify({
        'success': True,
        'key': key,
        'enabled': new_state,
        'message': f"Item {'ativado' if new_state else 'desativado'} com sucesso."
    })

@bp.route('/manage/export-package/<report_id>')
def export_package(report_id):
    """Baixa a pasta do módulo encapsulado em formato .ZIP."""
    stream, filename = ReportPackageManager.export_package(report_id)
    if not stream:
        flash(f"Não foi possível exportar o pacote do relatório '{report_id}'.", "danger")
        return redirect(url_for('reports.hub'))
    return send_file(
        stream,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/manage/import-package', methods=['POST'])
def import_package():
    """Importa e instala um novo módulo de relatório a partir de arquivo .ZIP."""
    if 'package_file' not in request.files:
        flash("Nenhum arquivo enviado.", "warning")
        return redirect(url_for('reports.hub'))
    file = request.files['package_file']
    if not file or file.filename == '':
        flash("Nenhum arquivo selecionado.", "warning")
        return redirect(url_for('reports.hub'))
    if not file.filename.lower().endswith('.zip'):
        flash("O arquivo deve ser um pacote compactado no formato .zip", "danger")
        return redirect(url_for('reports.hub'))

    success, message = ReportPackageManager.import_package(file.stream)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")
    return redirect(url_for('reports.hub'))



# =============================================================================
# PILAR 1: PERFORMANCE MULTICANAL & MARGEM POR MARKETPLACE
# =============================================================================
@bp.route('/multichannel')
def multichannel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_multichannel_performance(start_date, end_date, channel_filter=channel)

    # Obter lista de canais únicos
    all_channels = sorted(list(set(c['channel'] for c in report_data['channels'])))

    return render_template(
        'reports/multichannel.html',
        channels=report_data['channels'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        all_channels=all_channels,
        selected_channel=channel,
        period=period,
        start_date=start_date,
        end_date=end_date
    )

@bp.route('/multichannel/excel')
def export_multichannel_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_multichannel_performance(start_date, end_date, channel_filter=channel)

    excel_stream = BiExporter.export_multichannel_to_excel(report_data['channels'], report_data['summary'], start_date, end_date)
    filename = f"BlingBI_Multicanal_Margem_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/multichannel/pdf')
def export_multichannel_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_multichannel_performance(start_date, end_date, channel_filter=channel)

    pdf_stream = BiExporter.export_multichannel_to_pdf(report_data['channels'], report_data['summary'], start_date, end_date)
    filename = f"BlingBI_Multicanal_Margem_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


# =============================================================================
# PILAR 2: PRODUTOS, GIRO, CURVA ABC & ALERTA DE RUPTURA / COBERTURA
# =============================================================================
@bp.route('/stock-coverage')
def stock_coverage():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    category = request.args.get('category', 'all')
    status_cov = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_stock_coverage_and_abc(
        start_date, end_date, category_filter=category, status_filter=status_cov
    )

    categories = sorted(list(set(i['category'] for i in report_data['items'] if i.get('category'))))

    return render_template(
        'reports/stock_coverage.html',
        items=report_data['items'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        categories=categories,
        selected_category=category,
        selected_status=status_cov,
        period=period,
        start_date=start_date,
        end_date=end_date
    )

@bp.route('/stock-coverage/excel')
def export_stock_coverage_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    category = request.args.get('category', 'all')
    status_cov = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_stock_coverage_and_abc(
        start_date, end_date, category_filter=category, status_filter=status_cov
    )

    excel_stream = BiExporter.export_stock_coverage_to_excel(report_data['items'], report_data['summary'], start_date, end_date)
    filename = f"BlingBI_Cobertura_Estoque_ABC_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/stock-coverage/pdf')
def export_stock_coverage_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    category = request.args.get('category', 'all')
    status_cov = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_stock_coverage_and_abc(
        start_date, end_date, category_filter=category, status_filter=status_cov
    )

    pdf_stream = BiExporter.export_stock_coverage_to_pdf(report_data['items'], report_data['summary'], start_date, end_date)
    filename = f"BlingBI_Cobertura_Estoque_ABC_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


# =============================================================================
# PILAR 3: MATRIZ RFM & SEGMENTAÇÃO CRM
# =============================================================================
@bp.route('/rfm')
def rfm():
    cluster = request.args.get('cluster', 'all')
    report_data = StandardReportsEngine.get_rfm_matrix(cluster_filter=cluster)

    return render_template(
        'reports/rfm.html',
        customers=report_data['customers'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        selected_cluster=cluster
    )

@bp.route('/rfm/excel')
def export_rfm_excel():
    cluster = request.args.get('cluster', 'all')
    report_data = StandardReportsEngine.get_rfm_matrix(cluster_filter=cluster)

    excel_stream = BiExporter.export_rfm_to_excel(report_data['customers'], report_data['summary'])
    filename = "BlingBI_Matriz_RFM_Clientes.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/rfm/pdf')
def export_rfm_pdf():
    cluster = request.args.get('cluster', 'all')
    report_data = StandardReportsEngine.get_rfm_matrix(cluster_filter=cluster)

    pdf_stream = BiExporter.export_rfm_to_pdf(report_data['customers'], report_data['summary'])
    filename = "BlingBI_Matriz_RFM_Clientes.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


# =============================================================================
# PILAR 4: DRE GERENCIAL SINTÉTICO & FLUXO DE CAIXA
# =============================================================================
@bp.route('/dre')
def dre():
    period = request.args.get('period', 'this_month')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_dre_statement(start_date, end_date)

    return render_template(
        'reports/dre.html',
        lines=report_data['lines'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        period=period,
        start_date=start_date,
        end_date=end_date
    )

@bp.route('/dre/excel')
def export_dre_excel():
    period = request.args.get('period', 'this_month')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_dre_statement(start_date, end_date)

    excel_stream = BiExporter.export_dre_to_excel(report_data['lines'], report_data['summary'], start_date, end_date)
    filename = f"BlingBI_DRE_Gerencial_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/dre/pdf')
def export_dre_pdf():
    period = request.args.get('period', 'this_month')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_dre_statement(start_date, end_date)

    pdf_stream = BiExporter.export_dre_to_pdf(report_data['lines'], report_data['summary'], start_date, end_date)
    filename = f"BlingBI_DRE_Gerencial_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/cash-flow')
def cash_flow():
    days = int(request.args.get('days', 30))
    report_data = StandardReportsEngine.get_cash_flow_projection(days=days)

    return render_template(
        'reports/cash_flow.html',
        daily_rows=report_data['daily_rows'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        days=days
    )


# =============================================================================
# EXPORTAÇÕES LEGADAS DE VENDAS E PRODUTOS
# =============================================================================
@bp.route('/sales/excel')
def export_sales_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')
    status = request.args.get('status', 'all')
    search = (request.args.get('q') or request.args.get('search') or '').strip()

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_sales_analytics(start_date, end_date, channel=channel, status=status, search=search)

    excel_stream = BiExporter.export_sales_to_excel(analytics['orders'], start_date, end_date)
    filename = f"BlingBI_Vendas_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/sales/pdf')
def export_sales_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')
    status = request.args.get('status', 'all')
    search = (request.args.get('q') or request.args.get('search') or '').strip()

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_sales_analytics(start_date, end_date, channel=channel, status=status, search=search)

    pdf_stream = BiExporter.export_sales_to_pdf(
        analytics['orders'],
        start_date,
        end_date,
        analytics['total_gross'],
        analytics['avg_ticket']
    )
    filename = f"BlingBI_Relatorio_Vendas_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/products/excel')
def export_products_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_products_analytics(start_date, end_date)

    excel_stream = BiExporter.export_products_to_excel(analytics['abc_products'], start_date, end_date)
    filename = f"BlingBI_Curva_ABC_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )
