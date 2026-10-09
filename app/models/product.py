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
    stock = db.Column(db.Float, default=0.0)
    category = db.Column(db.String(100), nullable=True, index=True)
    size = db.Column(db.String(20), nullable=True, index=True)
    color = db.Column(db.String(50), nullable=True, index=True)
    style = db.Column(db.String(50), nullable=True, index=True)
    format = db.Column(db.String(50), nullable=True) # S (Simples), C (Composição), etc.
    status = db.Column(db.String(20), default='A') # A (Ativo), I (Inativo)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamento com itens de pedido
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'bling_id': self.bling_id,
            'sku': self.sku or '',
            'name': self.name,
            'price': self.price,
            'cost': self.cost,
            'stock': self.stock,
            'category': self.category or 'Geral',
            'size': self.size or '',
            'color': self.color or '',
            'style': self.style or '',
            'status': self.status
        }
