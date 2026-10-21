import threading
import logging
from datetime import datetime
from flask import current_app

logger = logging.getLogger(__name__)

class SyncWorker:
    """
    Gerenciador thread-safe de sincronização assíncrona em background.
    Elimina permanentemente os timeouts de gateway (504/502) no Render e outros ambientes cloud.
    """
    _lock = threading.Lock()
    _thread = None
    _state = {
        'status': 'idle',          # 'idle', 'running', 'success', 'error'
        'current_step': 'idle',    # 'auth', 'customers', 'products', 'stocks', 'orders', 'finance', 'completed'
        'progress_percent': 0,
        'message': 'Nenhuma sincronização em andamento.',
        'started_at': None,
        'finished_at': None,
        'summary': {},
        'error': None
    }

    @classmethod
    def get_status(cls) -> dict:
        """Retorna uma cópia do estado atual da sincronização."""
        with cls._lock:
            return dict(cls._state)

    @classmethod
    def is_running(cls) -> bool:
        """Verifica se há uma tarefa de sincronização ativa no momento."""
        with cls._lock:
            return cls._state.get('status') == 'running'

    @classmethod
    def update_progress(cls, step: str, progress_pct: int, message: str, summary: dict = None):
        """Atualiza o progresso da tarefa em andamento de forma thread-safe."""
        with cls._lock:
            cls._state['current_step'] = step
            cls._state['progress_percent'] = max(0, min(100, progress_pct))
            cls._state['message'] = message
            if summary:
                cls._state['summary'].update(summary)

    @classmethod
    def start_sync(cls, app, options: dict = None) -> tuple[bool, str]:
        """
        Inicia a sincronização em uma thread daemon em background.
        Retorna imediatamente (True, 'Sincronização iniciada com sucesso').
        """
        with cls._lock:
            if cls._state.get('status') == 'running':
                return False, "Já existe uma sincronização em andamento. Aguarde a finalização."

            cls._state = {
                'status': 'running',
                'current_step': 'auth',
                'progress_percent': 5,
                'message': 'Iniciando validação de conexão com a API Bling v3...',
                'started_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'finished_at': None,
                'summary': {},
                'error': None
            }

        def run_sync_task(app_instance, opts):
            with app_instance.app_context():
                from app.services.sync_service import SyncService
                try:
                    logger.info("[SyncWorker] Tarefa de sincronização em background iniciada.")
                    success, result = SyncService.sync_selected(
                        options=opts,
                        progress_callback=cls.update_progress
                    )
                    with cls._lock:
                        if success:
                            cls._state['status'] = 'success'
                            cls._state['current_step'] = 'completed'
                            cls._state['progress_percent'] = 100
                            cls._state['message'] = 'Sincronização concluída com sucesso!'
                            cls._state['finished_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                            if isinstance(result, dict):
                                cls._state['summary'].update(result)
                        else:
                            cls._state['status'] = 'error'
                            cls._state['progress_percent'] = 100
                            cls._state['error'] = str(result)
                            cls._state['message'] = f"Falha na sincronização: {result}"
                            cls._state['finished_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.error(f"[SyncWorker] Erro crítico na sincronização: {e}", exc_info=True)
                    with cls._lock:
                        cls._state['status'] = 'error'
                        cls._state['progress_percent'] = 100
                        cls._state['error'] = str(e)
                        cls._state['message'] = f"Erro inesperado: {str(e)}"
                        cls._state['finished_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        cls._thread = threading.Thread(
            target=run_sync_task,
            args=(app._get_current_object() if hasattr(app, '_get_current_object') else app, options or {}),
            daemon=True
        )
        cls._thread.start()
        return True, "Sincronização em segundo plano iniciada com sucesso!"
