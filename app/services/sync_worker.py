import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _initial_state():
    return {
        'status': 'idle',          # 'idle', 'running', 'success', 'error'
        'current_step': 'idle',    # 'auth', 'customers', 'products', 'stocks', 'orders', 'finance', 'completed'
        'progress_percent': 0,
        'message': 'Nenhuma sincronização em andamento.',
        'started_at': None,
        'finished_at': None,
        'summary': {},
        'error': None
    }


class SyncWorker:
    """
    Gerenciador thread-safe de sincronização assíncrona em background.
    Elimina permanentemente os timeouts de gateway (504/502) no Render e outros ambientes cloud.

    IMPORTANTE (multi-tenant): a thread em background NÃO possui a sessão HTTP do Flask.
    Por isso a URI do tenant é capturada na requisição e reaplicada via TenantManager.tenant_scope,
    garantindo que Settings (tokens Bling), produtos e estoques sejam lidos/gravados na base do cliente.
    O estado é mantido separadamente por tenant.
    """
    _lock = threading.Lock()
    _threads = {}
    _states = {}

    @staticmethod
    def _key(tenant_uri):
        return tenant_uri or '__DEFAULT__'

    @classmethod
    def _resolve_tenant_uri(cls, tenant_uri=None):
        if tenant_uri:
            return tenant_uri
        try:
            from app.core.tenant_manager import TenantManager
            return TenantManager.get_current_tenant_uri()
        except Exception:
            return None

    @classmethod
    def get_status(cls, tenant_uri=None) -> dict:
        """Retorna uma cópia do estado atual da sincronização do tenant."""
        key = cls._key(cls._resolve_tenant_uri(tenant_uri))
        with cls._lock:
            state = cls._states.get(key) or _initial_state()
            copy = dict(state)
            copy['summary'] = dict(state.get('summary') or {})
            return copy

    @classmethod
    def is_running(cls, tenant_uri=None) -> bool:
        """Verifica se há uma tarefa de sincronização ativa para o tenant."""
        return cls.get_status(tenant_uri).get('status') == 'running'

    @classmethod
    def _make_progress_updater(cls, key):
        def update(step: str, progress_pct: int, message: str, summary: dict = None):
            with cls._lock:
                state = cls._states.setdefault(key, _initial_state())
                state['current_step'] = step
                state['progress_percent'] = max(0, min(100, progress_pct))
                state['message'] = message
                if summary:
                    state['summary'].update(summary)
        return update

    @classmethod
    def update_progress(cls, step: str, progress_pct: int, message: str, summary: dict = None, tenant_uri=None):
        """Atualiza o progresso da tarefa (compatibilidade)."""
        key = cls._key(cls._resolve_tenant_uri(tenant_uri))
        cls._make_progress_updater(key)(step, progress_pct, message, summary)

    @classmethod
    def start_sync(cls, app, options: dict = None, tenant_uri=None) -> tuple[bool, str]:
        """
        Inicia a sincronização em uma thread daemon em background.
        Retorna imediatamente (True, 'Sincronização iniciada com sucesso').
        """
        tenant_uri = cls._resolve_tenant_uri(tenant_uri)
        key = cls._key(tenant_uri)

        with cls._lock:
            if (cls._states.get(key) or {}).get('status') == 'running':
                return False, "Já existe uma sincronização em andamento. Aguarde a finalização."

            cls._states[key] = {
                'status': 'running',
                'current_step': 'auth',
                'progress_percent': 5,
                'message': 'Iniciando validação de conexão com a API Bling v3...',
                'started_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'finished_at': None,
                'summary': {},
                'error': None
            }

        progress_updater = cls._make_progress_updater(key)

        def finish(status, message, error=None, summary=None):
            with cls._lock:
                state = cls._states.setdefault(key, _initial_state())
                state['status'] = status
                state['progress_percent'] = 100
                state['message'] = message
                state['error'] = error
                state['finished_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                if status == 'success':
                    state['current_step'] = 'completed'
                if isinstance(summary, dict):
                    state['summary'].update(summary)

        def run_sync_task(app_instance, opts, t_uri):
            from app.core.tenant_manager import TenantManager
            from app.database import db
            with app_instance.app_context():
                with TenantManager.tenant_scope(t_uri):
                    from app.services.sync_service import SyncService
                    try:
                        logger.info(f"[SyncWorker] Sincronização em background iniciada (tenant={t_uri}).")
                        success, result = SyncService.sync_selected(
                            options=opts,
                            progress_callback=progress_updater
                        )
                        if success:
                            finish('success', 'Sincronização concluída com sucesso!', summary=result)
                        else:
                            finish('error', f"Falha na sincronização: {result}", error=str(result))
                    except Exception as e:
                        logger.error(f"[SyncWorker] Erro crítico na sincronização: {e}", exc_info=True)
                        finish('error', f"Erro inesperado: {str(e)}", error=str(e))
                    finally:
                        try:
                            db.session.remove()
                        except Exception:
                            pass

        app_obj = app._get_current_object() if hasattr(app, '_get_current_object') else app
        thread = threading.Thread(
            target=run_sync_task,
            args=(app_obj, options or {}, tenant_uri),
            daemon=True
        )
        cls._threads[key] = thread
        thread.start()
        return True, "Sincronização em segundo plano iniciada com sucesso!"
