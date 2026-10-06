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
    notes = db.Text

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
            'customer_name': self.customer.name if self.customer else 'Consumidor Final',
            'items_count': len(self.items) if self.items else 0
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    product_name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), nullable=True)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    cost_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
