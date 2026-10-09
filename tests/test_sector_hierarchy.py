import pytest

def test_sector_sales_routes(client):
    """Testa todas as telas e abas do Setor 1: Vendas e Pedidos"""
    routes = [
        '/sales/',
        '/sales/multichannel',
        '/sales/sellers',
        '/sales/conditional-bags'
    ]
    for r in routes:
        res = client.get(r)
        assert res.status_code == 200, f"Falha na rota {r}: status {res.status_code}"
        assert b'Vendas e Pedidos' in res.data or b'Vendas &amp; Pedidos' in res.data

def test_sector_products_routes(client):
    """Testa todas as telas e abas do Setor 2: Produtos e Curva ABC"""
    routes = [
        '/products/',
        '/products/abc',
        '/products/stock-coverage',
        '/products/returns'
    ]
    for r in routes:
        res = client.get(r)
        assert res.status_code == 200, f"Falha na rota {r}: status {res.status_code}"
        assert b'Produtos e Curva ABC' in res.data or b'Produtos &amp; Curva ABC' in res.data

    # A rota anterior de busca agora redireciona transparentemente para a aba de inventário e catálogo
    res_search_redirect = client.get('/products/search')
    assert res_search_redirect.status_code == 302
    assert '/products/' in res_search_redirect.headers.get('Location', '')

def test_sector_customers_routes(client):
    """Testa todas as telas e abas do Setor 3: Clientes e CRM"""
    routes = [
        '/customers/',
        '/customers/rfm',
        '/customers/abc',
        '/customers/profiles',
        '/customers/birthdays',
        '/customers/nps'
    ]
    for r in routes:
        res = client.get(r)
        assert res.status_code == 200, f"Falha na rota {r}: status {res.status_code}"
        assert b'Clientes e CRM' in res.data or b'Clientes &amp; CRM' in res.data

def test_sector_finance_routes(client):
    """Testa todas as telas e abas do Setor 4: Financeiro e DRE"""
    routes = [
        '/finance/',
        '/finance/dre',
        '/finance/cash-flow',
        '/finance/aging',
        '/finance/cash-statement'
    ]
    for r in routes:
        res = client.get(r)
        assert res.status_code == 200, f"Falha na rota {r}: status {res.status_code}"
        assert b'Financeiro &amp; DRE' in res.data or b'Financeiro e DRE' in res.data or b'Financeiro & DRE' in res.data

def test_sector_exports(client):
    """Testa rotas de exportação dos setores"""
    export_routes = [
        ('/sales/export/excel', 'spreadsheetml'),
        ('/sales/export/pdf', 'pdf'),
        ('/products/export/excel', 'spreadsheetml'),
        ('/products/export/pdf', 'pdf'),
        ('/customers/export/excel', 'spreadsheetml'),
        ('/customers/export/pdf', 'pdf'),
        ('/finance/dre/export/excel', 'spreadsheetml'),
        ('/finance/dre/export/pdf', 'pdf'),
        ('/finance/cash-statement/export/excel', 'spreadsheetml'),
        ('/finance/cash-statement/export/pdf', 'pdf')
    ]
    for url, mime_substr in export_routes:
        res = client.get(url)
        assert res.status_code == 200, f"Falha na exportação {url}: status {res.status_code}"
        assert mime_substr in res.headers.get('Content-Type', '')

def test_order_detail_and_thermal_receipt_modal(client):
    """Testa se a tela de vendas possui a modal de cupom térmico e o endpoint JSON do pedido funciona"""
    # 1. Verifica se a página de Visão Geral de Vendas possui o botão e a modal
    res_page = client.get('/sales/')
    assert res_page.status_code == 200
    assert b'orderModalBackdrop' in res_page.data
    assert b'thermalReceiptPrintArea' in res_page.data
    assert b'Imprimir Cupom 78mm' in res_page.data or b'Imprimir Cupom T\xc3\xa9rmico (78mm)' in res_page.data

    # 2. Testa o endpoint JSON de um pedido existente
    from app.models.order import Order
    order = Order.query.first()
    if order:
        res_api = client.get(f'/sales/orders/{order.id}')
        assert res_api.status_code == 200
        data = res_api.get_json()
        assert data['id'] == order.id
        assert data['number'] == order.number
        assert 'customer' in data
        assert 'items' in data
        assert 'financial' in data
        assert 'total' in data['financial']


def test_sales_overview_search_filters(client):
    """Testa a barra de busca por nome do cliente, número do pedido e CPF em visão geral"""
    from app.models.order import Order
    from app.models.customer import Customer
    from app.database import db

    # 1. Verifica se a barra de busca está presente na tela
    res = client.get('/sales/')
    assert res.status_code == 200
    assert b'id="orderSearchInput"' in res.data
    assert b'Buscar por cliente, n\xc2\xba pedido ou CPF' in res.data

    # Cria pedido com cliente e documento se necessário para testar busca
    order = Order.query.first()
    if order and order.customer:
        cust = order.customer
        cust.document = "123.456.789-00"
        cust.name = "Cliente Teste BlingBI"
        db.session.commit()

        # Busca por número do pedido
        res_by_num = client.get(f'/sales/?q={order.number}')
        assert res_by_num.status_code == 200
        assert order.number.encode('utf-8') in res_by_num.data

        # Busca por nome do cliente
        res_by_name = client.get('/sales/?q=Cliente Teste')
        assert res_by_name.status_code == 200
        assert b'Cliente Teste BlingBI' in res_by_name.data

        # Busca por CPF formatado
        res_by_cpf = client.get('/sales/?q=123.456.789-00')
        assert res_by_cpf.status_code == 200
        assert b'123.456.789-00' in res_by_cpf.data

        # Busca por dígitos do CPF
        res_by_digits = client.get('/sales/?q=12345678900')
        assert res_by_digits.status_code == 200
        assert b'Cliente Teste BlingBI' in res_by_digits.data


def test_product_search_by_attributes_and_exports(client):
    """Testa a integração da busca geral de produtos por tamanho, cor e nome na aba Inventário e Catálogo e suas exportações"""
    # 1. Acesso à aba Inventário e Catálogo de Produtos
    res = client.get('/products/')
    assert res.status_code == 200
    assert b'Invent\xc3\xa1rio &amp; Cat\xc3\xa1logo' in res.data or b'Invent\xc3\xa1rio & Cat\xc3\xa1logo' in res.data
    assert b'id="prodSearchInput"' in res.data
    assert b'id="sizeSelect"' in res.data
    assert b'id="colorSelect"' in res.data
    assert b'Invent\xc3\xa1rio &amp; Cat\xc3\xa1logo de Produtos' in res.data or b'Invent\xc3\xa1rio & Cat\xc3\xa1logo de Produtos' in res.data

    # 2. Busca por termo de nome
    res_name = client.get('/products/?q=Vestido')
    assert res_name.status_code == 200

    # 3. Busca por tamanho
    res_size = client.get('/products/?size=M')
    assert res_size.status_code == 200

    # 4. Busca por cor
    res_color = client.get('/products/?color=Preto')
    assert res_color.status_code == 200

    # 5. Exportação Excel de Inventário & Catálogo
    res_excel = client.get('/products/export/excel?q=Vestido&size=M')
    assert res_excel.status_code == 200
    assert 'spreadsheetml' in res_excel.headers.get('Content-Type', '')

    # 6. Exportação PDF de Inventário & Catálogo
    res_pdf = client.get('/products/export/pdf?q=Vestido&size=M')
    assert res_pdf.status_code == 200
    assert 'pdf' in res_pdf.headers.get('Content-Type', '')


def test_customer_multi_attribute_filters_and_periods(client):
    """Testa a segmentação de clientes por múltiplos atributos estratégicos e períodos comerciais"""
    from app.models.customer import Customer

    # 1. Melhores Clientes (Mês)
    res_best = client.get('/customers/?filter_type=best_customers&period=month')
    assert res_best.status_code == 200
    assert b'Melhores Clientes' in res_best.data
    assert b'custSearchInput' in res_best.data

    # 2. Mais Produtos Comprados (Trimestre)
    res_prods = client.get('/customers/?filter_type=most_products&period=quarter')
    assert res_prods.status_code == 200
    assert b'Mais Produtos Comprados' in res_prods.data

    # 3. Clientes Última Compra (Semestre)
    res_last = client.get('/customers/?filter_type=last_purchase&period=semester')
    assert res_last.status_code == 200
    assert b'\xc3\x9altima Compra' in res_last.data or b'Ultima Compra' in res_last.data

    # 4. Clientes que não compram há mais tempo (Ano)
    res_inact = client.get('/customers/?filter_type=longest_inactive&period=year')
    assert res_inact.status_code == 200
    assert b'N\xc3\xa3o Compram H\xc3\xa1 Mais Tempo' in res_inact.data or b'Inativo' in res_inact.data

    # 5. Clientes de Consignado (Mês)
    res_consign = client.get('/customers/?filter_type=consignment&period=month')
    assert res_consign.status_code == 200
    assert b'Clientes de Consignado' in res_consign.data

    # 6. Período Personalizado / Selecionado
    res_custom = client.get('/customers/?filter_type=best_customers&period=custom&start_date=2026-01-01&end_date=2026-10-08')
    assert res_custom.status_code == 200

    # 7. Exportações com filtros
    res_excel = client.get('/customers/export/excel?filter_type=best_customers&period=quarter')
    assert res_excel.status_code == 200
    assert 'spreadsheetml' in res_excel.headers.get('Content-Type', '')

    res_pdf = client.get('/customers/export/pdf?filter_type=consignment&period=month')
    assert res_pdf.status_code == 200
    assert 'pdf' in res_pdf.headers.get('Content-Type', '')

    # 8. Endpoint de Detalhes do Cliente (JSON para Modal)
    cust = Customer.query.first()
    if cust:
        res_details = client.get(f'/customers/{cust.id}/details')
        assert res_details.status_code == 200
        data = res_details.get_json()
        assert data['id'] == cust.id
        assert data['name'] == cust.name
        assert 'orders' in data
        assert 'bags' in data


def test_cash_statement_and_daily_closing(client):
    """Testa a nova aba de Fechamento de Caixa e Extrato de Movimentação Financeira e registro de sangria"""
    # 1. Carregamento da página principal de Fechamento de Caixa
    res = client.get('/finance/cash-statement')
    assert res.status_code == 200
    assert b'Saldo Inicial' in res.data or b'Saldo Inicial (Abertura)' in res.data
    assert b'Total Entradas' in res.data
    assert b'Total Sa\xc3\xaddas' in res.data or b'Total Saidas' in res.data
    assert b'Extrato Cronol\xc3\xb3gico' in res.data
    assert b'Hist\xc3\xb3rico Consolidado de Fechamentos Di\xc3\xa1rios' in res.data

    # 2. Filtros por período e tipo
    res_inflow = client.get('/finance/cash-statement?type=inflow&period=month')
    assert res_inflow.status_code == 200

    res_outflow = client.get('/finance/cash-statement?type=outflow&period=month')
    assert res_outflow.status_code == 200

    # 3. Registro de Movimentação Avulsa / Sangria de Caixa
    res_entry = client.post('/finance/cash-statement/entry', data={
        'entry_type': 'PAGAR',
        'description': 'Sangria Teste para Depósito',
        'amount': '350.00',
        'entity_name': 'Banco do Brasil',
        'category': 'Sangria',
        'payment_method': 'Dinheiro',
        'date': '2026-10-08'
    }, follow_redirects=True)
    assert res_entry.status_code == 200
    assert b'Sangria Teste para Dep\xc3\xb3sito' in res_entry.data or b'350' in res_entry.data

    # 4. Exportação Excel do Extrato
    res_excel = client.get('/finance/cash-statement/export/excel?period=month')
    assert res_excel.status_code == 200
    assert 'spreadsheetml' in res_excel.headers.get('Content-Type', '')

    # 5. Exportação PDF do Extrato
    res_pdf = client.get('/finance/cash-statement/export/pdf?period=month')
    assert res_pdf.status_code == 200
    assert 'pdf' in res_pdf.headers.get('Content-Type', '')





