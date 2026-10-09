import os
import io
import json
import zipfile
import shutil
import logging
from typing import Tuple, Optional
from app.reports.registry import report_registry

logger = logging.getLogger(__name__)

class ReportPackageManager:
    """
    Gerenciador de Portabilidade e Pacotes de Relatórios (.ZIP).
    Permite empacotar módulos para distribuição e importar novos relatórios em runtime.
    """

    @classmethod
    def export_package(cls, report_id: str) -> Tuple[Optional[io.BytesIO], str]:
        """
        Empacota a pasta do relatório em um arquivo ZIP em memória.
        Retorna (buffer_bytes, nome_arquivo).
        """
        module = report_registry.get(report_id)
        if not module or not module.module_dir or not os.path.isdir(module.module_dir):
            return None, "Relatório não encontrado"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(module.module_dir):
                # Ignora caches e arquivos temporários
                dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', '.git')]
                for file in files:
                    if file.endswith('.pyc') or file.startswith('.'):
                        continue
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, module.module_dir)
                    zf.write(abs_path, rel_path)

        zip_buffer.seek(0)
        filename = f"report_module_{report_id}_{module.version}.zip"
        return zip_buffer, filename

    @classmethod
    def import_package(cls, file_stream) -> Tuple[bool, str]:
        """
        Descompacta, valida a integridade do pacote e registra o novo relatório no sistema.
        Retorna (sucesso, mensagem).
        """
        try:
            # Lê o stream do arquivo zip
            if hasattr(file_stream, 'read'):
                file_bytes = io.BytesIO(file_stream.read())
            else:
                file_bytes = io.BytesIO(file_stream)

            if not zipfile.is_zipfile(file_bytes):
                return False, "O arquivo fornecido não é um pacote ZIP válido."

            with zipfile.ZipFile(file_bytes, 'r') as zf:
                file_list = zf.namelist()

                # Segurança contra Path Traversal
                for item in file_list:
                    if ".." in item or item.startswith("/"):
                        return False, "Arquivo ZIP contém caminhos de arquivo inválidos ou inseguros."

                # Localiza manifest.json (na raiz ou dentro de uma pasta única)
                manifest_entry = None
                prefix = ""
                if "manifest.json" in file_list:
                    manifest_entry = "manifest.json"
                else:
                    for item in file_list:
                        if item.endswith("/manifest.json") and item.count("/") == 1:
                            manifest_entry = item
                            prefix = item.rsplit("/", 1)[0] + "/"
                            break

                if not manifest_entry:
                    return False, "Pacote inválido: arquivo 'manifest.json' não foi encontrado na raiz do pacote."

                manifest_content = zf.read(manifest_entry).decode('utf-8')
                try:
                    manifest_data = json.loads(manifest_content)
                except Exception as je:
                    return False, f"Erro ao decodificar manifest.json: {je}"

                report_id = manifest_data.get('id', '').strip()
                if not report_id:
                    return False, "manifest.json deve conter um campo 'id' válido e não vazio."

                # Valida presença de engine.py
                engine_entry = f"{prefix}engine.py" if prefix else "engine.py"
                if engine_entry not in file_list:
                    return False, "Pacote inválido: arquivo 'engine.py' não foi encontrado."

                # Diretório de destino
                target_dir = os.path.join(report_registry.modules_directory, report_id)
                os.makedirs(target_dir, exist_ok=True)

                # Extrai arquivos com segurança
                for member in zf.infolist():
                    member_name = member.filename
                    if prefix and member_name.startswith(prefix):
                        dest_rel = member_name[len(prefix):]
                    else:
                        dest_rel = member_name

                    if not dest_rel or dest_rel.endswith('/'):
                        continue

                    # Ignora caches
                    if '__pycache__' in dest_rel or dest_rel.endswith('.pyc'):
                        continue

                    dest_path = os.path.join(target_dir, dest_rel)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, 'wb') as outfile:
                        outfile.write(zf.read(member))

            # Recarrega o registro
            report_registry.reload()

            loaded_report = report_registry.get(report_id)
            if not loaded_report:
                return False, f"Pacote extraído, porém a classe em engine.py não pôde ser instanciada."

            return True, f"Relatório '{loaded_report.name}' (v{loaded_report.version}) importado e ativado com sucesso!"

        except Exception as e:
            logger.error(f"[ReportPackageManager] Falha ao importar pacote: {e}", exc_info=True)
            return False, f"Erro inesperado durante a importação: {str(e)}"
