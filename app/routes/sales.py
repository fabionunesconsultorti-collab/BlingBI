from flask import Blueprint, render_template, request, send_file, jsonify
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.fashion_bi import FashionBiEngine
from app.services.exporter import BiExporter
from app.models.order import Order
from app.models.product import Product
from app.core.feature_registry import requires_feature

bp = Blueprint('sales', __name__, url_prefix='/sales')

# -----------------------------------------------------------------------------
# 1.1 VISÃO GERAL DE VENDAS & PEDIDOS
# -----------------------------------------------------------------------------
@bp.route('/')
@requires_feature('sales.overview')
def index():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')
    status = request.args.get('status', 'all')
    search = (request.args.get('q') or request.args.get('search') or '').strip()

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    analytics = BiAnalytics.get_sales_analytics(start_date, end_date, channel=channel, status=status, search=search)

    return render_template(
        'sales/index.html',
        analytics=analytics,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        channel=channel,
        status=status,
        search=search,
        active_tab='overview'
    )

@bp.route('/orders/<int:order_id>')
def order_detail(order_id):
    """Retorna os dados detalhados de um pedido para a modal e impressão de cupom térmico 78mm."""
    order = Order.query.get_or_404(order_id)

    # Pré-carrega mapa de produtos para resolução ágil e precisa de saldos
    prods = Product.query.all()
    prod_map_id = {p.id: p for p in prods}
    prod_map_bling = {p.bling_id: p for p in prods if p.bling_id}
    prod_map_sku = {p.sku.strip().upper(): p for p in prods if p.sku}
    prod_map_name = {p.name.strip().upper(): p for p in prods if p.name}

    items_list = []
    subtotal_items = 0.0
    for item in order.items:
        # Resolução do produto em cascata para obter saldo em estoque atualizado
        prod = prod_map_id.get(item.product_id) or prod_map_bling.get(item.product_id)
        if not prod and item.sku:
            prod = prod_map_sku.get(item.sku.strip().upper())
        if not prod and item.product_name:
            prod = prod_map_name.get(item.product_name.strip().upper())

        stock_val = float(prod.stock or 0.0) if prod else 0.0

        items_list.append({
            'id': item.id,
            'product_id': item.product_id or (prod.id if prod else None),
            'sku': item.sku or (prod.sku if prod else 'N/A'),
            'product_name': item.product_name,
            'size': item.size or (prod.size if prod else ''),
            'color': item.color or (prod.color if prod else ''),
            'style': item.style or (prod.style if prod else ''),
            'quantity': float(item.quantity or 1),
            'unit_price': float(item.unit_price or 0.0),
            'total_price': float(item.total_price or 0.0),
            'stock': stock_val
        })
        subtotal_items += float(item.total_price or 0.0)

    customer_info = {
        'name': order.customer.name if order.customer else 'Consumidor Final',
        'document': order.customer.document if (order.customer and order.customer.document) else 'Não informado',
        'phone': order.customer.phone if (order.customer and order.customer.phone) else '',
        'email': order.customer.email if (order.customer and order.customer.email) else '',
        'city': order.customer.city if (order.customer and order.customer.city) else '',
        'state': order.customer.state if (order.customer and order.customer.state) else ''
    }

    if subtotal_items <= 0:
        subtotal_items = float(order.total or 0.0) + float(order.discount or 0.0) - float(order.shipping or 0.0)

    data = {
        'id': order.id,
        'bling_id': order.bling_id,
        'number': order.number,
        'order_date': order.order_date.strftime('%d/%m/%Y') if order.order_date else '',
        'created_at': order.created_at.strftime('%d/%m/%Y %H:%M') if order.created_at else '',
        'status': order.status,
        'channel': order.channel or 'Loja Virtual',
        'seller_name': order.seller_name or 'Balcão / Geral',
        'notes': str(order.notes) if (order.notes and isinstance(order.notes, str)) else '',
        'customer': customer_info,
        'items': items_list,
        'financial': {
            'subtotal': round(subtotal_items, 2),
            'discount': round(float(order.discount or 0.0), 2),
            'shipping': round(float(order.shipping or 0.0), 2),
            'total': round(float(order.total or 0.0), 2)
        }
    }
    return jsonify(data)


# -----------------------------------------------------------------------------
# 1.2 PERFORMANCE MULTICANAL & MARGEM POR MARKETPLACE
# -----------------------------------------------------------------------------
@bp.route('/multichannel')
@requires_feature('sales.multichannel', fallback_endpoint='sales.index')
def multichannel():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    channel = request.args.get('channel', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    report_data = StandardReportsEngine.get_multichannel_performance(start_date, end_date, channel_filter=channel)

    all_channels = sorted(list(set(c['channel'] for c in report_data['channels'])))

    return render_template(
        'sales/multichannel.html',
        channels=report_data['channels'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        all_channels=all_channels,
        selected_channel=channel,
        period=period,
        start_date=start_date,
        end_date=end_date,
        active_tab='multichannel'
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
    filename = f"BlingBI_Vendas_Multicanal_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

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
    filename = f"BlingBI_Vendas_Multicanal_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

# -----------------------------------------------------------------------------
# 1.3 PRODUTIVIDADE & METAS POR VENDEDOR / CONSULTOR
# -----------------------------------------------------------------------------
@bp.route('/sellers')
@requires_feature('sales.sellers', fallback_endpoint='sales.index')
def sellers():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    kpis = FashionBiEngine.get_service_performance_kpis(
        start_date, end_date, seller=seller if seller != 'all' else None
    )

    filter_opts = FashionBiEngine.get_filter_options()

    return render_template(
        'sales/sellers.html',
        kpis=kpis,
        sellers=filter_opts.get('sellers', []),
        selected_seller=seller,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        active_tab='sellers'
    )

# -----------------------------------------------------------------------------
# 1.4 MALAS CONDICIONAIS (CONSIGNAÇÃO / HOME DELIVERY)
# -----------------------------------------------------------------------------
@bp.route('/conditional-bags')
@requires_feature('sales.conditional_bags', fallback_endpoint='sales.index')
def conditional_bags():
    period = request.args.get('period', 'last_60_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller', 'all')
    status = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    bags_data = FashionBiEngine.get_conditional_bags_analytics(
        start_date, end_date, 
        seller=seller if seller != 'all' else None,
        status=status if status != 'all' else None
    )
    filter_options = FashionBiEngine.get_filter_options()

    return render_template(
        'sales/conditional_bags.html',
        bags_data=bags_data,
        period=period,
        seller=seller,
        status=status,
        filter_options=filter_options,
        active_tab='conditional_bags'
    )

@bp.route('/conditional-bags/export/excel')
def export_conditional_bags_excel():
    period = request.args.get('period', 'last_60_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller', 'all')
    status = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    bags_data = FashionBiEngine.get_conditional_bags_analytics(
        start_date, end_date, 
        seller=seller if seller != 'all' else None,
        status=status if status != 'all' else None
    )

    excel_stream = BiExporter.export_conditional_bags_to_excel(bags_data['bags'], start_date, end_date)
    return send_file(
        excel_stream,
        as_attachment=True,
        download_name=f"Malas_Condicionais_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.route('/conditional-bags/export/pdf')
def export_conditional_bags_pdf():
    period = request.args.get('period', 'last_60_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller', 'all')
    status = request.args.get('status', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    bags_data = FashionBiEngine.get_conditional_bags_analytics(
        start_date, end_date, 
        seller=seller if seller != 'all' else None,
        status=status if status != 'all' else None
    )

    pdf_stream = BiExporter.export_conditional_bags_to_pdf(bags_data, start_date, end_date)
    return send_file(
        pdf_stream,
        as_attachment=True,
        download_name=f"Malas_Condicionais_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
        mimetype="application/pdf"
    )

# -----------------------------------------------------------------------------
# EXPORTAÇÕES GERAIS DE VENDAS
# -----------------------------------------------------------------------------
@bp.route('/export/excel')
@bp.route('/excel')
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
    return send_file(
        excel_stream,
        as_attachment=True,
        download_name=f"Vendas_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.route('/export/pdf')
@bp.route('/pdf')
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
    return send_file(
        pdf_stream,
        as_attachment=True,
        download_name=f"Vendas_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
        mimetype="application/pdf"
    )

