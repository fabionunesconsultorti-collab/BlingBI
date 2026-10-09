from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple
from app.models.setting import Setting
from app.services.bi_data_library import BiDataLibrary

@dataclass
class ReportMetadata:
    id: str
    name: str
    category: str
    description: str
    version: str = "1.0.0"
    author: str = "BlingBI Core"
    icon: str = "bar-chart"
    color: str = "#008B54"
    tags: List[str] = field(default_factory=list)
    export_formats: List[str] = field(default_factory=lambda: ["excel", "pdf"])
    default_period: str = "last_30_days"
    legacy_url: Optional[str] = None

class BaseReportModule(ABC):
    """
    Classe base obrigatória para todos os Módulos de Relatórios Encapsulados.
    
    Cada relatório implementa sua lógica de extração através da BiDataLibrary,
    formatações, cálculos analíticos e exportação, mantendo total independência.
    """

    def __init__(self, metadata: ReportMetadata, module_dir: Optional[str] = None):
        self.metadata = metadata
        self.module_dir = module_dir

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def category(self) -> str:
        return self.metadata.category

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def version(self) -> str:
        return self.metadata.version

    @property
    def is_enabled(self) -> bool:
        """Verifica se o relatório está ativo nas configurações do sistema."""
        val = Setting.get(f"report_{self.id}_enabled", "1")
        return val == "1"

    def set_enabled(self, enabled: bool) -> None:
        """Habilita ou desabilita o relatório."""
        Setting.set(f"report_{self.id}_enabled", "1" if enabled else "0")

    @abstractmethod
    def get_data(self, start_date: date, end_date: date, **filters) -> Dict[str, Any]:
        """
        Executa a agregação analítica consumindo a BiDataLibrary.
        Deve retornar dicionário estruturado para alimentar a view e gráficos.
        """
        pass

    def get_summary(self) -> Dict[str, Any]:
        """
        Retorna métricas resumidas para os cards rápidos da Central/Hub de Relatórios.
        Padrão: calcula para os últimos 30 dias.
        """
        start_date, end_date = BiDataLibrary.parse_date_filter("last_30_days")
        try:
            data = self.get_data(start_date, end_date)
            return data.get("summary", {})
        except Exception:
            return {}

    @abstractmethod
    def render(self, request_args: Dict[str, Any]) -> str:
        """
        Processa os parâmetros da requisição HTTP e renderiza o template HTML do relatório.
        """
        pass

    def export_excel(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        """
        Gera a planilha Excel (.xlsx) para download.
        Retorna tupla: (BytesIO_stream, nome_do_arquivo)
        """
        raise NotImplementedError(f"Exportação em Excel não implementada no relatório {self.id}")

    def export_pdf(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        """
        Gera o documento PDF para download.
        Retorna tupla: (BytesIO_stream, nome_do_arquivo)
        """
        raise NotImplementedError(f"Exportação em PDF não implementada no relatório {self.id}")
