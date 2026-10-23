from datetime import datetime, date
from sqlalchemy.orm import synonym
from app.database import db

class FinancialEntry(db.Model):
    __tablename__ = 'financial_entries'

    id = db.Column(db.Integer, primary_key=True)
    bling_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    entry_type = db.Column(db.String(10), nullable=False, index=True) # RECEBER ou PAGAR
    description = db.Column(db.String(255), nullable=False)
    entity_name = db.Column(db.String(255), nullable=True) # Nome do cliente ou fornecedor
    payee_payer = synonym('entity_name')
    category = db.Column(db.String(100), default='Operacional', index=True)
    amount = db.Column(db.Float, default=0.0)
    issue_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    due_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    payment_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(20), default='Pendente', index=True) # Pendente, Pago, Atrasado, Cancelado
    payment_method = db.Column(db.String(100), nullable=True) # Boleto, Pix, Cartão, Transferência, Dinheiro
    notes = db.Column(db.Text, nullable=True)
    discount = db.Column(db.Float, default=0.0)
    fine_fee = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __getitem__(self, item):
        return getattr(self, item)

    def get(self, item, default=None):
        return getattr(self, item, default)

    @property
    def is_overdue(self) -> bool:
        if self.status in ('Pendente', 'Atrasado') and self.due_date:
            return self.due_date < date.today()
        return False

    @property
    def days_until_due(self) -> int:
        if self.due_date:
            return (self.due_date - date.today()).days
        return 0

    @property
    def net_amount(self) -> float:
        return max(0.0, (self.amount or 0.0) - (self.discount or 0.0) + (self.fine_fee or 0.0))

    @property
    def due_date_formatted(self) -> str:
        return self.due_date.strftime('%d/%m/%Y') if self.due_date else ''

    @property
    def issue_date_formatted(self) -> str:
        return self.issue_date.strftime('%d/%m/%Y') if self.issue_date else ''

    @property
    def payment_date_formatted(self) -> str:
        return self.payment_date.strftime('%d/%m/%Y') if self.payment_date else ''

    def to_dict(self):
        return {
            'id': self.id,
            'bling_id': self.bling_id,
            'entry_type': self.entry_type,
            'description': self.description,
            'entity_name': self.entity_name or 'N/A',
            'payee_payer': self.entity_name or 'N/A',
            'category': self.category,
            'amount': self.amount,
            'net_amount': self.net_amount,
            'issue_date': self.issue_date.strftime('%Y-%m-%d') if self.issue_date else None,
            'issue_date_formatted': self.issue_date_formatted,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'due_date_formatted': self.due_date_formatted,
            'payment_date': self.payment_date.strftime('%Y-%m-%d') if self.payment_date else None,
            'payment_date_formatted': self.payment_date_formatted,
            'status': self.status,
            'payment_method': self.payment_method or 'Outro',
            'notes': self.notes or '',
            'discount': self.discount or 0.0,
            'fine_fee': self.fine_fee or 0.0,
            'is_overdue': self.is_overdue,
            'days_until_due': self.days_until_due
        }

