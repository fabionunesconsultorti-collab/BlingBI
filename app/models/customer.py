from datetime import datetime
from app.database import db

class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    bling_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    document = db.Column(db.String(30), nullable=True, index=True) # CPF ou CNPJ
    person_type = db.Column(db.String(2), default='F') # F = Física, J = Jurídica
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(10), nullable=True, index=True) # UF (ex: SP, RJ)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamento com pedidos
    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'bling_id': self.bling_id,
            'name': self.name,
            'document': self.document,
            'person_type': self.person_type,
            'email': self.email,
            'phone': self.phone,
            'city': self.city,
            'state': self.state,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else None
        }
