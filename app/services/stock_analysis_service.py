import io
import logging
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy import func, desc, asc, or_
from app.database import db
from app.models.product import Product, ProductChannelPrice
from app.models.order import Order, OrderItem
from app.models.marketplace_rule import MarketplaceRule
from app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

ACTIVE_CHANNELS = [
    'Mercado Livre',
    'Shopee',
    'Amazon',
    'Site Próprio',
    'Loja Física'
]

class StockAnalysisService:
    """
    Serviço analítico de controle de estoque, preços por canal e auditoria de margens.
    """

    @classmethod
    def get_stock_analysis(cls, filters: dict) -> dict:
        PricingEngine.ensure_default_rules()

        q_text = filters.get('q', '').strip()
        category = filters.get('category', 'all')
        stock_status = filters.get('stock_status', 'all')
        abc_class = filters.get('abc_class', 'all')
        selected_channel = filters.get('channel', 'all')
        sort = filters.get('sort', 'stock_desc')

        min_price = float(filters['min_price']) if filters.get('min_price') else None
        max_price = float(filters['max_price']) if filters.get('max_price') else None
        min_cost = float(filters['min_cost']) if filters.get('min_cost') else None
        max_cost = float(filters['max_cost']) if filters.get('max_cost') else None
        min_margin = float(filters['min_margin']) if filters.get('min_margin') else None
        max_margin = float(filters['max_margin']) if filters.get('max_margin') else None

        # 1. Agregação histórica de vendas dos últimos 60 dias para Curva ABC e velocidade
        sixty_days_ago = datetime.utcnow().date() - timedelta(days=60)
        sales_agg = db.session.query(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label('qty_sold_60d'),
            func.sum(OrderItem.total_price).label('rev_sold_60d')
        ).join(Order, OrderItem.order_id == Order.id).filter(
            Order.order_date >= sixty_days_ago,
            Order.status == 'Atendido'
        ).group_by(OrderItem.product_id).all()

        total_rev_all = sum(float(r.rev_sold_60d or 0.0) for r in sales_agg)
        sorted_sales = sorted(sales_agg, key=lambda x: float(x.rev_sold_60d or 0.0), reverse=True)

        acc = 0.0
        abc_map = {}
        for r in sorted_sales:
            rev = float(r.rev_sold_60d or 0.0)
            acc += rev
            pct = (acc / total_rev_all * 100.0) if total_rev_all > 0 else 100.0
            cl = 'A' if pct <= 80.0 else ('B' if pct <= 95.0 else 'C')
            daily_run_rate = float(r.qty_sold_60d or 0.0) / 60.0
            abc_map[r.product_id] = {
                'abc_class': cl,
                'qty_sold_60d': float(r.qty_sold_60d or 0.0),
                'rev_sold_60d': rev,
                'run_rate': daily_run_rate
            }

        # 2. Query base de produtos
        query = Product.query

        if q_text:
            search_pattern = f"%{q_text}%"
            query = query.filter(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.sku.ilike(search_pattern),
                    Product.category.ilike(search_pattern)
                )
            )

        if category != 'all':
            query = query.filter(Product.category == category)

        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

        if min_cost is not None:
            query = query.filter(or_(Product.purchase_cost >= min_cost, Product.cost >= min_cost))
        if max_cost is not None:
            query = query.filter(or_(Product.purchase_cost <= max_cost, Product.cost <= max_cost))

        raw_products = query.all()

        # 3. Categorias disponíveis para filtro
        all_categories = sorted(list(set(p.category for p in Product.query.with_entities(Product.category).all() if p.category)))

        # 4. Mapeamento de preços por canal pré-carregados
        all_channel_prices = ProductChannelPrice.query.all()
        cp_lookup = {}
        for cp in all_channel_prices:
            if cp.product_id not in cp_lookup:
                cp_lookup[cp.product_id] = {}
            cp_lookup[cp.product_id][cp.channel] = float(cp.price)

        # 5. Processamento dos produtos com métricas de estoque e preços
        processed = []
        tot_skus = len(raw_products)
        tot_out_of_stock = 0
        tot_critical = 0
        tot_capital_cost = 0.0
        tot_potential_sales = 0.0
        margin_sum = 0.0
        margin_count = 0

        for p in raw_products:
            stk = float(p.stock or 0.0)
            min_stk = float(p.min_stock or 5.0)
            base_price = float(p.price or 0.0)
            eff_cost = float(p.purchase_cost if p.purchase_cost and p.purchase_cost > 0 else (p.cost or 0.0))
            
            # Status de Estoque
            if stk <= 0:
                s_status = 'out_of_stock'
                s_label = 'Ruptura (Zerado)'
                s_badge = 'danger'
                tot_out_of_stock += 1
            elif stk <= min_stk:
                s_status = 'critical'
                s_label = 'Crítico / Baixo'
                s_badge = 'warning'
                tot_critical += 1
            elif stk > (min_stk * 4):
                s_status = 'excess'
                s_label = 'Excesso / Sobra'
                s_badge = 'info'
            else:
                s_status = 'normal'
                s_label = 'Equilibrado'
                s_badge = 'success'

            # Filtro por status de estoque
            if stock_status != 'all' and s_status != stock_status:
                continue

            # Dados de curva ABC e giro
            abc_info = abc_map.get(p.id, {'abc_class': 'C', 'qty_sold_60d': 0.0, 'rev_sold_60d': 0.0, 'run_rate': 0.0})
            if abc_class != 'all' and abc_info['abc_class'] != abc_class:
                continue

            # Dias de cobertura
            daily_run_rate = abc_info['run_rate']
            coverage_days = int(stk / daily_run_rate) if daily_run_rate > 0 else (999 if stk > 0 else 0)

            # Margem bruta unitária
            margin_unit = base_price - eff_cost
            margin_pct = (margin_unit / base_price * 100.0) if base_price > 0 else 0.0

            if min_margin is not None and margin_pct < min_margin:
                continue
            if max_margin is not None and margin_pct > max_margin:
                continue

            # Preços por canal
            p_channels = cp_lookup.get(p.id, {})

            # Se filtrou por canal, garante que o produto tem preço ou vendeu naquele canal
            if selected_channel != 'all':
                if selected_channel not in p_channels:
                    # fallback: verifica se o produto tem preço base
                    pass

            # Acumuladores de KPI
            tot_capital_cost += (stk * eff_cost)
            tot_potential_sales += (stk * base_price)
            if base_price > 0:
                margin_sum += margin_pct
                margin_count += 1

            processed.append({
                'id': p.id,
                'bling_id': p.bling_id,
                'sku': p.sku or 'S/ SKU',
                'name': p.name,
                'category': p.category or 'Geral',
                'stock': stk,
                'min_stock': min_stk,
                'cost': float(p.cost or 0.0),
                'purchase_cost': float(p.purchase_cost or 0.0),
                'effective_cost': eff_cost,
                'price': base_price,
                'margin_unit': margin_unit,
                'margin_pct': round(margin_pct, 1),
                'stock_status': s_status,
                'stock_status_label': s_label,
                'stock_status_badge': s_badge,
                'abc_class': abc_info['abc_class'],
                'coverage_days': coverage_days,
                'qty_sold_60d': abc_info['qty_sold_60d'],
                'capital_cost': stk * eff_cost,
                'potential_sales': stk * base_price,
                'channel_prices': p_channels
            })

        # 6. Ordenação
        if sort == 'stock_asc':
            processed.sort(key=lambda x: x['stock'])
        elif sort == 'stock_desc':
            processed.sort(key=lambda x: x['stock'], reverse=True)
        elif sort == 'revenue_desc':
            processed.sort(key=lambda x: x['potential_sales'], reverse=True)
        elif sort == 'margin_desc':
            processed.sort(key=lambda x: x['margin_pct'], reverse=True)
        elif sort == 'cost_desc':
            processed.sort(key=lambda x: x['effective_cost'], reverse=True)
        elif sort == 'name_asc':
            processed.sort(key=lambda x: x['name'].lower())
        elif sort == 'sku_asc':
            processed.sort(key=lambda x: x['sku'].lower())

        avg_margin = round(margin_sum / margin_count, 1) if margin_count > 0 else 0.0

        return {
            'products': processed,
            'channels': ACTIVE_CHANNELS,
            'categories': all_categories,
            'summary': {
                'total_skus': tot_skus,
                'filtered_count': len(processed),
                'out_of_stock_count': tot_out_of_stock,
                'critical_count': tot_critical,
                'total_capital_cost': tot_capital_cost,
                'total_potential_sales': tot_potential_sales,
                'avg_margin': avg_margin
            }
        }

    @classmethod
    def update_product_inline(cls, product_id: int, field: str, value: float, channel: str = None) -> dict:
        """
        Atualiza campos numéricos diretamente na tabela de produtos ou na tabela de preços por canal.
        Campos permitidos: 'cost', 'purchase_cost', 'price', 'min_stock', 'channel_price'.
        """
        try:
            prod = Product.query.get(product_id)
            if not prod:
                return {'success': False, 'message': 'Produto não encontrado.'}

            val = max(0.0, float(value or 0.0))

            if field == 'cost':
                prod.cost = round(val, 2)
            elif field == 'purchase_cost':
                prod.purchase_cost = round(val, 2)
            elif field == 'price':
                prod.price = round(val, 2)
            elif field == 'min_stock':
                prod.min_stock = round(val, 2)
            elif field == 'channel_price':
                if not channel:
                    return {'success': False, 'message': 'Canal de venda não especificado.'}
                PricingEngine.apply_channel_price(product_id, channel, val)
                return {
                    'success': True,
                    'message': f"Preço no canal '{channel}' atualizado para R$ {val:.2f}!",
                    'field': field,
                    'value': val,
                    'channel': channel
                }
            else:
                return {'success': False, 'message': f"Campo '{field}' não permitido para edição."}

            prod.updated_at = datetime.utcnow()
            db.session.commit()

            return {
                'success': True,
                'message': f"Campo '{field}' atualizado com sucesso!",
                'field': field,
                'value': val
            }
        except Exception as e:
            logger.error(f"[StockAnalysisService] Erro no update inline: {e}")
            db.session.rollback()
            return {'success': False, 'message': f"Erro ao atualizar: {str(e)}"}

    @classmethod
    def export_excel(cls, products_data: list[dict]) -> io.BytesIO:
        """Gera planilha Excel profissional com os dados de estoque e preços por canal para conferência/edição."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Análise de Estoque & Preços"
        ws.views.sheetView[0].showGridLines = True

        header_fill = PatternFill(start_color="008B54", end_color="008B54", fill_type="solid")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        num_align = Alignment(horizontal="right", vertical="center")
        text_align = Alignment(horizontal="left", vertical="center")

        headers = [
            "ID", "SKU", "Nome do Produto", "Categoria", "Estoque Atual", "Estoque Mínimo",
            "Custo Base (R$)", "Valor Pago (R$)", "Preço Base (R$)", "Margem (%)",
            "Mercado Livre (R$)", "Shopee (R$)", "Amazon (R$)", "Site Próprio (R$)", "Loja Física (R$)"
        ]

        ws.append(headers)
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for p in products_data:
            cp = p.get('channel_prices', {})
            row = [
                p['id'],
                p['sku'],
                p['name'],
                p['category'],
                p['stock'],
                p['min_stock'],
                p['cost'],
                p['purchase_cost'],
                p['price'],
                p['margin_pct'],
                cp.get('Mercado Livre', ''),
                cp.get('Shopee', ''),
                cp.get('Amazon', ''),
                cp.get('Site Próprio', ''),
                cp.get('Loja Física', '')
            ]
            ws.append(row)

        # Ajuste de largura das colunas
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @classmethod
    def import_excel(cls, file_stream) -> dict:
        """Lê planilha Excel e atualiza em massa Custo, Valor Pago, Preço Base e Preços por Canal."""
        try:
            wb = openpyxl.load_workbook(file_stream, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if len(rows) < 2:
                return {'success': False, 'message': 'Planilha vazia ou sem dados.'}

            headers = [str(h).strip().lower() if h else '' for h in rows[0]]
            
            # Mapeamento dinâmico de cabeçalhos
            sku_idx = next((i for i, h in enumerate(headers) if 'sku' in h), None)
            id_idx = next((i for i, h in enumerate(headers) if h == 'id'), None)
            custo_idx = next((i for i, h in enumerate(headers) if 'custo' in h), None)
            valor_pago_idx = next((i for i, h in enumerate(headers) if 'pago' in h or 'aquisição' in h), None)
            preco_base_idx = next((i for i, h in enumerate(headers) if 'base' in h or 'preço' in h), None)
            
            ml_idx = next((i for i, h in enumerate(headers) if 'mercado' in h), None)
            shopee_idx = next((i for i, h in enumerate(headers) if 'shopee' in h), None)
            amazon_idx = next((i for i, h in enumerate(headers) if 'amazon' in h), None)
            site_idx = next((i for i, h in enumerate(headers) if 'site' in h or 'virtual' in h), None)
            loja_idx = next((i for i, h in enumerate(headers) if 'física' in h or 'loja' in h), None)

            updated_count = 0
            for r in rows[1:]:
                prod = None
                if id_idx is not None and r[id_idx]:
                    prod = Product.query.get(r[id_idx])
                elif sku_idx is not None and r[sku_idx]:
                    prod = Product.query.filter_by(sku=str(r[sku_idx]).strip()).first()

                if not prod:
                    continue

                if custo_idx is not None and r[custo_idx] is not None:
                    try: prod.cost = float(r[custo_idx])
                    except (ValueError, TypeError): pass

                if valor_pago_idx is not None and r[valor_pago_idx] is not None:
                    try: prod.purchase_cost = float(r[valor_pago_idx])
                    except (ValueError, TypeError): pass

                if preco_base_idx is not None and r[preco_base_idx] is not None:
                    try: prod.price = float(r[preco_base_idx])
                    except (ValueError, TypeError): pass

                # Canais
                channel_updates = [
                    (ml_idx, 'Mercado Livre'),
                    (shopee_idx, 'Shopee'),
                    (amazon_idx, 'Amazon'),
                    (site_idx, 'Site Próprio'),
                    (loja_idx, 'Loja Física')
                ]
                for ch_idx, ch_name in channel_updates:
                    if ch_idx is not None and r[ch_idx] is not None and str(r[ch_idx]).strip() != '':
                        try:
                            ch_val = float(r[ch_idx])
                            PricingEngine.apply_channel_price(prod.id, ch_name, ch_val)
                        except (ValueError, TypeError):
                            pass

                prod.updated_at = datetime.utcnow()
                updated_count += 1

            db.session.commit()
            return {
                'success': True,
                'updated_count': updated_count,
                'message': f"Sucesso! {updated_count} produto(s) atualizados a partir da planilha."
            }
        except Exception as e:
            logger.error(f"[StockAnalysisService] Erro ao importar excel: {e}")
            db.session.rollback()
            return {'success': False, 'message': f"Erro ao processar planilha: {str(e)}"}
