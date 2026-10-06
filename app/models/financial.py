from datetime import datetime
from app.database import db

class FinancialEntry(db.Model):
    __tablename__ = 'financial_entries'

    id = db.Column(db.Integer, primary_key=True)
    bling_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    entry_type = db.Column(db.String(10), nullable=False, index=True) # RECEBER ou PAGAR
    description = db.Column(db.String(255), nullable=False)
    entity_name = db.Column(db.String(255), nullable=True) # Nome do cliente ou fornecedor
    category = db.Column(db.String(100), default='Operacional', index=True)
    amount = db.Column(db.Float, default=0.0)
    issue_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=False, index=True)
    payment_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(20), default='Pendente', index=True) # Pendente, Pago, Atrasado, Cancelado
    payment_method = db.Column(db.String(100), nullable=True) # Boleto, Pix, Cartão, Transferência
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'bling_id': self.bling_id,
            'entry_type': self.entry_type,
            'description': self.description,
            'entity_name': self.entity_name or 'N/A',
            'category': self.category,
            'amount': self.amount,
            'issue_date': self.issue_date.strftime('%Y-%m-%d') if self.issue_date else None,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'payment_date': self.payment_date.strftime('%Y-%m-%d') if self.payment_date else None,
            'status': self.status,
            'payment_method': self.payment_method or 'Outro'
        }
