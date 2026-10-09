from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from datetime import date
from app.services.bi_analytics import BiAnalytics
from app.services.fashion_bi import FashionBiEngine
from app.services.demo_fashion_data import seed_fashion_demo_data
from app.services.exporter import BiExporter
from app.models.fashion import ConditionalBag
from app.core.feature_registry import FeatureRegistry

bp = Blueprint('fashion', __name__, url_prefix='/fashion')

@bp.route('/')
def index():
    tab = request.args.get('tab', 'block1')
    if not FeatureRegistry.is_enabled(f'fashion.{tab}'):
        # Encontrar primeira aba de moda habilitada
        available = [b for b in ['block1', 'block2', 'block3', 'block4'] if FeatureRegistry.is_enabled(f'fashion.{b}')]
        if available:
            return redirect(url_for('fashion.index', tab=available[0]))
        else:
            flash("O módulo de Moda & Vestuário ou suas abas estão desativados.", "warning")
            return redirect(url_for('dashboard.index'))
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    # Filtros refinados
    seller = request.args.get('seller', 'all')
    category = request.args.get('category', 'all')
    abc_class = request.args.get('abc_class', 'all')
    month_str = request.args.get('month', '')
    month = int(month_str) if month_str.isdigit() else date.today().month
    tier = request.args.get('tier', 'all')
    reason = request.args.get('reason', 'all')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)

    # Auto-popula dados de moda se for a primeira vez acessando e não houver malas
    if ConditionalBag.query.count() == 0:
        try:
            seed_fashion_demo_data()
        except Exception:
            pass

    filter_options = FashionBiEngine.get_filter_options()

    # BLOCO 1: Perfil e Comportamento de Compra
    profiles_data = FashionBiEngine.get_customer_purchase_profiles(
        start_date, end_date, 
        seller=seller if seller != 'all' else None, 
        category=category if category != 'all' else None
    )
    abc_data = FashionBiEngine.get_customer_abc_curve(
        start_date, end_date, 
        seller=seller if seller != 'all' else None,
        abc_class=abc_class if abc_class != 'all' else None
    )
    birthdays_data = FashionBiEngine.get_birthday_customers(target_month=month)

    # BLOCO 2: Movimentação e Preferências de Moda
    bags_data = FashionBiEngine.get_conditional_bags_analytics(
        start_date, end_date, 
        seller=seller if seller != 'all' else None
    )
    top_categories_data = FashionBiEngine.get_top_products_by_category(
        start_date, end_date, 
        category=category if category != 'all' else None
    )
    returns_data = FashionBiEngine.get_returns_and_exchanges_report(
        start_date, end_date, 
        seller=seller if seller != 'all' else None,
        reason=reason if reason != 'all' else None
    )

    # BLOCO 3: Desempenho do Atendimento (KPIs)
    service_kpis = FashionBiEngine.get_service_performance_kpis(
        start_date, end_date, 
        seller=seller if seller != 'all' else None
    )

    # BLOCO 4: Relacionamento e Fidelização (CRM)
    inactives_data = FashionBiEngine.get_inactive_customers_report(
        tier_filter=tier if tier != 'all' else None
    )
    cohort_data = FashionBiEngine.get_repurchase_cohort()
    satisfaction = FashionBiEngine.get_satisfaction_metrics(
        start_date, end_date, 
        seller=seller if seller != 'all' else None
    )

    return render_template(
        'fashion_bi.html',
        active_tab=tab,
        period=period,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        # Filtros ativos
        current_seller=seller,
        current_category=category,
        current_abc_class=abc_class,
        current_month=month,
        current_tier=tier,
        current_reason=reason,
        filter_options=filter_options,
        # Bloco 1
        profiles_data=profiles_data,
        abc_data=abc_data,
        birthdays_data=birthdays_data,
        # Bloco 2
        bags_data=bags_data,
        top_categories_data=top_categories_data,
        returns_data=returns_data,
        # Bloco 3
        service_kpis=service_kpis,
        # Bloco 4
        inactives_data=inactives_data,
        cohort_data=cohort_data,
        satisfaction=satisfaction
    )

@bp.route('/seed-demo', methods=['GET', 'POST'])
def seed_demo():
    seed_fashion_demo_data()
    flash('Dados de demonstração de Varejo de Moda e Customer Success atualizados com sucesso!', 'success')
    return redirect(url_for('fashion.index'))

# =============================================================================
# EXPORTAÇÕES EXCEL (.xlsx)
# =============================================================================

@bp.route('/export/abc')
def export_abc():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller')
    abc_class = request.args.get('abc_class')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    abc_data = FashionBiEngine.get_customer_abc_curve(
        start_date, end_date, 
        seller=seller if seller != 'all' else None,
        abc_class=abc_class if abc_class != 'all' else None
    )

    excel_stream = BiExporter.export_fashion_abc_to_excel(abc_data['customers'], start_date, end_date)
    filename = f"BlingBI_Curva_ABC_Clientes_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/export/inactives')
def export_inactives():
    tier = request.args.get('tier')
    inactives_data = FashionBiEngine.get_inactive_customers_report(tier_filter=tier if tier != 'all' else None)
    excel_stream = BiExporter.export_inactive_customers_to_excel(inactives_data['customers'], date.today())
    filename = f"BlingBI_CRM_Clientes_Inativos_{date.today().strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/export/bags')
def export_bags():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    bags_data = FashionBiEngine.get_conditional_bags_analytics(
        start_date, end_date, 
        seller=seller if seller != 'all' else None
    )

    excel_stream = BiExporter.export_conditional_bags_to_excel(bags_data['bags'], start_date, end_date)
    filename = f"BlingBI_Malas_Condicionais_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

# =============================================================================
# EXPORTAÇÕES PDF (.pdf)
# =============================================================================

@bp.route('/export/abc/pdf')
def export_abc_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller')
    abc_class = request.args.get('abc_class')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    abc_data = FashionBiEngine.get_customer_abc_curve(
        start_date, end_date, 
        seller=seller if seller != 'all' else None,
        abc_class=abc_class if abc_class != 'all' else None
    )

    pdf_stream = BiExporter.export_fashion_abc_to_pdf(abc_data['customers'], abc_data['summary'], start_date, end_date)
    filename = f"BlingBI_Curva_ABC_Clientes_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/export/bags/pdf')
def export_bags_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    bags_data = FashionBiEngine.get_conditional_bags_analytics(
        start_date, end_date, 
        seller=seller if seller != 'all' else None
    )

    pdf_stream = BiExporter.export_conditional_bags_to_pdf(bags_data, start_date, end_date)
    filename = f"BlingBI_Malas_Condicionais_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/export/kpis/pdf')
def export_kpis_pdf():
    period = request.args.get('period', 'last_30_days')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    seller = request.args.get('seller')

    start_date, end_date = BiAnalytics.parse_date_filter(period, start_str, end_str)
    service_kpis = FashionBiEngine.get_service_performance_kpis(
        start_date, end_date, 
        seller=seller if seller != 'all' else None
    )

    pdf_stream = BiExporter.export_service_performance_to_pdf(service_kpis, start_date, end_date)
    filename = f"BlingBI_Desempenho_Atendimento_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@bp.route('/export/inactives/pdf')
def export_inactives_pdf():
    tier = request.args.get('tier')
    inactives_data = FashionBiEngine.get_inactive_customers_report(tier_filter=tier if tier != 'all' else None)
    pdf_stream = BiExporter.export_inactives_to_pdf(inactives_data, date.today())
    filename = f"BlingBI_CRM_Clientes_Inativos_{date.today().strftime('%Y%m%d')}.pdf"

    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

# Aliases de compatibilidade por bloco
@bp.route('/export/block1/pdf')
def export_block1_pdf():
    return export_abc_pdf()

@bp.route('/export/block2/pdf')
def export_block2_pdf():
    return export_bags_pdf()

@bp.route('/export/block3/pdf')
def export_block3_pdf():
    return export_kpis_pdf()

@bp.route('/export/block4/pdf')
def export_block4_pdf():
    return export_inactives_pdf()

