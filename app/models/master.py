import secrets
from datetime import datetime, timedelta
import json
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import db

class MasterSegment(db.Model):
    """
    Segmentos de atuação das empresas (ex: Moda, Movelaria, Restaurante, etc.).
    Define o catálogo de telas, abas e relatórios disponíveis para os clientes do segmento.
    """
    __tablename__ = 'master_segments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    icon = db.Column(db.String(50), default='📊')
    description = db.Column(db.Text, nullable=True)
    
    # Listas em JSON com identificadores de recursos liberados
    # allowed_screens: ['dashboard', 'sales', 'products', 'customers', 'finance', 'fashion', 'reports', 'integrations']
    allowed_screens_json = db.Column(db.Text, default='[]')
    
    # allowed_tabs: chaves de FEATURES_CATALOG (ex: 'sales.overview', 'fashion.block1', ...)
    allowed_tabs_json = db.Column(db.Text, default='[]')
    
    # allowed_reports: IDs dos módulos de relatórios (ex: 'dre', 'cash_flow', 'rfm', 'fashion_bi', ...)
    allowed_reports_json = db.Column(db.Text, default='[]')
    
    is_system_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('MasterUser', backref='segment', lazy='dynamic')

    @property
    def allowed_screens(self):
        try:
            return json.loads(self.allowed_screens_json or '[]')
        except Exception:
            return []

    @allowed_screens.setter
    def allowed_screens(self, val):
        self.allowed_screens_json = json.dumps(val or [])

    @property
    def allowed_tabs(self):
        try:
            return json.loads(self.allowed_tabs_json or '[]')
        except Exception:
            return []

    @allowed_tabs.setter
    def allowed_tabs(self, val):
        self.allowed_tabs_json = json.dumps(val or [])

    @property
    def allowed_reports(self):
        try:
            return json.loads(self.allowed_reports_json or '[]')
        except Exception:
            return []

    @allowed_reports.setter
    def allowed_reports(self, val):
        self.allowed_reports_json = json.dumps(val or [])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'icon': self.icon,
            'description': self.description,
            'allowed_screens': self.allowed_screens,
            'allowed_tabs': self.allowed_tabs,
            'allowed_reports': self.allowed_reports,
            'is_system_default': self.is_system_default,
            'users_count': self.users.count() if hasattr(self, 'users') else 0
        }


class MasterUser(db.Model):
    """
    Usuários centrais do sistema (Administrador Geral e Clientes/Empresas).
    """
    __tablename__ = 'master_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    company_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), default='client')  # 'admin' ou 'client'
    
    # Vinculação com o Segmento (nulo apenas para o admgeral)
    segment_id = db.Column(db.Integer, db.ForeignKey('master_segments.id'), nullable=True)
    
    # Configuração de isolamento de banco de dados
    # db_type: 'sqlite' (arquivo isolado em data/tenants/{slug}.db) ou 'custom_uri' (Postgres/MySQL externa)
    db_type = db.Column(db.String(20), default='sqlite')
    db_uri = db.Column(db.Text, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'company_name': self.company_name,
            'role': self.role,
            'is_admin': self.is_admin,
            'segment_id': self.segment_id,
            'segment_name': self.segment.name if self.segment else 'Administrador do Sistema',
            'db_type': self.db_type,
            'db_uri': self.db_uri,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%d/%m/%Y %H:%M') if self.created_at else ''
        }


class PasswordResetToken(db.Model):
    """
    Tokens temporários para recuperação de senha esquecida.
    """
    __tablename__ = 'master_password_resets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('master_users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('MasterUser', backref=db.backref('reset_tokens', lazy=True))

    @classmethod
    def create_token(cls, user, expires_hours=2):
        # Invalida tokens anteriores do usuário
        cls.query.filter_by(user_id=user.id, used=False).update({'used': True})
        
        token_str = secrets.token_urlsafe(32)
        expire_time = datetime.utcnow() + timedelta(hours=expires_hours)
        
        reset_obj = cls(
            user_id=user.id,
            token=token_str,
            expires_at=expire_time,
            used=False
        )
        db.session.add(reset_obj)
        db.session.commit()
        return reset_obj

    def is_valid(self):
        return not self.used and datetime.utcnow() <= self.expires_at
