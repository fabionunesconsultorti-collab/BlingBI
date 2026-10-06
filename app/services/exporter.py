import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class BiExporter:
    @staticmethod
    def export_sales_to_excel(orders_data, start_date, end_date):
        """Gera planilha Excel (.xlsx) com o relatório de vendas."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Relatório de Vendas"

        # Cores padrão Bling
        bling_green = PatternFill(start_color="008B54", end_color="008B54", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="008B54")
        bold_font = Font(name="Calibri", size=10, bold=True)
        thin_border = Border(
            left=Side(style='thin', color='DDDDDD'),
            right=Side(style='thin', color='DDDDDD'),
            top=Side(style='thin', color='DDDDDD'),
            bottom=Side(style='thin', color='DDDDDD')
        )

        # Cabeçalho do documento
        ws.append(["BLING BI - RELATÓRIO DE VENDAS E PEDIDOS"])
        ws.cell(row=1, column=1).font = title_font
        ws.append([f"Período: {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')} | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"])
        ws.append([])

        # Tabela
        headers = ["Nº Pedido", "Data", "Cliente", "Canal / Loja", "Itens", "Desconto (R$)", "Frete (R$)", "Total (R$)", "Situação"]
        ws.append(headers)

        header_row = 4
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.fill = bling_green
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        total_sum = 0.0
        row_idx = 5
        for o in orders_data:
            tot = float(o.get('total', 0.0))
            if o.get('status') == 'Atendido':
                total_sum += tot

            ws.append([
                o.get('number', ''),
                o.get('order_date', ''),
                o.get('customer_name', ''),
                o.get('channel', ''),
                o.get('items_count', 0),
                float(o.get('discount', 0.0)),
                float(o.get('shipping', 0.0)),
                tot,
                o.get('status', '')
            ])
            for col_idx in range(1, len(headers) + 1):
                c = ws.cell(row=row_idx, column=col_idx)
                c.border = thin_border
                if col_idx in [6, 7, 8]:
                    c.number_format = 'R$ #,##0.00'
                    c.alignment = Alignment(horizontal="right")
                elif col_idx in [1, 2, 5, 9]:
                    c.alignment = Alignment(horizontal="center")
            row_idx += 1

        # Linha Totalizadora
        ws.append(["TOTAL ATENDIDO", "", "", "", "", "", "", total_sum, ""])
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=row_idx, column=col_idx)
            c.font = bold_font
            c.border = thin_border
            if col_idx == 8:
                c.number_format = 'R$ #,##0.00'
                c.alignment = Alignment(horizontal="right")

        # Ajuste automático de largura de colunas
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def export_products_to_excel(products_data, start_date, end_date):
        """Gera planilha Excel com a Curva ABC e Produtos."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Curva ABC Produtos"

        bling_green = PatternFill(start_color="008B54", end_color="008B54", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="008B54")
        thin_border = Border(
            left=Side(style='thin', color='DDDDDD'),
            right=Side(style='thin', color='DDDDDD'),
            top=Side(style='thin', color='DDDDDD'),
            bottom=Side(style='thin', color='DDDDDD')
        )

        ws.append(["BLING BI - CURVA ABC DE PRODUTOS"])
        ws.cell(row=1, column=1).font = title_font
        ws.append([f"Período: {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}"])
        ws.append([])

        headers = ["Classe", "SKU", "Produto", "Qtd Vendida", "Faturamento (R$)", "Custo Total (R$)", "Margem Líquida (R$)", "% Margem", "% Acumulado", "Estoque Atual"]
        ws.append(headers)

        header_row = 4
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.fill = bling_green
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        row_idx = 5
        for p in products_data:
            ws.append([
                p.get('class', 'C'),
                p.get('sku', ''),
                p.get('name', ''),
                p.get('qty_sold', 0),
                p.get('revenue', 0.0),
                p.get('cost', 0.0),
                p.get('margin', 0.0),
                f"{p.get('margin_pct', 0.0):.1f}%",
                f"{p.get('accumulated_pct', 0.0):.1f}%",
                p.get('stock', 0)
            ])
            for col_idx in range(1, len(headers) + 1):
                c = ws.cell(row=row_idx, column=col_idx)
                c.border = thin_border
                if col_idx in [5, 6, 7]:
                    c.number_format = 'R$ #,##0.00'
                    c.alignment = Alignment(horizontal="right")
                elif col_idx in [1, 4, 8, 9, 10]:
                    c.alignment = Alignment(horizontal="center")
            row_idx += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @staticmethod
    def export_sales_to_pdf(orders_data, start_date, end_date, total_gross, avg_ticket):
        """Gera relatório de vendas profissional em PDF."""
        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            textColor=colors.HexColor('#008B54'),
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            'SubTitleStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=15
        )
        kpi_style = ParagraphStyle(
            'KpiStyle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=colors.HexColor('#1E293B')
        )

        elements.append(Paragraph("BlingBI - Relatório Executivo de Vendas", title_style))
        period_text = f"Período: {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')} | Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        elements.append(Paragraph(period_text, subtitle_style))

        # Tabela de Resumo KPI
        kpi_data = [
            [
                Paragraph(f"<b>Faturamento Total:</b> R$ {total_gross:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'), kpi_style),
                Paragraph(f"<b>Pedidos Atendidos:</b> {len([o for o in orders_data if o.get('status') == 'Atendido'])}", kpi_style),
                Paragraph(f"<b>Ticket Médio:</b> R$ {avg_ticket:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'), kpi_style)
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[260, 260, 260])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#008B54')),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 15))

        # Tabela Detalhada de Pedidos
        table_headers = ["Nº Pedido", "Data", "Cliente", "Canal / Loja", "Itens", "Total", "Status"]
        table_rows = [table_headers]

        for o in orders_data[:40]: # Limita a 40 para visualização limpa
            table_rows.append([
                str(o.get('number', '')),
                str(o.get('order_date', '')),
                str(o.get('customer_name', 'Consumidor'))[:25],
                str(o.get('channel', ''))[:18],
                str(o.get('items_count', 0)),
                f"R$ {float(o.get('total', 0.0)):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                str(o.get('status', ''))
            ])

        orders_table = Table(table_rows, colWidths=[70, 75, 230, 160, 50, 100, 95])
        orders_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#008B54')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('ALIGN', (5, 0), (5, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        elements.append(orders_table)

        doc.build(elements)
        output.seek(0)
        return output
