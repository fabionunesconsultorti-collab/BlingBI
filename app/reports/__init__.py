"""
Mecanismo de Relatórios Encapsulados e Desacoplados (BlingBI Reporting Engine).
Permite criar, registrar, importar, exportar e gerenciar relatórios de forma independente.
"""
from app.reports.base import BaseReportModule, ReportMetadata
from app.reports.registry import report_registry
