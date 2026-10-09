from datetime import datetime
from flask import Blueprint, render_template, request, send_file, redirect, url_for
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.fashion_bi import FashionBiEngine
from app.services.exporter import BiExporter
from app.services.product_attributes import (
    search_catalog_products,
    get_catalog_filter_options,
    enrich_products_attributes_if_needed,
    get_inventory_catalog_analytics
)

from app.core.feature_registry import requires_feature

bp = Blueprint('products', __name__, url_prefix='/products')

# -----------------------------------------------------------------------------
# 2.1 INVENTÁRIO E CATÁLOGO DE PRODUTOS (COM BUSCA GERAL POR TAMANHO, COR E NOME)
# -----------------------------------------------------------------------------
@bp.route('/')
@requires_feature('products.overview')
def index():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    q = request.args.get('q', '').strip()
    size = request.args.get('size', 'all')
    color = request.args.get('color', 'all')
    stock_status = request.args.get('stock_status', 'all')
    abc_class = request.args.get('abc_class', 'all')
    status = request.args.get('status', 'all')
    sort = request.args.get('sort', 'name_asc')

    enrich_products_attributes_if_needed()
    filter_options = get_catalog_filter_options()

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = get_inventory_catalog_analytics(
        start_date, end_date,
        q=q,
        size=size,
        color=color,
        stock_status=stock_status,
        abc_class=abc_class,
        status=status,
        sort=sort
    )

    return render_template(
        'products/index.html',
        analytics=analytics,
        products=analytics['products'],
        summary=analytics,
        filter_options=filter_options,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        q=q,
        size=size,
        color=color,
        stock_status=stock_status,
        abc_class=abc_class,
        status=status,
        sort=sort,
        active_tab='catalog'
    )

# -----------------------------------------------------------------------------
# 2.2 CURVA ABC DE PRODUTOS (PARETO)
# -----------------------------------------------------------------------------
@bp.route('/abc')
@requires_feature('products.abc', fallback_endpoint='products.index')
def abc():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_products_analytics(start_date, end_date)

    return render_template(
        'products/abc.html',
        analytics=analytics,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        active_tab='abc'
    )

# -----------------------------------------------------------------------------
# 2.3 DIAS DE COBERTURA DE ESTOQUE & ALERTAS DE RUPTURA
# -----------------------------------------------------------------------------
@bp.route('/stock-coverage')
@requires_feature('products.stock_coverage', fallback_endpoint='products.index')
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
        'products/stock_coverage.html',
        items=report_data['items'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        categories=categories,
        selected_category=category,
        selected_status=status_cov,
        period=period,
        start_date=start_date,
        end_date=end_date,
        active_tab='coverage'
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
    filename = f"BlingBI_Produtos_Cobertura_Estoque_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

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
    filename = f"BlingBI_Produtos_Cobertura_Estoque_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

# -----------------------------------------------------------------------------
# 2.4 TROCAS & DEVOLUÇÕES POR SKU
# -----------------------------------------------------------------------------
@bp.route('/returns')
@requires_feature('products.returns', fallback_endpoint='products.index')
def returns():
    period = request.args.get('period', 'last_60_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    reason = request.args.get('reason', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    returns_data = FashionBiEngine.get_returns_and_exchanges_report(
        start_date, end_date, reason=reason if reason != 'all' else None
    )

    filter_opts = FashionBiEngine.get_filter_options()

    return render_template(
        'products/returns.html',
        returns_data=returns_data,
        reasons=filter_opts.get('reasons', []),
        selected_reason=reason,
        period=period,
        active_tab='returns'
    )

# -----------------------------------------------------------------------------
# EXPORTAÇÃO INVENTÁRIO & CATÁLOGO DE PRODUTOS (EXCEL & PDF)
# -----------------------------------------------------------------------------
@bp.route('/export/excel')
@bp.route('/excel')
def export_abc_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    q = request.args.get('q', '').strip()
    size = request.args.get('size', 'all')
    color = request.args.get('color', 'all')
    stock_status = request.args.get('stock_status', 'all')
    abc_class = request.args.get('abc_class', 'all')
    status = request.args.get('status', 'all')
    sort = request.args.get('sort', 'name_asc')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = get_inventory_catalog_analytics(
        start_date, end_date,
        q=q, size=size, color=color, stock_status=stock_status, abc_class=abc_class, status=status, sort=sort
    )

    excel_stream = BiExporter.export_product_search_to_excel(analytics['products'], analytics)
    filename = f"BlingBI_Inventario_Catalogo_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/export/pdf')
@bp.route('/pdf')
def export_abc_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    q = request.args.get('q', '').strip()
    size = request.args.get('size', 'all')
    color = request.args.get('color', 'all')
    stock_status = request.args.get('stock_status', 'all')
    abc_class = request.args.get('abc_class', 'all')
    status = request.args.get('status', 'all')
    sort = request.args.get('sort', 'name_asc')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = get_inventory_catalog_analytics(
        start_date, end_date,
        q=q, size=size, color=color, stock_status=stock_status, abc_class=abc_class, status=status, sort=sort
    )

    pdf_stream = BiExporter.export_product_search_to_pdf(analytics['products'], analytics)
    filename = f"BlingBI_Inventario_Catalogo_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


# -----------------------------------------------------------------------------
# REDIRECIONAMENTOS DE COMPATIBILIDADE DA BUSCA PARA O INVENTÁRIO PRINCIPAL
# -----------------------------------------------------------------------------
@bp.route('/search')
def search():
    """Redireciona para a aba unificada de Inventário e Catálogo de Produtos."""
    return redirect(url_for('products.index', **request.args))

@bp.route('/search/excel')
def export_search_excel():
    return redirect(url_for('products.export_abc_excel', **request.args))

@bp.route('/search/pdf')
def export_search_pdf():
    return redirect(url_for('products.export_abc_pdf', **request.args))


