from datetime import datetime
from app.database import db

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    bling_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    number = db.Column(db.String(50), nullable=False, index=True)
    order_date = db.Column(db.Date, nullable=False, index=True)
    total = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    shipping = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default='Atendido', index=True) # Atendido, Em aberto, Cancelado
    channel = db.Column(db.String(100), default='Loja Virtual', index=True) # Mercado Livre, Shopee, Site, Loja Física
    seller_name = db.Column(db.String(100), nullable=True, index=True) # Vendedor / Consultor de Vendas
    payment_method = db.Column(db.String(100), default='Cartão de Crédito', nullable=True, index=True) # Dinheiro, Cartão, Boleto, Pix, Consignado
    notes = db.Column(db.Text, nullable=True)

    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamento com itens
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'bling_id': self.bling_id,
            'number': self.number,
            'order_date': self.order_date.strftime('%Y-%m-%d') if self.order_date else None,
            'total': self.total,
            'discount': self.discount,
            'shipping': self.shipping,
            'status': self.status,
            'channel': self.channel,
            'seller_name': self.seller_name or 'Não Atribuído',
            'payment_method': self.payment_method or 'Outro',
            'customer_name': self.customer.name if self.customer else 'Consumidor Final',
            'customer_document': self.customer.document if (self.customer and self.customer.document) else '',
            'items_count': len(self.items) if self.items else 0
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    product_name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), nullable=True)
    size = db.Column(db.String(20), nullable=True, index=True)
    color = db.Column(db.String(50), nullable=True, index=True)
    style = db.Column(db.String(50), nullable=True, index=True)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    cost_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)

    def to_dict(self):
        stock_curr = float(self.product.stock or 0.0) if self.product else 0.0
        return {
            'id': self.id,
            'order_id': self.order_id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'sku': self.sku or 'N/A',
            'size': self.size or '',
            'color': self.color or '',
            'style': self.style or '',
            'quantity': float(self.quantity or 1.0),
            'unit_price': float(self.unit_price or 0.0),
            'cost_price': float(self.cost_price or 0.0),
            'total_price': float(self.total_price or 0.0),
            'stock': stock_curr
        }
