from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session

class MultiTenantSession(Session):
    """
    Sessão customizada do SQLAlchemy que direciona consultas automaticamente:
    - Modelos Master (master_users, master_segments, master_password_resets) vão para o Master DB.
    - Modelos Operacionais do Cliente (orders, products, customers, financial, etc.) vão para a base dedicada do Tenant.
    """
    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        # 1. Se um bind explícito foi passado
        if bind is not None:
            return bind

        # 2. Se o mapper apontar para tabelas do Master DB
        if mapper is not None and hasattr(mapper, 'class_'):
            tablename = getattr(mapper.class_, '__tablename__', '')
            if tablename.startswith('master_'):
                return self._db.engines[None]

        # 3. Se houver uma cláusula SQL expressa sobre tabelas master
        if clause is not None:
            try:
                clause_str = str(clause)
                if 'master_' in clause_str:
                    return self._db.engines[None]
            except Exception:
                pass

        # 4. Verifica se há um tenant ativo no contexto da requisição
        try:
            from app.core.tenant_manager import TenantManager
            tenant_uri = TenantManager.get_current_tenant_uri()
            if tenant_uri and tenant_uri != "__MASTER__":
                tenant_engine = TenantManager.get_engine(tenant_uri)
                if tenant_engine is not None:
                    return tenant_engine
        except Exception:
            pass

        # 5. Fallback padrão para o Master Engine
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)

db = SQLAlchemy(session_options={'class_': MultiTenantSession})
