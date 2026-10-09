from flask import Blueprint, render_template, request, send_file, jsonify
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.fashion_bi import FashionBiEngine
from app.services.exporter import BiExporter
from app.services.customer_filters import CustomerFilterService
from app.models.customer import Customer
from app.models.order import Order
from app.models.fashion import ConditionalBag
from app.core.feature_registry import requires_feature

bp = Blueprint('customers', __name__, url_prefix='/customers')

# -----------------------------------------------------------------------------
# 3.1 BASE DE CLIENTES & SEGMENTAÇÃO CRM MULTIATRIBUTO
# -----------------------------------------------------------------------------
@bp.route('/')
@requires_feature('customers.overview')
def index():
    filter_type = request.args.get('filter_type', 'best_customers')
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    search = request.args.get('q')
    state = request.args.get('state', 'all')
    sort_by = request.args.get('sort')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)

    data = CustomerFilterService.get_filtered_customers(
        filter_type=filter_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        search=search,
        state=state,
        sort_by=sort_by
    )

    return render_template(
        'customers/index.html',
        customers=data['customers'],
        summary=data['summary'],
        filter_meta=data['filter_meta'],
        available_states=data['available_states'],
        available_filter_types=data['available_filter_types'],
        active_tab='base'
    )

# -----------------------------------------------------------------------------
# 3.2 MATRIZ RFM (CLUSTERS DE FIDELIZAÇÃO E REATIVAÇÃO)
# -----------------------------------------------------------------------------
@bp.route('/rfm')
@requires_feature('customers.rfm', fallback_endpoint='customers.index')
def rfm():
    cluster = request.args.get('cluster', 'all')
    report_data = StandardReportsEngine.get_rfm_matrix(cluster_filter=cluster)

    return render_template(
        'customers/rfm.html',
        customers=report_data['customers'],
        summary=report_data['summary'],
        charts=report_data['charts'],
        selected_cluster=cluster,
        active_tab='rfm'
    )

@bp.route('/rfm/excel')
def export_rfm_excel():
    cluster = request.args.get('cluster', 'all')
    report_data = StandardReportsEngine.get_rfm_matrix(cluster_filter=cluster)

    excel_stream = BiExporter.export_rfm_to_excel(report_data['customers'], report_data['summary'])
    filename = "BlingBI_Clientes_Matriz_RFM.xlsx"

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
    filename = "BlingBI_Clientes_Matriz_RFM.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

# -----------------------------------------------------------------------------
# 3.3 CURVA ABC DE CLIENTES (REGRA 80/20)
# -----------------------------------------------------------------------------
@bp.route('/abc')
@requires_feature('customers.abc', fallback_endpoint='customers.index')
def abc():
    period = request.args.get('period', 'last_60_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    abc_class = request.args.get('abc_class', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    abc_data = FashionBiEngine.get_customer_abc_curve(
        start_date, end_date, abc_class=abc_class if abc_class != 'all' else None
    )

    return render_template(
        'customers/abc.html',
        abc_data=abc_data,
        selected_class=abc_class,
        period=period,
        active_tab='abc'
    )

# -----------------------------------------------------------------------------
# 3.4 PERFIL DE CONSUMO & PREFERÊNCIAS (MODA ESTATÍSTICA)
# -----------------------------------------------------------------------------
@bp.route('/profiles')
@requires_feature('customers.profiles', fallback_endpoint='customers.index')
def profiles():
    period = request.args.get('period', 'last_60_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    profile_data = FashionBiEngine.get_customer_purchase_profiles(start_date, end_date)

    return render_template(
        'customers/profiles.html',
        profile_data=profile_data,
        period=period,
        active_tab='profiles'
    )

# -----------------------------------------------------------------------------
# 3.5 ANIVERSARIANTES DO MÊS
# -----------------------------------------------------------------------------
@bp.route('/birthdays')
@requires_feature('customers.birthdays', fallback_endpoint='customers.index')
def birthdays():
    from datetime import date
    month = request.args.get('month', type=int)
    birthdays_data = FashionBiEngine.get_birthday_customers(target_month=month)
    filter_opts = FashionBiEngine.get_filter_options()

    return render_template(
        'customers/birthdays.html',
        birthdays_data=birthdays_data,
        months=filter_opts.get('months', []),
        selected_month=month or date.today().month,
        active_tab='birthdays'
    )

# -----------------------------------------------------------------------------
# 3.6 SATISFAÇÃO & NPS PÓS-VENDA
# -----------------------------------------------------------------------------
@bp.route('/nps')
@requires_feature('customers.nps', fallback_endpoint='customers.index')
def nps():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    nps_data = FashionBiEngine.get_satisfaction_metrics(start_date, end_date, seller=seller if seller != 'all' else None)
    filter_opts = FashionBiEngine.get_filter_options()

    return render_template(
        'customers/nps.html',
        nps_data=nps_data,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        seller=seller,
        sellers=filter_opts.get('sellers', []),
        active_tab='nps'
    )

# -----------------------------------------------------------------------------
# DETALHES DO CLIENTE (MODAL JSON)
# -----------------------------------------------------------------------------
@bp.route('/<int:customer_id>/details')
def customer_details(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    orders = Order.query.filter_by(customer_id=customer.id).order_by(Order.order_date.desc()).limit(10).all()
    bags = ConditionalBag.query.filter_by(customer_id=customer.id).order_by(ConditionalBag.sent_date.desc()).all()

    orders_data = [
        {
            'id': o.id,
            'number': o.number,
            'order_date': o.order_date.strftime('%d/%m/%Y') if o.order_date else '',
            'total': o.total,
            'status': o.status,
            'items_count': len(o.items) if o.items else 0
        }
        for o in orders
    ]

    bags_data = [
        {
            'id': b.id,
            'bag_code': b.bag_code,
            'sent_date': b.sent_date.strftime('%d/%m/%Y') if b.sent_date else '',
            'items_sent': b.items_sent,
            'items_invoiced': b.items_invoiced,
            'items_returned': b.items_returned,
            'conversion_rate': b.conversion_rate,
            'status': b.status
        }
        for b in bags
    ]

    return jsonify({
        'id': customer.id,
        'bling_id': customer.bling_id,
        'name': customer.name,
        'document': customer.document or 'Não informado',
        'person_type': customer.person_type or 'F',
        'phone': customer.phone or 'Não informado',
        'email': customer.email or 'Não informado',
        'city': customer.city or '',
        'state': customer.state or '',
        'preferred_size': customer.preferred_size or 'M',
        'preferred_style': customer.preferred_style or 'Casual',
        'orders': orders_data,
        'bags': bags_data
    })

# -----------------------------------------------------------------------------
# EXPORTAÇÕES (EXCEL & PDF)
# -----------------------------------------------------------------------------
@bp.route('/export/excel')
@bp.route('/excel')
def export_customers_excel():
    filter_type = request.args.get('filter_type', 'best_customers')
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    search = request.args.get('q')
    state = request.args.get('state', 'all')
    sort_by = request.args.get('sort')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)

    data = CustomerFilterService.get_filtered_customers(
        filter_type=filter_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        search=search,
        state=state,
        sort_by=sort_by
    )

    excel_stream = BiExporter.export_filtered_customers_to_excel(
        data['customers'], data['summary'], data['filter_meta']
    )
    filename = f"BlingBI_Clientes_{filter_type}_{period}.xlsx"
    return send_file(
        excel_stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.route('/export/pdf')
@bp.route('/pdf')
def export_customers_pdf():
    filter_type = request.args.get('filter_type', 'best_customers')
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    search = request.args.get('q')
    state = request.args.get('state', 'all')
    sort_by = request.args.get('sort')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)

    data = CustomerFilterService.get_filtered_customers(
        filter_type=filter_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        search=search,
        state=state,
        sort_by=sort_by
    )

    pdf_stream = BiExporter.export_filtered_customers_to_pdf(
        data['customers'], data['summary'], data['filter_meta']
    )
    filename = f"BlingBI_Clientes_{filter_type}_{period}.pdf"
    return send_file(
        pdf_stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


