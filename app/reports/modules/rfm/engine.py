from datetime import date
from io import BytesIO
from typing import Dict, Any, Tuple
from flask import render_template
from app.reports.base import BaseReportModule
from app.services.standard_reports import StandardReportsEngine
from app.services.exporter import BiExporter

class RfmReportModule(BaseReportModule):
    """Módulo encapsulado de Matriz RFM e Segmentação de Clientes."""

    def get_data(self, start_date: date, end_date: date, **filters) -> Dict[str, Any]:
        cluster = filters.get('cluster', 'all')
        return StandardReportsEngine.get_rfm_matrix(cluster_filter=cluster)

    def get_summary(self) -> Dict[str, Any]:
        res = self.get_data(date.today(), date.today())
        return res.get('summary', {})

    def render(self, request_args: Dict[str, Any]) -> str:
        cluster = request_args.get('cluster', 'all')
        report_data = self.get_data(date.today(), date.today(), cluster=cluster)

        return render_template(
            'reports/rfm.html',
            customers=report_data.get('customers', []),
            summary=report_data.get('summary', {}),
            clusters=report_data.get('clusters', {}),
            selected_cluster=cluster,
            report_module=self
        )

    def export_excel(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        cluster = request_args.get('cluster', 'all')
        report_data = self.get_data(date.today(), date.today(), cluster=cluster)

        stream = BiExporter.export_rfm_to_excel(
            report_data['customers'], report_data['summary'], cluster
        )
        filename = f"BlingBI_Matriz_RFM_{date.today().strftime('%Y%m%d')}.xlsx"
        return stream, filename

    def export_pdf(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        cluster = request_args.get('cluster', 'all')
        report_data = self.get_data(date.today(), date.today(), cluster=cluster)

        stream = BiExporter.export_rfm_to_pdf(
            report_data['customers'], report_data['summary'], cluster
        )
        filename = f"BlingBI_Matriz_RFM_{date.today().strftime('%Y%m%d')}.pdf"
        return stream, filename
