import os
import json
import logging
import importlib.util
from typing import Dict, Any, List, Optional
from app.reports.base import BaseReportModule, ReportMetadata

logger = logging.getLogger(__name__)

class ReportRegistry:
    """
    Registro Central de Módulos de Relatórios do BlingBI.
    Gerencia o ciclo de vida, descoberta automática, ativação e recarregamento.
    """

    def __init__(self):
        self._modules: Dict[str, BaseReportModule] = {}
        self._modules_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "modules")
        )

    @property
    def modules_directory(self) -> str:
        return self._modules_dir

    def register(self, module: BaseReportModule) -> None:
        """Registra um módulo no catálogo central."""
        self._modules[module.id] = module
        logger.info(f"[ReportRegistry] Relatório registrado: {module.id} ({module.name})")

    def unregister(self, report_id: str) -> Optional[BaseReportModule]:
        """Remove um módulo do catálogo."""
        return self._modules.pop(report_id, None)

    def get(self, report_id: str) -> Optional[BaseReportModule]:
        """Recupera um módulo pelo seu identificador único."""
        return self._modules.get(report_id)

    def get_all(self, category: Optional[str] = None, active_only: bool = False) -> List[BaseReportModule]:
        """Retorna todos os módulos registrados, com filtros opcionais de categoria e ativação."""
        modules = list(self._modules.values())
        if category and category != 'all':
            modules = [m for m in modules if m.category.lower() == category.lower()]
        if active_only:
            modules = [m for m in modules if m.is_enabled]
        return modules

    def get_categories(self) -> List[Dict[str, Any]]:
        """Retorna todas as categorias existentes e suas contagens de relatórios."""
        cat_counts: Dict[str, int] = {}
        for m in self._modules.values():
            cat = m.category.lower()
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        cat_labels = {
            'comercial': 'Vendas & Comercial',
            'produtos': 'Produtos & Estoque',
            'clientes': 'Clientes & CRM',
            'financeiro': 'Financeiro & Controladoria',
            'moda': 'Moda & Varejo de Vestuário',
            'personalizado': 'Personalizados / Custom'
        }

        result = []
        for cat, count in cat_counts.items():
            result.append({
                'id': cat,
                'name': cat_labels.get(cat, cat.capitalize()),
                'count': count
            })
        return sorted(result, key=lambda x: x['name'])

    def discover_and_register_modules(self) -> int:
        """
        Varre a pasta de módulos, lê os manifestos e instancia os módulos dinamicamente.
        Retorna o total de módulos carregados com sucesso.
        """
        if not os.path.exists(self._modules_dir):
            os.makedirs(self._modules_dir, exist_ok=True)
            return 0

        loaded_count = 0
        for entry in os.scandir(self._modules_dir):
            if not entry.is_dir():
                continue

            manifest_path = os.path.join(entry.path, "manifest.json")
            engine_path = os.path.join(entry.path, "engine.py")

            if not os.path.exists(manifest_path) or not os.path.exists(engine_path):
                continue

            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)

                metadata = ReportMetadata(
                    id=manifest_data.get('id', entry.name),
                    name=manifest_data.get('name', entry.name.capitalize()),
                    category=manifest_data.get('category', 'personalizado'),
                    description=manifest_data.get('description', ''),
                    version=manifest_data.get('version', '1.0.0'),
                    author=manifest_data.get('author', 'Comunidade'),
                    icon=manifest_data.get('icon', 'bar-chart'),
                    color=manifest_data.get('color', '#008B54'),
                    tags=manifest_data.get('tags', []),
                    export_formats=manifest_data.get('export_formats', ['excel', 'pdf']),
                    default_period=manifest_data.get('default_period', 'last_30_days'),
                    legacy_url=manifest_data.get('legacy_url')
                )

                # Carregamento dinâmico via importlib
                module_name = f"app.reports.modules.{metadata.id}.engine"
                spec = importlib.util.spec_from_file_location(module_name, engine_path)
                if spec and spec.loader:
                    py_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(py_module)

                    # Procura classe derivada de BaseReportModule
                    target_cls = None
                    for attr_name in dir(py_module):
                        attr = getattr(py_module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BaseReportModule) and attr is not BaseReportModule:
                            target_cls = attr
                            break

                    if target_cls:
                        instance = target_cls(metadata, module_dir=entry.path)
                        self.register(instance)
                        loaded_count += 1
                    else:
                        logger.warning(f"[ReportRegistry] Nenhuma subclasse de BaseReportModule em {engine_path}")

            except Exception as e:
                logger.error(f"[ReportRegistry] Falha ao carregar relatório de {entry.path}: {e}", exc_info=True)

        return loaded_count

    def reload(self) -> int:
        """Limpa e recarrega todos os módulos do disco."""
        self._modules.clear()
        return self.discover_and_register_modules()


# Instância global singleton
report_registry = ReportRegistry()
