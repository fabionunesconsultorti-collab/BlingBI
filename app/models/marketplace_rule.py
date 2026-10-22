from datetime import datetime
from app.database import db

class MarketplaceRule(db.Model):
    """
    Regras de comissão, taxas fixas, frete e margem para precificação automática por marketplace/canal.
    """
    __tablename__ = 'marketplace_rules'

    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(100), unique=True, nullable=False, index=True)
    channel_display_name = db.Column(db.String(150), nullable=True)
    icon = db.Column(db.String(20), default='🛒')
    
    # Parâmetros de custos da venda
    commission_percent = db.Column(db.Float, default=14.0) # % comissão cobrada pelo canal
    fixed_fee = db.Column(db.Float, default=0.0) # R$ taxa fixa para itens abaixo do threshold (ex: R$ 6.50 no ML)
    fixed_fee_threshold = db.Column(db.Float, default=79.0) # Limiar de preço para taxa fixa (ex: < 79.00 no ML)
    free_shipping_threshold = db.Column(db.Float, default=79.0) # Limiar para frete grátis obrigatório
    default_shipping_cost = db.Column(db.Float, default=22.0) # R$ custo médio de frete grátis assumido pelo seller
    
    # Parâmetros fiscais e operacionais do lojista
    tax_percent = db.Column(db.Float, default=6.0) # % imposto DAS Simples Nacional
    operational_cost_percent = db.Column(db.Float, default=3.0) # % despesas operacionais / embalagem / perdas
    target_margin_percent = db.Column(db.Float, default=20.0) # % margem de lucro líquida desejada
    
    is_active = db.Column(db.Boolean, default=True)
    bling_loja_id = db.Column(db.BigInteger, nullable=True, index=True) # ID da loja/canal retornado pelo Bling (/canais-venda)
    bling_tipo = db.Column(db.String(50), nullable=True) # Tipo do canal no Bling (ex: 'ViaVarejo', 'MadeiraMadeira', 'IntegraCommerce', etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def base_marketplace_name(self):
        """Retorna o nome comercial limpo do marketplace/canal."""
        ch = (self.channel or '') + ' ' + (self.channel_display_name or '')
        ch_lower = ch.lower()
        if 'via varejo' in ch_lower or 'viavarejo' in ch_lower or 'casas bahia' in ch_lower:
            return 'Via Varejo'
        if 'madeira madeira' in ch_lower or 'madeiramadeira' in ch_lower:
            return 'Madeira Madeira'
        if 'mercado livre' in ch_lower or 'mercadolivre' in ch_lower:
            return 'Mercado Livre'
        if 'shopee' in ch_lower:
            return 'Shopee'
        if 'amazon' in ch_lower:
            return 'Amazon Brasil'
        if 'magalu' in ch_lower or 'magazine luiza' in ch_lower or 'integracommerce' in ch_lower:
            return 'Magazine Luiza'
        if 'shein' in ch_lower:
            return 'Shein'
        if 'tiktok' in ch_lower:
            return 'TikTok Shop'
        if 'nuvemshop' in ch_lower:
            return 'Nuvemshop'
        if 'tray' in ch_lower:
            return 'Site Próprio (Tray)'
        if 'loja integrada' in ch_lower:
            return 'Loja Integrada'
        if 'shopify' in ch_lower:
            return 'Shopify'
        if 'site' in ch_lower or 'e-commerce' in ch_lower or 'virtual' in ch_lower:
            return 'Loja Virtual'
        if 'loja física' in ch_lower or 'loja fisica' in ch_lower or 'balcão' in ch_lower:
            return 'Loja Física'
        if 'whatsapp' in ch_lower:
            return 'WhatsApp VIP'
        if 'instagram' in ch_lower:
            return 'Instagram Direct'
        return self.channel_display_name or self.channel

    @property
    def short_rule_explanation(self):
        """Retorna breve explicação da regra/anúncio para a segunda linha do botão."""
        ch = (self.channel or '') + ' ' + (self.channel_display_name or '')
        ch_lower = ch.lower()
        if 'via varejo' in ch_lower or 'viavarejo' in ch_lower or 'casas bahia' in ch_lower:
            return 'Casas Bahia Marketplace'
        if 'madeira madeira' in ch_lower or 'madeiramadeira' in ch_lower:
            return 'Móveis & Decoração'
        if 'clássico' in ch_lower or 'classico' in ch_lower:
            return 'Anúncio Clássico'
        if 'premium' in ch_lower:
            return 'Anúncio Premium 12x'
        if 'padrão' in ch_lower or 'padrao' in ch_lower:
            return f'Comissão Padrão {self.commission_percent:.0f}%'
        if 'frete grátis' in ch_lower or 'frete gratis' in ch_lower:
            return 'Frete Grátis Extra'
        if 'amazon' in ch_lower:
            return f'Tarifa Padrão ({self.commission_percent:.0f}%)'
        if 'magalu' in ch_lower or 'magazine luiza' in ch_lower or 'integracommerce' in ch_lower:
            return 'Magalu Marketplace'
        if 'shein' in ch_lower:
            return 'Shein Marketplace'
        if 'tiktok' in ch_lower:
            return 'TikTok Marketplace'
        if 'tray' in ch_lower:
            return 'Plataforma Tray E-commerce'
        if any(w in ch_lower for w in ['site', 'e-commerce', 'virtual', 'nuvemshop', 'loja integrada', 'shopify']):
            return 'Checkout & Gateway'
        if any(w in ch_lower for w in ['física', 'fisica', 'balcão', 'balcao']):
            return 'Venda Balcão / VIP'
        if 'whatsapp' in ch_lower or 'instagram' in ch_lower:
            return 'Venda Direta Social'
        return f'Taxa {self.commission_percent:.0f}%'

    @property
    def logo_key(self):
        """Retorna identificador padronizado para renderização do SVG do logotipo."""
        ch = ((self.channel or '') + ' ' + (self.channel_display_name or '') + ' ' + (self.bling_tipo or '')).lower()
        if 'via varejo' in ch or 'viavarejo' in ch or 'casas bahia' in ch:
            return 'viavarejo'
        if 'madeira madeira' in ch or 'madeiramadeira' in ch:
            return 'madeiramadeira'
        if 'mercado livre' in ch or 'mercadolivre' in ch:
            return 'mercadolivre'
        if 'shopee' in ch:
            return 'shopee'
        if 'amazon' in ch:
            return 'amazon'
        if 'magalu' in ch or 'magazine luiza' in ch or 'integracommerce' in ch:
            return 'magalu'
        if 'shein' in ch:
            return 'shein'
        if 'tiktok' in ch:
            return 'tiktok'
        if 'nuvemshop' in ch:
            return 'nuvemshop'
        if 'tray' in ch or 'shopify' in ch or 'loja integrada' in ch or 'site' in ch or 'e-commerce' in ch or 'virtual' in ch:
            return 'loja_virtual'
        if 'whatsapp' in ch:
            return 'whatsapp'
        if 'instagram' in ch:
            return 'instagram'
        if 'física' in ch or 'fisica' in ch or 'balcão' in ch:
            return 'loja_fisica'
        return 'generic'

    def to_dict(self):
        return {
            'id': self.id,
            'channel': self.channel,
            'channel_display_name': self.channel_display_name or self.channel,
            'base_marketplace_name': self.base_marketplace_name,
            'short_rule_explanation': self.short_rule_explanation,
            'logo_key': self.logo_key,
            'icon': self.icon,
            'bling_loja_id': self.bling_loja_id,
            'bling_tipo': self.bling_tipo,
            'commission_percent': self.commission_percent,
            'fixed_fee': self.fixed_fee,
            'fixed_fee_threshold': self.fixed_fee_threshold,
            'free_shipping_threshold': self.free_shipping_threshold,
            'default_shipping_cost': self.default_shipping_cost,
            'tax_percent': self.tax_percent,
            'operational_cost_percent': self.operational_cost_percent,
            'target_margin_percent': self.target_margin_percent,
            'is_active': self.is_active,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

