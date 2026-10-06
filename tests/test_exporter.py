from datetime import date, timedelta
from app.services.bi_analytics import BiAnalytics
from app.services.exporter import BiExporter

def test_export_sales_excel(app):
    start = date.today() - timedelta(days=30)
    end = date.today()
    analytics = BiAnalytics.get_sales_analytics(start, end)

    excel_io = BiExporter.export_sales_to_excel(analytics['orders'], start, end)
    content = excel_io.getvalue()
    
    assert len(content) > 0
    # Verifica assinatura PK (formato zip/xlsx padrão)
    assert content.startswith(b'PK')

def test_export_products_excel(app):
    start = date.today() - timedelta(days=30)
    end = date.today()
    analytics = BiAnalytics.get_products_analytics(start, end)

    excel_io = BiExporter.export_products_to_excel(analytics['abc_products'], start, end)
    content = excel_io.getvalue()
    
    assert len(content) > 0
    assert content.startswith(b'PK')

def test_export_sales_pdf(app):
    start = date.today() - timedelta(days=30)
    end = date.today()
    analytics = BiAnalytics.get_sales_analytics(start, end)

    pdf_io = BiExporter.export_sales_to_pdf(
        analytics['orders'],
        start,
        end,
        analytics['total_gross'],
        analytics['avg_ticket']
    )
    content = pdf_io.getvalue()

    assert len(content) > 0
    # Verifica assinatura %PDF
    assert content.startswith(b'%PDF')
