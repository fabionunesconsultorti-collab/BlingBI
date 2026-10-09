from datetime import date
from io import BytesIO
from typing import Dict, Any, Tuple
from flask import render_template
from app.reports.base import BaseReportModule
from app.services.bi_data_library import BiDataLibrary
from app.services.standard_reports import StandardReportsEngine
from app.services.exporter import BiExporter

class DreReportModule(BaseReportModule):
    """Módulo encapsulado de Demonstrativo do Resultado do Exercício (DRE Gerencial)."""

    def get_data(self, start_date: date, end_date: date, **filters) -> Dict[str, Any]:
        return StandardReportsEngine.get_dre_statement(start_date=start_date, end_date=end_date)

    def get_summary(self) -> Dict[str, Any]:
        start_date, end_date = BiDataLibrary.parse_date_filter('last_30_days')
        res = self.get_data(start_date, end_date)
        return res.get('summary', {})

    def render(self, request_args: Dict[str, Any]) -> str:
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)
        report_data = self.get_data(start_date, end_date)

        return render_template(
            'reports/dre.html',
            lines=report_data.get('lines', []),
            summary=report_data.get('summary', {}),
            charts=report_data.get('charts', {}),
            period=period,
            start_date=start_date,
            end_date=end_date,
            report_module=self
        )

    def export_excel(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)
        report_data = self.get_data(start_date, end_date)

        stream = BiExporter.export_dre_to_excel(
            report_data['lines'], report_data['summary'], start_date, end_date
        )
        filename = f"BlingBI_DRE_Gerencial_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
        return stream, filename

    def export_pdf(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)
        report_data = self.get_data(start_date, end_date)

        stream = BiExporter.export_dre_to_pdf(
            report_data['lines'], report_data['summary'], start_date, end_date
        )
        filename = f"BlingBI_DRE_Gerencial_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return stream, filename
