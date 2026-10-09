from datetime import date
from io import BytesIO
from typing import Dict, Any, Tuple
from flask import render_template
from app.reports.base import BaseReportModule
from app.services.bi_data_library import BiDataLibrary
from app.services.fashion_bi import FashionBiEngine
from app.models.fashion import ConditionalBag
from app.services.demo_fashion_data import seed_fashion_demo_data
from app.services.exporter import BiExporter

class FashionBiReportModule(BaseReportModule):
    """Módulo encapsulado de Inteligência para Varejo de Moda e Customer Success."""

    def get_data(self, start_date: date, end_date: date, **filters) -> Dict[str, Any]:
        seller = filters.get('seller') if filters.get('seller') != 'all' else None
        category = filters.get('category') if filters.get('category') != 'all' else None
        abc_class = filters.get('abc_class') if filters.get('abc_class') != 'all' else None
        month = filters.get('month', date.today().month)
        tier = filters.get('tier') if filters.get('tier') != 'all' else None
        reason = filters.get('reason') if filters.get('reason') != 'all' else None

        profiles_data = FashionBiEngine.get_customer_purchase_profiles(
            start_date, end_date, seller=seller, category=category
        )
        abc_data = FashionBiEngine.get_customer_abc_curve(
            start_date, end_date, seller=seller, abc_class=abc_class
        )
        birthdays_data = FashionBiEngine.get_birthday_customers(target_month=month)
        bags_data = FashionBiEngine.get_conditional_bags_analytics(
            start_date, end_date, seller=seller
        )
        top_categories_data = FashionBiEngine.get_top_products_by_category(
            start_date, end_date, category=category
        )
        returns_data = FashionBiEngine.get_returns_and_exchanges_report(
            start_date, end_date, seller=seller, reason=reason
        )
        service_kpis = FashionBiEngine.get_service_performance_kpis(
            start_date, end_date, seller=seller
        )
        inactives_data = FashionBiEngine.get_inactive_customers_report(tier_filter=tier)
        cohort_data = FashionBiEngine.get_repurchase_cohort()
        satisfaction = FashionBiEngine.get_satisfaction_metrics(
            start_date, end_date, seller=seller
        )

        return {
            'summary': {
                'bags_conversion_rate': bags_data.get('conversion_rate', 0.0),
                'bags_sold_pieces': bags_data.get('sold_pieces', 0),
                'nps_score': satisfaction.get('nps', 0),
                'active_sellers': len(service_kpis.get('sellers', []))
            },
            'profiles_data': profiles_data,
            'abc_data': abc_data,
            'birthdays_data': birthdays_data,
            'bags_data': bags_data,
            'top_categories_data': top_categories_data,
            'returns_data': returns_data,
            'service_kpis': service_kpis,
            'inactives_data': inactives_data,
            'cohort_data': cohort_data,
            'satisfaction': satisfaction
        }

    def get_summary(self) -> Dict[str, Any]:
        start_date, end_date = BiDataLibrary.parse_date_filter('last_30_days')
        res = self.get_data(start_date, end_date)
        return res.get('summary', {})

    def render(self, request_args: Dict[str, Any]) -> str:
        tab = request_args.get('tab', 'block1')
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')

        seller = request_args.get('seller', 'all')
        category = request_args.get('category', 'all')
        abc_class = request_args.get('abc_class', 'all')
        month_str = request_args.get('month', '')
        month = int(month_str) if month_str.isdigit() else date.today().month
        tier = request_args.get('tier', 'all')
        reason = request_args.get('reason', 'all')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)

        # Auto-popula dados de demonstração caso banco vazio
        if ConditionalBag.query.count() == 0:
            try:
                seed_fashion_demo_data()
            except Exception:
                pass

        filter_options = FashionBiEngine.get_filter_options()
        data = self.get_data(
            start_date, end_date,
            seller=seller, category=category, abc_class=abc_class,
            month=month, tier=tier, reason=reason
        )

        return render_template(
            'fashion_bi.html',
            active_tab=tab,
            period=period,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            current_seller=seller,
            current_category=category,
            current_abc_class=abc_class,
            current_month=month,
            current_tier=tier,
            current_reason=reason,
            filter_options=filter_options,
            profiles_data=data['profiles_data'],
            abc_data=data['abc_data'],
            birthdays_data=data['birthdays_data'],
            bags_data=data['bags_data'],
            top_categories_data=data['top_categories_data'],
            returns_data=data['returns_data'],
            service_kpis=data['service_kpis'],
            inactives_data=data['inactives_data'],
            cohort_data=data['cohort_data'],
            satisfaction=data['satisfaction'],
            report_module=self
        )

    def export_excel(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        tab = request_args.get('tab', 'block1')
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')
        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)

        bags_data = FashionBiEngine.get_conditional_bags_analytics(start_date, end_date)
        stream = BiExporter.export_fashion_bi_to_excel(bags_data, start_date, end_date)
        filename = f"BlingBI_Fashion_BI_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
        return stream, filename

    def export_pdf(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        tab = request_args.get('tab', 'block1')
        period = request_args.get('period', 'last_30_days')
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')
        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)

        bags_data = FashionBiEngine.get_conditional_bags_analytics(start_date, end_date)
        stream = BiExporter.export_fashion_bi_to_pdf(bags_data, start_date, end_date)
        filename = f"BlingBI_Fashion_BI_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return stream, filename
