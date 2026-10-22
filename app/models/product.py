from datetime import datetime
from app.database import db

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    bling_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    sku = db.Column(db.String(100), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    price = db.Column(db.Float, default=0.0)
    cost = db.Column(db.Float, default=0.0)
    purchase_cost = db.Column(db.Float, default=0.0) # Valor pago na aquisição / compra
    stock = db.Column(db.Float, default=0.0)
    min_stock = db.Column(db.Float, default=5.0) # Estoque mínimo de segurança
    lead_time_days = db.Column(db.Integer, default=7) # Prazo de reposição em dias
    weight_kg = db.Column(db.Float, default=0.3) # Peso estimado para cálculo de frete
    category = db.Column(db.String(100), nullable=True, index=True)
    size = db.Column(db.String(20), nullable=True, index=True)
    color = db.Column(db.String(50), nullable=True, index=True)
    style = db.Column(db.String(50), nullable=True, index=True)
    format = db.Column(db.String(50), nullable=True) # S (Simples), C (Composição), etc.
    status = db.Column(db.String(20), default='A') # A (Ativo), I (Inativo)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamento com itens de pedido e preços por canal
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    channel_prices = db.relationship('ProductChannelPrice', backref='product', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'bling_id': self.bling_id,
            'sku': self.sku or '',
            'name': self.name,
            'price': self.price,
            'cost': self.cost,
            'purchase_cost': self.purchase_cost,
            'stock': self.stock,
            'min_stock': self.min_stock,
            'category': self.category or 'Geral',
            'size': self.size or '',
            'color': self.color or '',
            'style': self.style or '',
            'status': self.status,
            'channel_prices': {cp.channel: cp.price for cp in self.channel_prices} if self.channel_prices else {}
        }


class ProductChannelPrice(db.Model):
    """
    Armazena o preço específico de venda praticado para cada produto em cada canal/marketplace.
    Ex: 'Mercado Livre', 'Shopee', 'Amazon', 'Site Próprio', 'Loja Física', etc.
    """
    __tablename__ = 'product_channel_prices'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    channel = db.Column(db.String(100), nullable=False, index=True)
    price = db.Column(db.Float, default=0.0)
    markup = db.Column(db.Float, default=0.0) # Markup % em relação ao custo
    margin_percent = db.Column(db.Float, default=0.0) # Margem líquida estimada
    is_active = db.Column(db.Boolean, default=True)
    
    # Rastreabilidade com a API v3 do Bling (/produtos/lojas)
    bling_produto_loja_id = db.Column(db.BigInteger, nullable=True, index=True) # ID único do vínculo do produto na loja (ex: 920233394)
    bling_loja_id = db.Column(db.BigInteger, nullable=True) # ID da loja no Bling (ex: 205523454)
    sync_status = db.Column(db.String(30), default='synced') # 'synced', 'pending', 'error'
    last_sync_at = db.Column(db.DateTime, nullable=True) # Data da última atualização refletida no Bling

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'channel': self.channel,
            'price': self.price,
            'markup': self.markup,
            'margin_percent': self.margin_percent,
            'is_active': self.is_active,
            'bling_produto_loja_id': self.bling_produto_loja_id,
            'bling_loja_id': self.bling_loja_id,
            'sync_status': self.sync_status,
            'last_sync_at': self.last_sync_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_sync_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

