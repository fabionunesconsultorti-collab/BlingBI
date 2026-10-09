from datetime import date
from io import BytesIO
from typing import Dict, Any, Tuple
from flask import render_template
from app.reports.base import BaseReportModule
from app.services.bi_data_library import BiDataLibrary
from app.services.standard_reports import StandardReportsEngine
from app.services.exporter import BiExporter

class StockCoverageReportModule(BaseReportModule):
    """Módulo encapsulado de Cobertura de Estoque, Giro e Curva ABC."""

    def get_data(self, start_date: date, end_date: date, **filters) -> Dict[str, Any]:
        category = filters.get('category', 'all')
        status = filters.get('status', 'all')
        return StandardReportsEngine.get_stock_coverage_and_abc(
            start_date=start_date,
            end_date=end_date,
            category_filter=category,
            status_filter=status
        )

    def get_summary(self) -> Dict[str, Any]:
        start_date, end_date = BiDataLibrary.parse_date_filter('last_30_days')
        res = self.get_data(start_date, end_date)
        return res.get('summary', {})

    def render(self, request_args: Dict[str, Any]) -> str:
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')
        category = request_args.get('category', 'all')
        status_cov = request_args.get('status', 'all')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)
        report_data = self.get_data(start_date, end_date, category=category, status=status_cov)

        items = report_data.get('items', [])
        categories = sorted(list(set(p['category'] for p in items if p.get('category'))))

        return render_template(
            'reports/stock_coverage.html',
            items=items,
            summary=report_data.get('summary', {}),
            charts=report_data.get('charts', {}),
            categories=categories,
            selected_category=category,
            selected_status=status_cov,
            period=period,
            start_date=start_date,
            end_date=end_date,
            report_module=self
        )

    def export_excel(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')
        category = request_args.get('category', 'all')
        status_cov = request_args.get('status', 'all')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)
        report_data = self.get_data(start_date, end_date, category=category, status=status_cov)

        stream = BiExporter.export_stock_coverage_to_excel(
            report_data['items'], report_data['summary'], start_date, end_date
        )
        filename = f"BlingBI_Cobertura_Estoque_ABC_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
        return stream, filename

    def export_pdf(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')
        category = request_args.get('category', 'all')
        status_cov = request_args.get('status', 'all')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)
        report_data = self.get_data(start_date, end_date, category=category, status=status_cov)

        stream = BiExporter.export_stock_coverage_to_pdf(
            report_data['items'], report_data['summary'], start_date, end_date
        )
        filename = f"BlingBI_Cobertura_Estoque_ABC_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return stream, filename
