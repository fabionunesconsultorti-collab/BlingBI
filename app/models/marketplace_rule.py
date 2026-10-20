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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'channel': self.channel,
            'channel_display_name': self.channel_display_name or self.channel,
            'icon': self.icon,
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
