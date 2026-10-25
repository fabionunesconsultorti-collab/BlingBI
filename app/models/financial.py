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
    competence_date = db.Column(db.Date, nullable=True, default=date.today, index=True)
    status = db.Column(db.String(20), default='Pendente', index=True) # Pendente, Pago, Atrasado, Cancelado
    payment_method = db.Column(db.String(100), nullable=True) # Boleto, Pix, Cartão, Transferência, Dinheiro
    notes = db.Column(db.Text, nullable=True)
    discount = db.Column(db.Float, default=0.0)
    fine_fee = db.Column(db.Float, default=0.0)
    
    # Campos de vínculo e espelhamento oficial com a API v3 do Bling
    bling_contact_id = db.Column(db.BigInteger, nullable=True, index=True)
    bling_category_id = db.Column(db.BigInteger, nullable=True)
    bling_payment_method_id = db.Column(db.BigInteger, nullable=True)
    bling_bordero_id = db.Column(db.BigInteger, nullable=True, index=True) # ID da baixa / borderô no Bling
    sync_status = db.Column(db.String(30), default='synced', index=True) # synced, pending_sync, sync_error, local_only
    last_sync_at = db.Column(db.DateTime, nullable=True)
    sync_error_msg = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def has_real_bling_id(self) -> bool:
        """Retorna True se o lançamento possui ID oficial registrado no Bling ERP."""
        if not self.bling_id:
            return False
        return 0 < self.bling_id < 1_000_000_000_000

    @classmethod
    def is_real_bling_id(cls, bling_id: int | None) -> bool:
        """Verifica se um dado bling_id é um ID numérico oficial do Bling."""
        if not bling_id:
            return False
        try:
            val = int(bling_id)
            return 0 < val < 1_000_000_000_000
        except (ValueError, TypeError):
            return False

    @classmethod
    def is_synthetic(cls, bling_id: int | None) -> bool:
        """Retorna True se o ID for sintético/temporário gerado localmente."""
        return not cls.is_real_bling_id(bling_id)

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

    @property
    def competence_date_formatted(self) -> str:
        if self.competence_date:
            return self.competence_date.strftime('%d/%m/%Y')
        if self.issue_date:
            return self.issue_date.strftime('%d/%m/%Y')
        return self.due_date.strftime('%d/%m/%Y') if self.due_date else ''

    @property
    def last_sync_at_formatted(self) -> str:
        return self.last_sync_at.strftime('%d/%m/%Y %H:%M') if self.last_sync_at else ''

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
            'competence_date': self.competence_date.strftime('%Y-%m-%d') if self.competence_date else (self.issue_date.strftime('%Y-%m-%d') if self.issue_date else None),
            'competence_date_formatted': self.competence_date_formatted,
            'payment_date': self.payment_date.strftime('%Y-%m-%d') if self.payment_date else None,
            'payment_date_formatted': self.payment_date_formatted,
            'status': self.status,
            'payment_method': self.payment_method or 'Outro',
            'notes': self.notes or '',
            'discount': self.discount or 0.0,
            'fine_fee': self.fine_fee or 0.0,
            'bling_contact_id': self.bling_contact_id,
            'bling_category_id': self.bling_category_id,
            'bling_payment_method_id': self.bling_payment_method_id,
            'bling_bordero_id': self.bling_bordero_id,
            'has_real_bling_id': self.has_real_bling_id,
            'sync_status': self.sync_status or 'synced',
            'last_sync_at': self.last_sync_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_sync_at else None,
            'last_sync_at_formatted': self.last_sync_at_formatted,
            'sync_error_msg': self.sync_error_msg or '',
            'is_overdue': self.is_overdue,
            'days_until_due': self.days_until_due
        }


