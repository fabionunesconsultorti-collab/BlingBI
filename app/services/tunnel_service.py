import subprocess
import threading
import re
import time
import os
import signal
import logging
from app.models.setting import Setting

import shutil
import glob

logger = logging.getLogger(__name__)

def _find_npx():
    npx_bin = shutil.which('npx')
    if npx_bin:
        return npx_bin
    home = os.path.expanduser('~')
    nvm_candidates = sorted(glob.glob(os.path.join(home, '.nvm/versions/node/*/bin/npx')), reverse=True)
    if nvm_candidates and os.path.exists(nvm_candidates[0]):
        return nvm_candidates[0]
    for path in ['/usr/local/bin/npx', '/usr/bin/npx', r'C:\Program Files\nodejs\npx.cmd']:
        if os.path.exists(path):
            return path
    return 'npx'

class TunnelService:
    _process = None
    _url = None
    _lock = threading.Lock()

    @classmethod
    def get_status(cls):
        """Retorna se o túnel está ativo e a URL atual."""
        with cls._lock:
            is_alive = cls._process is not None and cls._process.poll() is None
            if not is_alive:
                cls._process = None
                cls._url = None
            return {
                'active': is_alive,
                'url': cls._url or Setting.get('bling_webhook_url', '')
            }

    @classmethod
    def start_tunnel(cls, port=5000):
        """Inicia o túnel HTTPS em segundo plano e retorna a URL pública gerada."""
        with cls._lock:
            # Se já estiver rodando, retorna a URL
            if cls._process is not None and cls._process.poll() is None:
                if cls._url:
                    return True, cls._url

            # Tenta iniciar via localtunnel (npx)
            try:
                npx_bin = _find_npx()
                cmd = [npx_bin, "-y", "localtunnel", "--port", str(port)]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    preexec_fn=os.setsid if os.name != 'nt' else None
                )

                extracted_url = None
                start_time = time.time()

                # Aguarda até 12 segundos para a URL ser impressa
                while time.time() - start_time < 12:
                    line = process.stdout.readline()
                    if not line:
                        if process.poll() is not None:
                            break
                        time.sleep(0.2)
                        continue

                    logger.info(f"[Localtunnel stdout] {line.strip()}")
                    # Busca padrão https://*.loca.lt ou https://*
                    match = re.search(r'(https://[a-zA-Z0-9-]+\.loca\.lt)', line)
                    if match:
                        extracted_url = match.group(1)
                        break

                if extracted_url:
                    full_webhook_url = f"{extracted_url.rstrip('/')}/integrations/webhook"
                    cls._process = process
                    cls._url = full_webhook_url
                    try:
                        from flask import has_app_context
                        if has_app_context():
                            Setting.set('bling_webhook_url', full_webhook_url)
                        else:
                            from app import create_app
                            app = create_app()
                            with app.app_context():
                                Setting.set('bling_webhook_url', full_webhook_url)
                    except Exception as set_err:
                        logger.warning(f"Não foi possível salvar setting automaticamente: {set_err}")

                    logger.info(f"Túnel iniciado com sucesso: {full_webhook_url}")
                    return True, full_webhook_url
                else:
                    # Mata o processo se falhou ao obter URL
                    try:
                        if os.name != 'nt':
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        else:
                            process.terminate()
                    except Exception:
                        pass
                    return False, "Não foi possível obter a URL do túnel em tempo hábil."

            except Exception as e:
                logger.error(f"Erro ao iniciar túnel: {e}", exc_info=True)
                return False, str(e)

    @classmethod
    def stop_tunnel(cls):
        """Finaliza o processo do túnel se estiver ativo."""
        with cls._lock:
            if cls._process is not None:
                try:
                    if os.name != 'nt':
                        os.killpg(os.getpgid(cls._process.pid), signal.SIGTERM)
                    else:
                        cls._process.terminate()
                except Exception as e:
                    logger.warning(f"Erro ao encerrar processo do túnel: {e}")
                cls._process = None
                cls._url = None
                return True
            return False
