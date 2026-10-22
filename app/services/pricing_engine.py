import logging
from datetime import datetime
from app.database import db
from app.models.marketplace_rule import MarketplaceRule
from app.models.product import Product, ProductChannelPrice

logger = logging.getLogger(__name__)

DEFAULT_RULES = [
    {
        'channel': 'Mercado Livre Clássico',
        'channel_display_name': 'Mercado Livre (Anúncio Clássico)',
        'icon': '🟡',
        'commission_percent': 13.0,
        'fixed_fee': 6.50,
        'fixed_fee_threshold': 79.0,
        'free_shipping_threshold': 79.0,
        'default_shipping_cost': 22.50,
        'tax_percent': 6.0,
        'operational_cost_percent': 3.0,
        'target_margin_percent': 20.0,
    },
    {
        'channel': 'Mercado Livre Premium',
        'channel_display_name': 'Mercado Livre (Anúncio Premium 12x)',
        'icon': '🟡',
        'commission_percent': 18.0,
        'fixed_fee': 6.50,
        'fixed_fee_threshold': 79.0,
        'free_shipping_threshold': 79.0,
        'default_shipping_cost': 22.50,
        'tax_percent': 6.0,
        'operational_cost_percent': 3.0,
        'target_margin_percent': 20.0,
    },
    {
        'channel': 'Shopee Padrão',
        'channel_display_name': 'Shopee (Comissão Padrão 14%)',
        'icon': '🟠',
        'commission_percent': 14.0,
        'fixed_fee': 4.00,
        'fixed_fee_threshold': 999999.0, # Sempre cobra taxa fixa por item
        'free_shipping_threshold': 999999.0,
        'default_shipping_cost': 0.0, # Frete pago pela Shopee/comprador
        'tax_percent': 6.0,
        'operational_cost_percent': 3.0,
        'target_margin_percent': 20.0,
    },
    {
        'channel': 'Shopee Frete Grátis',
        'channel_display_name': 'Shopee (Programa Frete Grátis Extra 20%)',
        'icon': '🟠',
        'commission_percent': 20.0,
        'fixed_fee': 4.00,
        'fixed_fee_threshold': 999999.0,
        'free_shipping_threshold': 999999.0,
        'default_shipping_cost': 0.0,
        'tax_percent': 6.0,
        'operational_cost_percent': 3.0,
        'target_margin_percent': 20.0,
    },
    {
        'channel': 'Amazon Brasil',
        'channel_display_name': 'Amazon Brasil',
        'icon': '📦',
        'commission_percent': 15.0,
        'fixed_fee': 0.0,
        'fixed_fee_threshold': 0.0,
        'free_shipping_threshold': 999999.0,
        'default_shipping_cost': 0.0,
        'tax_percent': 6.0,
        'operational_cost_percent': 3.0,
        'target_margin_percent': 20.0,
    },
    {
        'channel': 'Magazine Luiza',
        'channel_display_name': 'Magazine Luiza (Magalu Marketplace)',
        'icon': '🔵',
        'commission_percent': 16.0,
        'fixed_fee': 3.00,
        'fixed_fee_threshold': 79.0,
        'free_shipping_threshold': 79.0,
        'default_shipping_cost': 19.90,
        'tax_percent': 6.0,
        'operational_cost_percent': 3.0,
        'target_margin_percent': 20.0,
    },
    {
        'channel': 'Site Próprio',
        'channel_display_name': 'E-commerce / Loja Virtual Própria',
        'icon': '🌐',
        'commission_percent': 3.5, # Taxa gateway cartão/Pix
        'fixed_fee': 0.0,
        'fixed_fee_threshold': 0.0,
        'free_shipping_threshold': 999999.0,
        'default_shipping_cost': 0.0,
        'tax_percent': 6.0,
        'operational_cost_percent': 3.0,
        'target_margin_percent': 25.0,
    },
    {
        'channel': 'Loja Física / Venda Direta',
        'channel_display_name': 'Loja Física / Balcão / WhatsApp VIP',
        'icon': '🏬',
        'commission_percent': 2.0, # Taxa média de cartão
        'fixed_fee': 0.0,
        'fixed_fee_threshold': 0.0,
        'free_shipping_threshold': 999999.0,
        'default_shipping_cost': 0.0,
        'tax_percent': 6.0,
        'operational_cost_percent': 2.0,
        'target_margin_percent': 35.0,
    }
]


class PricingEngine:
    """
    Motor analítico de precificação e formação de preço de venda (Markup Reverso)
    para Marketplaces, canais digitais e varejo físico.
    """

    @classmethod
    def ensure_default_rules(cls):
        """Garante que as regras padrão de marketplaces estejam criadas no banco do tenant."""
        try:
            for rule_data in DEFAULT_RULES:
                rule = MarketplaceRule.query.filter_by(channel=rule_data['channel']).first()
                if not rule:
                    rule = MarketplaceRule(
                        channel=rule_data['channel'],
                        channel_display_name=rule_data['channel_display_name'],
                        icon=rule_data['icon'],
                        commission_percent=rule_data['commission_percent'],
                        fixed_fee=rule_data['fixed_fee'],
                        fixed_fee_threshold=rule_data['fixed_fee_threshold'],
                        free_shipping_threshold=rule_data['free_shipping_threshold'],
                        default_shipping_cost=rule_data['default_shipping_cost'],
                        tax_percent=rule_data['tax_percent'],
                        operational_cost_percent=rule_data['operational_cost_percent'],
                        target_margin_percent=rule_data['target_margin_percent']
                    )
                    db.session.add(rule)
            db.session.commit()
        except Exception as e:
            logger.error(f"[PricingEngine] Erro ao inicializar regras padrão: {e}")
            db.session.rollback()

    @classmethod
    def get_all_rules(cls) -> list[MarketplaceRule]:
        """Retorna todas as regras cadastradas e ativas."""
        cls.ensure_default_rules()
        active_rules = MarketplaceRule.query.filter_by(is_active=True).order_by(MarketplaceRule.id).all()
        if active_rules:
            return active_rules
        return MarketplaceRule.query.order_by(MarketplaceRule.id).all()

    @classmethod
    def sync_channels_from_bling(cls) -> list[MarketplaceRule]:
        """
        Sincroniza os canais de venda configurados no Bling (/canais-venda) e canais
        encontrados nos pedidos da base de dados, garantindo que todo marketplace ativo
        possua regras de precificação no sistema.
        """
        cls.ensure_default_rules()

        # 1. Busca canais diretamente da API v3 do Bling se configurado
        bling_channels = []
        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if client.is_configured():
                bling_channels = client.get_sales_channels() or []
        except Exception as e:
            logger.warning(f"[PricingEngine] Não foi possível consultar /canais-venda no Bling: {e}")

        has_real_bling_channels = False
        active_loja_ids = set()

        if bling_channels:
            active_bling = [c for c in bling_channels if c.get('situacao', 1) == 1]
            if active_bling:
                has_real_bling_channels = True

                for ch in active_bling:
                    loja_id = ch.get('id')
                    tipo = (ch.get('tipo') or '').strip()
                    ch_desc = (ch.get('descricao') or '').strip()
                    if not ch_desc:
                        continue

                    active_loja_ids.add(loja_id)
                    ch_lower = ch_desc.lower()
                    tipo_lower = tipo.lower()

                    # Define comissão padrão e ícone por marketplace
                    comm = 16.0
                    fixed_fee = 0.0
                    fixed_thresh = 0.0
                    free_ship = 999999.0
                    ship_cost = 0.0
                    icon = '🛒'
                    channel_name = ch_desc

                    if 'viavarejo' in tipo_lower or 'via varejo' in ch_lower or 'casas bahia' in ch_lower:
                        channel_name = 'Casas Bahia VIA VAREJO'
                        comm = 16.0
                        icon = '🛍️'
                    elif 'madeiramadeira' in tipo_lower or 'madeira madeira' in ch_lower:
                        channel_name = 'Madeira Madeira'
                        comm = 16.0
                        icon = '🪑'
                    elif 'integracommerce' in tipo_lower or 'magalu' in ch_lower or 'magazine luiza' in ch_lower:
                        channel_name = 'Magazine Luiza'
                        comm = 16.0
                        fixed_fee = 3.0
                        fixed_thresh = 79.0
                        icon = '🔵'
                    elif 'tray' in tipo_lower or 'tray' in ch_lower:
                        channel_name = 'Site Próprio (Tray)'
                        comm = 3.5
                        icon = '🌐'
                    elif 'lojafisica' in tipo_lower or 'física' in ch_lower or 'fisica' in ch_lower:
                        channel_name = 'Loja Física'
                        comm = 2.0
                        icon = '🏬'
                    elif 'mercadolivre' in tipo_lower or 'mercado livre' in ch_lower:
                        channel_name = 'Mercado Livre Clássico'
                        comm = 13.0
                        fixed_fee = 6.5
                        fixed_thresh = 79.0
                        icon = '🟡'
                    elif 'shopee' in tipo_lower or 'shopee' in ch_lower:
                        channel_name = 'Shopee Padrão'
                        comm = 14.0
                        fixed_fee = 4.0
                        fixed_thresh = 999999.0
                        icon = '🟠'
                    elif 'amazon' in tipo_lower or 'amazon' in ch_lower:
                        channel_name = 'Amazon Brasil'
                        comm = 15.0
                        icon = '📦'

                    # Busca se já existe regra cadastrada para esta loja no Bling
                    rule = MarketplaceRule.query.filter(
                        (MarketplaceRule.bling_loja_id == loja_id) |
                        (MarketplaceRule.channel == channel_name) |
                        (MarketplaceRule.channel == ch_desc) |
                        (MarketplaceRule.channel_display_name == ch_desc)
                    ).first()

                    if not rule:
                        rule = MarketplaceRule(
                            channel=channel_name,
                            channel_display_name=ch_desc,
                            icon=icon,
                            commission_percent=comm,
                            fixed_fee=fixed_fee,
                            fixed_fee_threshold=fixed_thresh,
                            free_shipping_threshold=free_ship,
                            default_shipping_cost=ship_cost,
                            tax_percent=6.0,
                            operational_cost_percent=3.0,
                            target_margin_percent=20.0,
                            bling_loja_id=loja_id,
                            bling_tipo=tipo,
                            is_active=True
                        )
                        db.session.add(rule)
                    else:
                        rule.channel_display_name = ch_desc
                        rule.bling_loja_id = loja_id
                        rule.bling_tipo = tipo
                        rule.is_active = True

                # Desativa regras antigas que não pertencem às lojas ativas no Bling desta conta
                for r in MarketplaceRule.query.all():
                    if r.bling_loja_id and r.bling_loja_id not in active_loja_ids:
                        r.is_active = False
                    elif not r.bling_loja_id:
                        r.is_active = False

                db.session.commit()

        # 2. Se não houver canais reais no Bling configurados, fallback para pedidos históricos e regras padrão
        if not has_real_bling_channels:
            order_channels = []
            try:
                from app.models.order import Order
                raw_channels = db.session.query(Order.channel).filter(
                    Order.channel != None, 
                    Order.channel != ''
                ).distinct().all()
                order_channels = [r[0].strip() for r in raw_channels if r[0] and r[0].strip()]
            except Exception as e:
                logger.warning(f"[PricingEngine] Erro ao consultar canais da tabela de pedidos: {e}")

            for c_name in order_channels:
                rule = MarketplaceRule.query.filter_by(channel=c_name).first()
                if not rule:
                    rule = MarketplaceRule(
                        channel=c_name,
                        channel_display_name=c_name,
                        icon='🛒',
                        commission_percent=14.0,
                        is_active=True
                    )
                    db.session.add(rule)
                else:
                    rule.is_active = True
            db.session.commit()

        return cls.get_all_rules()

    @classmethod
    def get_rule_by_channel(cls, channel_name: str) -> MarketplaceRule | None:
        """Busca uma regra por canal ou nome de exibição."""
        cls.ensure_default_rules()
        rule = MarketplaceRule.query.filter_by(channel=channel_name).first()
        if not rule:
            rule = MarketplaceRule.query.filter(
                (MarketplaceRule.channel.ilike(f"%{channel_name}%")) |
                (MarketplaceRule.channel_display_name.ilike(f"%{channel_name}%"))
            ).first()
        return rule


    @classmethod
    def calculate_price_for_cost(
        cls,
        cost: float,
        commission_percent: float,
        tax_percent: float,
        operational_percent: float,
        target_margin_percent: float,
        fixed_fee: float = 0.0,
        fixed_fee_threshold: float = 0.0,
        free_shipping_threshold: float = 999999.0,
        shipping_cost: float = 0.0
    ) -> dict:
        """
        Calcula o preço de venda ideal pelo método do Markup Reverso.
        Lida perfeitamente com a transição de faixa de frete e taxa fixa (ex: R$ 79 no ML).
        """
        cost = max(0.01, float(cost or 0.01))
        perc_sum = (
            float(commission_percent or 0.0) +
            float(tax_percent or 0.0) +
            float(operational_percent or 0.0) +
            float(target_margin_percent or 0.0)
        )

        # Evita divisão por zero ou markup negativo se a soma de porcentagens for >= 100%
        if perc_sum >= 95.0:
            perc_sum = 94.0

        divisor = 1.0 - (perc_sum / 100.0)

        # Cenário 1: Abaixo do limiar de frete grátis (com taxa fixa e sem frete seller)
        price_below = (cost + fixed_fee) / divisor

        # Cenário 2: Acima do limiar de frete grátis (com frete seller obrigatório e sem taxa fixa)
        price_above = (cost + shipping_cost) / divisor

        # Decisão de faixa
        if price_below < fixed_fee_threshold:
            suggested_price = round(price_below, 2)
            applied_fixed_fee = fixed_fee
            applied_shipping = 0.0
        elif price_above >= free_shipping_threshold:
            suggested_price = round(price_above, 2)
            applied_fixed_fee = 0.0
            applied_shipping = shipping_cost
        else:
            # Zona cinzenta entre o limiar: o lojista prefere colocar logo acima do limiar
            # ou no preço com frete para não ter margem comprimida
            suggested_price = round(max(price_above, free_shipping_threshold), 2)
            applied_fixed_fee = 0.0
            applied_shipping = shipping_cost

        # DRE Unitário detalhado
        comm_rs = round(suggested_price * (commission_percent / 100.0), 2)
        tax_rs = round(suggested_price * (tax_percent / 100.0), 2)
        op_rs = round(suggested_price * (operational_percent / 100.0), 2)
        net_profit_rs = round(
            suggested_price - cost - comm_rs - tax_rs - op_rs - applied_fixed_fee - applied_shipping,
            2
        )
        real_margin_pct = round((net_profit_rs / suggested_price * 100.0), 2) if suggested_price > 0 else 0.0
        markup_multiplier = round(suggested_price / cost, 2) if cost > 0 else 0.0

        return {
            'cost': cost,
            'suggested_price': suggested_price,
            'commission_percent': commission_percent,
            'commission_rs': comm_rs,
            'tax_percent': tax_percent,
            'tax_rs': tax_rs,
            'operational_percent': operational_percent,
            'operational_rs': op_rs,
            'fixed_fee_rs': applied_fixed_fee,
            'shipping_rs': applied_shipping,
            'net_profit_rs': net_profit_rs,
            'margin_percent': real_margin_pct,
            'target_margin_percent': target_margin_percent,
            'markup_multiplier': markup_multiplier
        }

    @classmethod
    def calculate_product_channel_pricing(
        cls,
        product: Product,
        rule: MarketplaceRule,
        custom_target_margin: float | None = None
    ) -> dict:
        """Calcula o preço sugerido de um produto específico para uma regra de marketplace."""
        # Prioriza o custo de aquisição / valor pago; se zerado, usa o custo base do produto
        cost = float(product.purchase_cost if product.purchase_cost and product.purchase_cost > 0 else (product.cost or 0.0))
        if cost <= 0:
            cost = float(product.price or 10.0) * 0.5 # estimativa se ambos estiverem zerados

        margin = custom_target_margin if custom_target_margin is not None else rule.target_margin_percent

        calc = cls.calculate_price_for_cost(
            cost=cost,
            commission_percent=rule.commission_percent,
            tax_percent=rule.tax_percent,
            operational_percent=rule.operational_cost_percent,
            target_margin_percent=margin,
            fixed_fee=rule.fixed_fee,
            fixed_fee_threshold=rule.fixed_fee_threshold,
            free_shipping_threshold=rule.free_shipping_threshold,
            shipping_cost=rule.default_shipping_cost
        )

        calc['product_id'] = product.id
        calc['product_name'] = product.name
        calc['sku'] = product.sku or ''
        calc['stock'] = float(product.stock or 0.0)
        calc['category'] = product.category or 'Geral'
        calc['size'] = product.size or ''
        calc['color'] = product.color or ''
        calc['base_price'] = float(product.price or 0.0)
        calc['channel'] = rule.channel
        calc['channel_display_name'] = rule.channel_display_name or rule.channel
        calc['channel_icon'] = rule.icon

        # Preço atual praticado no canal se existir
        current_cp = ProductChannelPrice.query.filter_by(
            product_id=product.id,
            channel=rule.channel
        ).first()
        calc['current_channel_price'] = float(current_cp.price) if current_cp else None
        calc['sync_status'] = current_cp.sync_status if current_cp else None
        calc['last_sync_at'] = current_cp.last_sync_at.strftime('%d/%m/%Y %H:%M') if current_cp and current_cp.last_sync_at else None
        calc['has_bling_link'] = bool(rule.bling_loja_id and product.bling_id)

        return calc

    @classmethod
    def sync_channel_prices_from_bling(cls, rule: MarketplaceRule, max_items: int = 500) -> int:
        """
        Consulta os preços e vínculos de produtos já cadastrados no canal no Bling (/produtos/lojas)
        e sincroniza com a tabela local ProductChannelPrice.
        Retorna a quantidade de produtos cujos preços de canal foram sincronizados.
        """
        if not rule or not rule.bling_loja_id:
            return 0

        try:
            from app.services.bling_api import BlingApiClient
            client = BlingApiClient()
            if not client.is_configured():
                return 0

            store_items = client.get_store_products(rule.bling_loja_id, max_items=max_items)
            if not store_items:
                return 0

            # 1. Pré-carrega todos os produtos em lote pelos seus IDs do Bling
            bling_prod_ids = [
                item.get('produto', {}).get('id')
                for item in store_items
                if item.get('produto', {}).get('id')
            ]
            if not bling_prod_ids:
                return 0

            products = Product.query.filter(Product.bling_id.in_(bling_prod_ids)).all()
            prod_by_bling_id = {p.bling_id: p for p in products if p.bling_id}

            # 2. Pré-carrega registros existentes de ProductChannelPrice para este canal
            prod_ids = [p.id for p in products]
            existing_cps = ProductChannelPrice.query.filter(
                ProductChannelPrice.channel == rule.channel,
                ProductChannelPrice.product_id.in_(prod_ids)
            ).all() if prod_ids else []
            cp_by_prod_id = {cp.product_id: cp for cp in existing_cps}

            synced_count = 0
            for item in store_items:
                bling_prod_id = item.get('produto', {}).get('id')
                if not bling_prod_id or bling_prod_id not in prod_by_bling_id:
                    continue

                prod = prod_by_bling_id[bling_prod_id]
                preco_loja = float(item.get('preco', 0.0) or 0.0)
                produto_loja_id = item.get('id')

                cp = cp_by_prod_id.get(prod.id)
                cost = float(prod.purchase_cost if prod.purchase_cost and prod.purchase_cost > 0 else (prod.cost or 0.0))
                markup = ((preco_loja - cost) / cost * 100.0) if cost > 0 and preco_loja > 0 else 0.0

                if not cp:
                    cp = ProductChannelPrice(
                        product_id=prod.id,
                        channel=rule.channel,
                        price=round(preco_loja, 2),
                        markup=round(markup, 2),
                        margin_percent=0.0,
                        bling_produto_loja_id=produto_loja_id,
                        bling_loja_id=rule.bling_loja_id,
                        sync_status='synced',
                        last_sync_at=datetime.utcnow(),
                        is_active=True
                    )
                    db.session.add(cp)
                    cp_by_prod_id[prod.id] = cp
                else:
                    cp.price = round(preco_loja, 2)
                    cp.markup = round(markup, 2)
                    cp.bling_produto_loja_id = produto_loja_id
                    cp.bling_loja_id = rule.bling_loja_id
                    cp.sync_status = 'synced'
                    cp.last_sync_at = datetime.utcnow()

                synced_count += 1

            db.session.commit()
            logger.info(f"[PricingEngine] {synced_count} preço(s) de produto sincronizado(s) do Bling para o canal '{rule.channel}'.")
            return synced_count
        except Exception as e:
            logger.error(f"[PricingEngine] Erro ao sincronizar preços do canal {rule.channel} do Bling: {e}")
            db.session.rollback()
            return 0

    @classmethod
    def apply_channel_price(cls, product_id: int, channel: str, new_price: float, margin_pct: float = 0.0) -> bool:
        """
        Aplica e persiste o preço de venda para um produto em um determinado canal,
        refletindo a atualização no ERP Bling em tempo real caso o canal esteja conectado.
        """
        try:
            rule = cls.get_rule_by_channel(channel)
            cp = ProductChannelPrice.query.filter_by(product_id=product_id, channel=channel).first()
            prod = Product.query.get(product_id)
            if not prod:
                return False

            cost = float(prod.purchase_cost if prod.purchase_cost and prod.purchase_cost > 0 else (prod.cost or 0.0))
            markup = ((new_price - cost) / cost * 100.0) if cost > 0 else 0.0

            if not cp:
                cp = ProductChannelPrice(
                    product_id=product_id,
                    channel=channel,
                    price=round(new_price, 2),
                    markup=round(markup, 2),
                    margin_percent=round(margin_pct, 2),
                    bling_loja_id=rule.bling_loja_id if rule else None,
                    sync_status='pending',
                    is_active=True
                )
                db.session.add(cp)
            else:
                cp.price = round(new_price, 2)
                cp.markup = round(markup, 2)
                cp.margin_percent = round(margin_pct, 2)
                if rule and rule.bling_loja_id:
                    cp.bling_loja_id = rule.bling_loja_id
                cp.updated_at = datetime.utcnow()

            db.session.flush()

            # Envia atualização para o Bling se o canal tiver vínculo ativo
            if rule and rule.bling_loja_id and prod.bling_id:
                try:
                    from app.services.bling_api import BlingApiClient
                    client = BlingApiClient()
                    if client.is_configured():
                        success, b_msg, b_data = client.update_product_store_price(
                            bling_product_id=prod.bling_id,
                            loja_id=rule.bling_loja_id,
                            price=new_price,
                            produto_loja_id=cp.bling_produto_loja_id
                        )
                        if success:
                            if b_data and b_data.get('id'):
                                cp.bling_produto_loja_id = b_data['id']
                            cp.sync_status = 'synced'
                            cp.last_sync_at = datetime.utcnow()
                        else:
                            cp.sync_status = 'error'
                            logger.warning(f"[PricingEngine] Aviso ao sincronizar com Bling: {b_msg}")
                except Exception as be:
                    logger.warning(f"[PricingEngine] Erro ao sincronizar preço no Bling: {be}")
                    cp.sync_status = 'error'

            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"[PricingEngine] Erro ao aplicar preço no canal: {e}")
            db.session.rollback()
            return False

    @classmethod
    def apply_prices_in_batch(cls, product_ids: list[int], channel: str, custom_target_margin: float | None = None) -> dict:
        """Aplica precificação automática em lote para uma lista de produtos em determinado canal e sincroniza com o Bling."""
        rule = cls.get_rule_by_channel(channel)
        if not rule:
            return {'success': False, 'message': f"Regra do canal '{channel}' não encontrada."}

        applied_count = 0
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        for prod in products:
            calc = cls.calculate_product_channel_pricing(prod, rule, custom_target_margin)
            success = cls.apply_channel_price(
                product_id=prod.id,
                channel=rule.channel,
                new_price=calc['suggested_price'],
                margin_pct=calc['margin_percent']
            )
            if success:
                applied_count += 1

        msg = f"Precificação aplicada com sucesso para {applied_count} produto(s) no canal {rule.base_marketplace_name}!"
        if rule.bling_loja_id:
            msg += " Os preços foram sincronizados e refletidos no Bling."

        return {
            'success': True,
            'applied_count': applied_count,
            'channel': rule.channel,
            'message': msg
        }

