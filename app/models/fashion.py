from datetime import datetime, date
from app.database import db

class ConditionalBag(db.Model):
    """
    Modelo de Bag / Mala Condicional (Consignação de Varejo de Moda).
    Rastreia peças retiradas pelo cliente para provar em casa vs peças faturadas.
    """
    __tablename__ = 'conditional_bags'

    id = db.Column(db.Integer, primary_key=True)
    bag_code = db.Column(db.String(50), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)
    customer_name = db.Column(db.String(255), nullable=False)
    seller_name = db.Column(db.String(100), nullable=False, default='Consultora de Vendas')
    items_sent = db.Column(db.Integer, default=0) # Peças enviadas / retiradas
    items_invoiced = db.Column(db.Integer, default=0) # Peças compradas / faturadas
    items_returned = db.Column(db.Integer, default=0) # Peças devolvidas
    total_sent_value = db.Column(db.Float, default=0.0)
    total_invoiced_value = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default='Finalizada', index=True) # Em Aberto, Finalizada, Cancelada
    sent_date = db.Column(db.Date, nullable=False, index=True)
    return_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento
    customer = db.relationship('Customer', backref=db.backref('conditional_bags', lazy='dynamic'))

    @property
    def conversion_rate(self):
        if self.items_sent and self.items_sent > 0:
            return round((self.items_invoiced / self.items_sent) * 100, 1)
        return 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'bag_code': self.bag_code,
            'customer_name': self.customer_name,
            'seller_name': self.seller_name,
            'items_sent': self.items_sent,
            'items_invoiced': self.items_invoiced,
            'items_returned': self.items_returned,
            'total_sent_value': self.total_sent_value,
            'total_invoiced_value': self.total_invoiced_value,
            'conversion_rate': self.conversion_rate,
            'status': self.status,
            'sent_date': self.sent_date.strftime('%Y-%m-%d') if self.sent_date else None,
            'return_date': self.return_date.strftime('%Y-%m-%d') if self.return_date else None
        }


class ProductReturn(db.Model):
    """
    Modelo de Trocas e Devoluções no Varejo de Moda.
    Rastreia SKU, motivo (modelagem, tamanho, defeito) e quantidade devolvida.
    """
    __tablename__ = 'product_returns'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    sku = db.Column(db.String(100), nullable=True, index=True)
    product_name = db.Column(db.String(255), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)
    customer_name = db.Column(db.String(255), nullable=False)
    seller_name = db.Column(db.String(100), nullable=True)
    quantity = db.Column(db.Float, default=1.0)
    reason = db.Column(db.String(100), nullable=False, index=True) # Motivo: Tamanho não serviu, Modelagem pequena, etc.
    return_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    customer = db.relationship('Customer', backref=db.backref('returns', lazy='dynamic'))
    product = db.relationship('Product', backref=db.backref('returns', lazy='dynamic'))
    order = db.relationship('Order', backref=db.backref('returns', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'product_name': self.product_name,
            'customer_name': self.customer_name,
            'seller_name': self.seller_name,
            'quantity': self.quantity,
            'reason': self.reason,
            'return_date': self.return_date.strftime('%Y-%m-%d') if self.return_date else None
        }


class SellerAttendance(db.Model):
    """
    Modelo de Atendimento e Prospecção (Leads de Loja / WhatsApp / Instagram).
    Permite calcular a Taxa de Conversão por Vendedor (Atendimentos vs Vendas).
    """
    __tablename__ = 'seller_attendances'

    id = db.Column(db.Integer, primary_key=True)
    seller_name = db.Column(db.String(100), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)
    customer_name = db.Column(db.String(255), nullable=False)
    channel = db.Column(db.String(50), default='Loja Física', index=True)
    converted = db.Column(db.Boolean, default=False, index=True) # Venda fechada?
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    customer = db.relationship('Customer', backref=db.backref('attendances', lazy='dynamic'))
    order = db.relationship('Order', backref=db.backref('attendance_ref', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'seller_name': self.seller_name,
            'customer_name': self.customer_name,
            'channel': self.channel,
            'converted': self.converted,
            'attendance_date': self.attendance_date.strftime('%Y-%m-%d') if self.attendance_date else None,
            'notes': self.notes
        }


class CustomerSurvey(db.Model):
    """
    Modelo de Pesquisas de Satisfação do Cliente (NPS e CSAT pós-venda).
    """
    __tablename__ = 'customer_surveys'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, index=True)
    customer_name = db.Column(db.String(255), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True, index=True)
    seller_name = db.Column(db.String(100), nullable=True)
    nps_score = db.Column(db.Integer, nullable=False) # 0 a 10
    csat_score = db.Column(db.Integer, nullable=False) # 1 a 5
    feedback = db.Column(db.Text, nullable=True)
    survey_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    customer = db.relationship('Customer', backref=db.backref('surveys', lazy='dynamic'))
    order = db.relationship('Order', backref=db.backref('surveys', lazy='dynamic'))

    @property
    def nps_category(self):
        if self.nps_score >= 9:
            return 'Promotor'
        elif self.nps_score >= 7:
            return 'Neutro'
        return 'Detrator'

    def to_dict(self):
        return {
            'id': self.id,
            'customer_name': self.customer_name,
            'seller_name': self.seller_name,
            'nps_score': self.nps_score,
            'csat_score': self.csat_score,
            'nps_category': self.nps_category,
            'feedback': self.feedback,
            'survey_date': self.survey_date.strftime('%Y-%m-%d') if self.survey_date else None
        }
