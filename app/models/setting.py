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
        item = cls.query.filter_by(key=key).first()
        return item.value if item and item.value is not None else default

    @classmethod
    def set(cls, key, value):
        try:
            item = cls.query.filter_by(key=key).first()
            if not item:
                item = cls(key=key)
                db.session.add(item)
            item.value = str(value) if value is not None else ''
            item.updated_at = datetime.utcnow()
            db.session.commit()
            return item
        except Exception as e:
            db.session.rollback()
            raise e
