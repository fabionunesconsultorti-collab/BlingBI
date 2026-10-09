from datetime import date
from io import BytesIO
from typing import Dict, Any, Tuple
from flask import render_template
from app.reports.base import BaseReportModule
from app.services.standard_reports import StandardReportsEngine

class CashFlowReportModule(BaseReportModule):
    """Módulo encapsulado de Fluxo de Caixa e Projeção Diária de Liquidez."""

    def get_data(self, start_date: date, end_date: date, **filters) -> Dict[str, Any]:
        days = int(filters.get('days', 30))
        return StandardReportsEngine.get_cash_flow_projection(days=days)

    def get_summary(self) -> Dict[str, Any]:
        res = self.get_data(date.today(), date.today(), days=30)
        return res.get('summary', {})

    def render(self, request_args: Dict[str, Any]) -> str:
        days = int(request_args.get('days', 30))
        report_data = self.get_data(date.today(), date.today(), days=days)

        return render_template(
            'reports/cash_flow.html',
            daily_rows=report_data.get('daily_rows', []),
            summary=report_data.get('summary', {}),
            charts=report_data.get('charts', {}),
            days=days,
            report_module=self
        )
