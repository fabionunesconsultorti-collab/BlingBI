from datetime import datetime
from flask import Blueprint, render_template, request, send_file, redirect, url_for, jsonify, flash
from app.database import db
from app.models.product import Product, ProductChannelPrice
from app.models.marketplace_rule import MarketplaceRule
from app.services.bi_analytics import BiAnalytics
from app.services.standard_reports import StandardReportsEngine
from app.services.fashion_bi import FashionBiEngine
from app.services.exporter import BiExporter
from app.services.stock_analysis_service import StockAnalysisService
from app.services.pricing_engine import PricingEngine
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


# -----------------------------------------------------------------------------
# 2.5 ANÁLISE DE ESTOQUE & GESTÃO DE PREÇOS POR CANAL
# -----------------------------------------------------------------------------
@bp.route('/stock-analysis')
@requires_feature('products.stock_analysis', fallback_endpoint='products.index')
def stock_analysis():
    """Tela de Análise Aprofundada de Estoque, Valores por Canal e Edição de Custos/Preços."""
    enrich_products_attributes_if_needed()
    data = StockAnalysisService.get_stock_analysis(request.args)

    return render_template(
        'products/stock_analysis.html',
        products=data['products'],
        summary=data['summary'],
        channels=data['channels'],
        categories=data['categories'],
        active_tab='stock_analysis',
        filters=request.args
    )


@bp.route('/stock-analysis/update-inline', methods=['POST'])
def stock_analysis_update_inline():
    """Atualiza Custo, Valor Pago, Preço Base ou Preço por Canal inline via AJAX."""
    try:
        payload = request.get_json(silent=True) or request.form
        product_id = payload.get('product_id', type=int) if hasattr(payload, 'get') else None
        field = payload.get('field', '').strip()
        value = payload.get('value')
        channel = payload.get('channel', '').strip() or None

        if not product_id or not field:
            return jsonify({'success': False, 'message': 'Parâmetros inválidos.'}), 400

        result = StockAnalysisService.update_product_inline(
            product_id=product_id,
            field=field,
            value=value,
            channel=channel
        )
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/stock-analysis/export-excel')
def stock_analysis_export_excel():
    """Exporta planilha completa para auditoria e preenchimento de custos/preços."""
    data = StockAnalysisService.get_stock_analysis(request.args)
    excel_stream = StockAnalysisService.export_excel(data['products'])
    filename = f"BlingBI_Analise_Estoque_Precos_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


@bp.route('/stock-analysis/import-excel', methods=['POST'])
def stock_analysis_import_excel():
    """Importa planilha Excel preenchida para atualizar custos e preços em lote."""
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado para importação.', 'warning')
        return redirect(url_for('products.stock_analysis'))

    file = request.files['file']
    if not file or file.filename == '':
        flash('Selecione uma planilha válida (.xlsx).', 'warning')
        return redirect(url_for('products.stock_analysis'))

    result = StockAnalysisService.import_excel(file.stream)
    if result.get('success'):
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')

    return redirect(url_for('products.stock_analysis'))


# -----------------------------------------------------------------------------
# 2.6 PRECIFICAÇÃO AUTOMÁTICA EM MARKETPLACES (MARKUP REVERSO & DRE UNITÁRIO)
# -----------------------------------------------------------------------------
@bp.route('/pricing')
@requires_feature('products.pricing', fallback_endpoint='products.index')
def pricing():
    """Tela de Precificação Inteligente de Marketplaces com DRE Unitário e aplicação em lote."""
    # Sincroniza automaticamente canais configurados no Bling e pedidos históricos
    try:
        PricingEngine.sync_channels_from_bling()
    except Exception as e:
        logger.warning(f"Aviso ao sincronizar canais no carregamento da precificação: {e}")

    rules = PricingEngine.get_all_rules()
    selected_channel = request.args.get('channel', rules[0].channel if rules else 'Mercado Livre Clássico')
    active_rule = PricingEngine.get_rule_by_channel(selected_channel) or (rules[0] if rules else None)

    # Verificação de preços existentes no canal local
    has_synced_prices = False
    if active_rule:
        has_synced_prices = ProductChannelPrice.query.filter_by(channel=active_rule.channel).count() > 0

    q = request.args.get('q', '').strip()
    category = request.args.get('category', 'all')
    custom_margin = request.args.get('custom_margin', type=float)

    query = Product.query
    if q:
        query = query.filter(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%")))
    if category != 'all':
        query = query.filter(Product.category == category)

    raw_prods = query.order_by(Product.name.asc()).limit(150).all()

    # Simula para cada produto o preço ideal no canal ativo
    simulated_products = []
    if active_rule:
        for p in raw_prods:
            calc = PricingEngine.calculate_product_channel_pricing(
                p, active_rule, custom_target_margin=custom_margin
            )
            simulated_products.append(calc)

    all_categories = sorted(list(set(p.category for p in Product.query.with_entities(Product.category).all() if p.category)))

    return render_template(
        'products/marketplace_pricing.html',
        rules=rules,
        active_rule=active_rule,
        selected_channel=selected_channel,
        products=simulated_products,
        categories=all_categories,
        selected_category=category,
        custom_margin=custom_margin,
        q=q,
        has_synced_prices=has_synced_prices,
        active_tab='pricing'
    )


@bp.route('/pricing/rules', methods=['GET', 'POST'])
def pricing_rules():
    """Consulta ou edita os parâmetros e taxas de um marketplace."""
    if request.method == 'GET':
        rules = PricingEngine.get_all_rules()
        return jsonify({'success': True, 'rules': [r.to_dict() for r in rules]})

    try:
        data = request.get_json(silent=True) or request.form
        raw_rule_id = data.get('rule_id')
        if not raw_rule_id:
            return jsonify({'success': False, 'message': 'ID da regra não informado.'}), 400
        try:
            rule_id = int(raw_rule_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'ID da regra inválido.'}), 400

        rule = MarketplaceRule.query.get(rule_id)
        if not rule:
            return jsonify({'success': False, 'message': 'Regra de canal não encontrada.'}), 404

        def _get_float(key, current_val):
            val = data.get(key)
            if val is None or str(val).strip() == '':
                return current_val
            try:
                return float(str(val).replace(',', '.'))
            except (ValueError, TypeError):
                return current_val

        rule.commission_percent = _get_float('commission_percent', rule.commission_percent)
        rule.fixed_fee = _get_float('fixed_fee', rule.fixed_fee)
        rule.fixed_fee_threshold = _get_float('fixed_fee_threshold', rule.fixed_fee_threshold)
        rule.free_shipping_threshold = _get_float('free_shipping_threshold', rule.free_shipping_threshold)
        rule.default_shipping_cost = _get_float('default_shipping_cost', rule.default_shipping_cost)
        rule.tax_percent = _get_float('tax_percent', rule.tax_percent)
        rule.operational_cost_percent = _get_float('operational_cost_percent', rule.operational_cost_percent)
        rule.target_margin_percent = _get_float('target_margin_percent', rule.target_margin_percent)
        rule.updated_at = datetime.utcnow()

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f"Regras do canal '{rule.channel}' atualizadas com sucesso!",
            'rule': rule.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/pricing/sync-channels', methods=['POST'])
def pricing_sync_channels():
    """Endpoint para sincronizar/atualizar canais de venda e marketplaces do Bling sob demanda."""
    try:
        synced_rules = PricingEngine.sync_channels_from_bling()
        return jsonify({
            'success': True,
            'message': f"{len(synced_rules)} canais de venda verificados e sincronizados com sucesso!",
            'channels': [r.to_dict() for r in synced_rules]
        })
    except Exception as e:
        logger.error(f"[Pricing] Erro ao sincronizar canais: {e}")
        return jsonify({'success': False, 'message': f"Erro ao sincronizar canais: {str(e)}"}), 500


@bp.route('/pricing/sync-store-prices', methods=['POST'])
def pricing_sync_store_prices():
    """Sincroniza sob demanda os preços já cadastrados no canal no Bling (/produtos/lojas)."""
    try:
        data = request.get_json(silent=True) or request.form
        channel = data.get('channel', '').strip()
        rule = PricingEngine.get_rule_by_channel(channel)
        if not rule or not rule.bling_loja_id:
            return jsonify({
                'success': False,
                'message': f"O canal '{channel}' não possui vínculo ativo com loja no Bling."
            }), 400

        count = PricingEngine.sync_channel_prices_from_bling(rule)
        return jsonify({
            'success': True,
            'message': f"{count} preço(s) de produto sincronizado(s) com sucesso a partir do Bling para '{rule.base_marketplace_name}'!",
            'synced_count': count
        })
    except Exception as e:
        logger.error(f"[Pricing] Erro ao sincronizar preços do Bling: {e}")
        return jsonify({'success': False, 'message': f"Erro ao sincronizar preços: {str(e)}"}), 500


@bp.route('/pricing/simulate', methods=['POST'])
def pricing_simulate():
    """Calculadora interativa: simula em tempo real o preço e DRE unitário de um produto."""
    try:
        data = request.get_json(silent=True) or request.form
        cost = float(data.get('cost', 10.0))
        commission_percent = float(data.get('commission_percent', 14.0))
        tax_percent = float(data.get('tax_percent', 6.0))
        operational_percent = float(data.get('operational_percent', 3.0))
        target_margin_percent = float(data.get('target_margin_percent', 20.0))
        fixed_fee = float(data.get('fixed_fee', 0.0))
        fixed_fee_threshold = float(data.get('fixed_fee_threshold', 79.0))
        free_shipping_threshold = float(data.get('free_shipping_threshold', 79.0))
        shipping_cost = float(data.get('shipping_cost', 0.0))

        calc = PricingEngine.calculate_price_for_cost(
            cost=cost,
            commission_percent=commission_percent,
            tax_percent=tax_percent,
            operational_percent=operational_percent,
            target_margin_percent=target_margin_percent,
            fixed_fee=fixed_fee,
            fixed_fee_threshold=fixed_fee_threshold,
            free_shipping_threshold=free_shipping_threshold,
            shipping_cost=shipping_cost
        )
        return jsonify({'success': True, 'calculation': calc})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/pricing/apply', methods=['POST'])
def pricing_apply():
    """Aplica preços calculados a um único produto ou a uma lista em lote."""
    try:
        data = request.get_json(silent=True) or request.form
        product_ids = data.get('product_ids', [])
        channel = data.get('channel', '').strip()
        custom_target_margin = data.get('custom_target_margin')
        if custom_target_margin is not None:
            try: custom_target_margin = float(custom_target_margin)
            except (ValueError, TypeError): custom_target_margin = None

        if isinstance(product_ids, str):
            product_ids = [int(p.strip()) for p in product_ids.split(',') if p.strip()]
        elif isinstance(product_ids, int):
            product_ids = [product_ids]

        if not product_ids or not channel:
            return jsonify({'success': False, 'message': 'Produtos ou canal não informados.'}), 400

        result = PricingEngine.apply_prices_in_batch(
            product_ids=product_ids,
            channel=channel,
            custom_target_margin=custom_target_margin
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



