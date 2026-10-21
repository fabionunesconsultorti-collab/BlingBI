import os
from datetime import datetime
from app.database import db

class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls, key, default=None):
        # 1. Busca no banco de dados ativo (Tenant atual)
        try:
            item = cls.query.filter_by(key=key).first()
            if item and item.value is not None and str(item.value).strip() != '':
                return item.value
        except Exception:
            pass

        # 2. Se não encontrou no Tenant, busca no Master DB como fallback
        try:
            from app.core.tenant_manager import TenantManager
            with TenantManager.master_scope():
                master_item = cls.query.filter_by(key=key).first()
                if master_item and master_item.value is not None and str(master_item.value).strip() != '':
                    return master_item.value
        except Exception:
            pass

        # 3. Fallback para variáveis de ambiente (ex: BLING_CLIENT_ID, BLING_ACCESS_TOKEN no Render/.env)
        env_val = os.environ.get(key.upper()) or os.environ.get(key)
        if env_val is not None and str(env_val).strip() != '':
            return str(env_val).strip()

        return default

    @classmethod
    def set(cls, key, value):
        str_val = str(value) if value is not None else ''
        try:
            item = cls.query.filter_by(key=key).first()
            if not item:
                item = cls(key=key)
                db.session.add(item)
            item.value = str_val
            item.updated_at = datetime.utcnow()
            db.session.commit()

            # Se for configuração do Bling, sincroniza também no Master DB
            if key.startswith('bling_'):
                try:
                    from app.core.tenant_manager import TenantManager
                    with TenantManager.master_scope():
                        m_item = cls.query.filter_by(key=key).first()
                        if not m_item:
                            m_item = cls(key=key)
                            db.session.add(m_item)
                        m_item.value = str_val
                        m_item.updated_at = datetime.utcnow()
                        db.session.commit()
                except Exception:
                    pass

            return item
        except Exception as e:
            db.session.rollback()
            raise e
