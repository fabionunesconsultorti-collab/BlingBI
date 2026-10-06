from flask import Blueprint, request, send_file
from app.services.bi_analytics import BiAnalytics
from app.services.exporter import BiExporter

bp = Blueprint('reports', __name__, url_prefix='/reports')

@bp.route('/sales/excel')
def export_sales_excel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')
    status = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_sales_analytics(start_date, end_date, channel=channel, status=status)

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

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_sales_analytics(start_date, end_date, channel=channel, status=status)

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
