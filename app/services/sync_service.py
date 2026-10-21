import logging
import time
from datetime import datetime
from dateutil import parser as date_parser
from app.database import db
from app.models.customer import Customer
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.financial import FinancialEntry
from app.models.setting import Setting
from app.services.bling_api import BlingApiClient

logger = logging.getLogger(__name__)

class SyncService:
    @staticmethod
    def sync_selected(options=None):
        """
        Executa sincronização modular baseada nas caixas de seleção do usuário.
        options: dict com chaves booleanas:
          - customers (default True)
          - products (default True)
          - orders (default True)
          - receivables (default True)
          - payables (default True)
        """
        if options is None:
            options = {
                'customers': True,
                'products': True,
                'orders': True,
                'receivables': True,
                'payables': True
            }

        client = BlingApiClient()
        if not client.is_configured():
            return False, "API do Bling não configurada. Conecte sua conta em Configurações."

        # Testa conexão
        conn_ok, conn_msg = client.test_connection()
        if not conn_ok:
            return False, f"Falha na autenticação com a API do Bling: {conn_msg}"

        summary = {}
        errors = []

        try:
            # 1. Clientes
            if options.get('customers', True):
                try:
                    logger.info("Sincronizando clientes...")
                    summary['customers'] = SyncService.sync_customers(client)
                except Exception as e:
                    logger.error(f"Erro ao sincronizar clientes: {e}")
                    errors.append(f"Clientes: {str(e)}")
                    db.session.rollback()

            # 2. Produtos & Estoques Físicos
            if options.get('products', True):
                try:
                    logger.info("Sincronizando produtos...")
                    summary['products'] = SyncService.sync_products(client)
                    logger.info("Sincronizando saldos reais de estoque...")
                    summary['stocks'] = SyncService.sync_stocks(client)
                except Exception as e:
                    logger.error(f"Erro ao sincronizar produtos/estoques: {e}")
                    errors.append(f"Produtos/Estoques: {str(e)}")
                    db.session.rollback()

            # 3. Pedidos de Venda
            if options.get('orders', True):
                try:
                    logger.info("Sincronizando pedidos...")
                    summary['orders'] = SyncService.sync_orders(client)
                    # Amarra retrospectivamente quaisquer itens que tenham ficado sem vínculo
                    SyncService.link_orphan_order_items()
                except Exception as e:
                    logger.error(f"Erro ao sincronizar pedidos: {e}")
                    errors.append(f"Pedidos: {str(e)}")
                    db.session.rollback()

            # 4. Contas a Receber
            if options.get('receivables', True):
                try:
                    logger.info("Sincronizando contas a receber...")
                    summary['receivables'] = SyncService.sync_receivables(client)
                except Exception as e:
                    logger.error(f"Erro ao sincronizar contas a receber: {e}")
                    errors.append(f"Contas a Receber: {str(e)}")
                    db.session.rollback()

            # 5. Contas a Pagar
            if options.get('payables', True):
                try:
                    logger.info("Sincronizando contas a pagar...")
                    summary['payables'] = SyncService.sync_payables(client)
                except Exception as e:
                    logger.error(f"Erro ao sincronizar contas a pagar: {e}")
                    errors.append(f"Contas a Pagar: {str(e)}")
                    db.session.rollback()

            # Desativa flag de demonstração
            Setting.set('demo_mode_active', '0')
            Setting.set('last_sync_date', datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S'))
            
            if errors:
                Setting.set('last_sync_status', f"Parcial com avisos ({', '.join(errors)})")
            else:
                total_items = sum(v for k, v in summary.items() if isinstance(v, int))
                Setting.set('last_sync_status', f"Sucesso ({total_items} registros atualizados)")

            return True, summary
        except Exception as e:
            logger.error(f"Erro geral no sync_selected: {e}", exc_info=True)
            db.session.rollback()
            Setting.set('last_sync_status', f"Erro: {str(e)}")
            return False, str(e)

    @staticmethod
    def sync_all():
        return SyncService.sync_selected({
            'customers': True,
            'products': True,
            'orders': True,
            'receivables': True,
            'payables': True
        })

    @staticmethod
    def sync_customers(client=None):
        client = client or BlingApiClient()
        page = 1
        count = 0
        while True:
            items = client.get_contacts(page=page, limit=100)
            if not items:
                break
            for item in items:
                try:
                    b_id = item.get('id')
                    if not b_id:
                        continue
                    cust = Customer.query.filter_by(bling_id=b_id).first()
                    if not cust:
                        cust = Customer(bling_id=b_id)
                        db.session.add(cust)
                    
                    cust.name = item.get('nome', 'Sem Nome')
                    cust.document = item.get('numeroDocumento')
                    cust.person_type = item.get('tipo', 'F')
                    cust.email = item.get('email')
                    cust.phone = item.get('telefone') or item.get('celular')
                    
                    address = item.get('endereco', {}) or {}
                    if isinstance(address, dict):
                        cust.city = address.get('municipio')
                        cust.state = address.get('uf')
                    count += 1
                except Exception as item_err:
                    logger.warning(f"Erro no contato {item.get('id')}: {item_err}")
            
            try:
                db.session.commit()
            except Exception as commit_err:
                logger.error(f"Erro no commit da página {page} de clientes: {commit_err}")
                db.session.rollback()
                raise commit_err

            if len(items) < 100:
                break
            page += 1
            time.sleep(0.3)
        return count

    @staticmethod
    def _save_or_update_product(item):
        """Salva ou atualiza um produto a partir de um registro retornado pela API v3 do Bling."""
        b_id = item.get('id')
        if not b_id:
            return None
        prod = Product.query.filter_by(bling_id=b_id).first()
        if not prod:
            prod = Product(bling_id=b_id)
            db.session.add(prod)

        prod.name = item.get('nome', 'Produto sem nome')
        prod.sku = item.get('codigo')
        prod.price = float(item.get('preco', 0.0) or 0.0)
        prod.cost = float(item.get('precoCusto', 0.0) or 0.0)

        # Se a listagem trouxe saldo embutido, armazena como estimativa inicial
        # (o saldo físico oficial consolidado de depósitos é sincronizado em sync_stocks)
        stock_data = item.get('estoque', {}) or {}
        if isinstance(stock_data, dict):
            sf = stock_data.get('saldoFisico') if stock_data.get('saldoFisico') is not None else stock_data.get('saldoFisicoTotal')
            if sf is not None:
                prod.stock = float(sf or 0.0)

        prod.format = item.get('formato')
        prod.status = item.get('situacao', 'A')

        from app.services.product_attributes import parse_product_attributes
        s_det, c_det = parse_product_attributes(prod.name)
        if s_det and not prod.size:
            prod.size = s_det
        if c_det and not prod.color:
            prod.color = c_det

        return prod

    @staticmethod
    def sync_products(client=None):
        client = client or BlingApiClient()
        page = 1
        count = 0
        has_variations = False

        while True:
            items = client.get_products(page=page, limit=100)
            if not items:
                break
            for item in items:
                try:
                    prod = SyncService._save_or_update_product(item)
                    if prod:
                        count += 1
                        if prod.format == 'V':
                            has_variations = True

                    # Se o produto com variações já vier com a lista de variações embutida
                    for v_item in item.get('variacoes', []):
                        if isinstance(v_item, dict) and v_item.get('id'):
                            v_prod = SyncService._save_or_update_product(v_item)
                            if v_prod:
                                count += 1
                except Exception as item_err:
                    logger.warning(f"Erro no produto {item.get('id')}: {item_err}")

            try:
                db.session.commit()
            except Exception as commit_err:
                logger.error(f"Erro no commit da página {page} de produtos: {commit_err}")
                db.session.rollback()
                raise commit_err

            if len(items) < 100:
                break
            page += 1
            time.sleep(0.3)

        # Se houver produtos com variações, busca explicitamente produtos do tipo 'V'
        # para garantir que todas as variações/grades tenham SKU e ID cadastrados
        if has_variations:
            try:
                var_page = 1
                while True:
                    var_items = client.get_products(page=var_page, limit=100, product_type='V')
                    if not var_items:
                        break
                    for v_item in var_items:
                        try:
                            v_prod = SyncService._save_or_update_product(v_item)
                            if v_prod:
                                count += 1
                        except Exception as v_err:
                            logger.warning(f"Erro ao salvar variação {v_item.get('id')}: {v_err}")

                    try:
                        db.session.commit()
                    except Exception as commit_err:
                        db.session.rollback()
                        break

                    if len(var_items) < 100:
                        break
                    var_page += 1
                    time.sleep(0.3)
            except Exception as var_sync_err:
                logger.info(f"Nota na busca de variações tipo='V': {var_sync_err}")

        # Sincroniza os saldos reais de estoque após cadastrar os produtos
        try:
            SyncService.sync_stocks(client)
        except Exception as stock_err:
            logger.warning(f"Aviso ao sincronizar saldos de estoque após sync_products: {stock_err}")

        return count

    @staticmethod
    def sync_stocks(client=None):
        """
        Sincroniza os saldos de estoque físico de todos os produtos a partir do endpoint
        oficial da API v3 do Bling (/estoques/saldos).
        
        Boas práticas Bling v3:
        1. Consulta em lotes (chunks) de até 100 IDs via parâmetro idsProdutos[]
        2. Agrega os saldos somando todos os depósitos retornados para cada produto.
        3. Atualiza o campo Product.stock com o saldoFisico real total consolidado.
        """
        client = client or BlingApiClient()
        products = Product.query.all()
        if not products:
            return 0

        prod_map_bling = {p.bling_id: p for p in products if p.bling_id}
        prod_map_sku = {p.sku.strip().upper(): p for p in products if p.sku}
        bling_ids = list(prod_map_bling.keys())
        count = 0

        if bling_ids:
            chunk_size = 100
            for i in range(0, len(bling_ids), chunk_size):
                chunk = bling_ids[i:i + chunk_size]
                items = client.get_stock_balances(product_ids=chunk)
                if not items:
                    continue

                # Acumula saldos físicos por ID de produto somando todos os depósitos
                stock_by_bling = {}
                for item in items:
                    p_info = item.get('produto', {}) or {}
                    b_id = p_info.get('id')
                    if not b_id:
                        continue

                    # Saldo físico real do depósito (ou fallback para saldoFisicoTotal)
                    sf = float(item.get('saldoFisico') if item.get('saldoFisico') is not None else item.get('saldoFisicoTotal', 0.0) or 0.0)
                    stock_by_bling[b_id] = stock_by_bling.get(b_id, 0.0) + sf

                # Atualiza os produtos pertencentes a este lote
                for b_id in chunk:
                    prod = prod_map_bling.get(b_id)
                    if prod:
                        if b_id in stock_by_bling:
                            prod.stock = float(stock_by_bling[b_id])
                        else:
                            # Se não retornou nenhum saldo para o produto, estoque é zero
                            prod.stock = 0.0
                        count += 1

                try:
                    db.session.commit()
                except Exception as commit_err:
                    logger.error(f"Erro no commit de saldos de estoque (lote {i // chunk_size + 1}): {commit_err}")
                    db.session.rollback()
                    raise commit_err

                time.sleep(0.2)
        else:
            # Fallback caso não haja produtos com bling_id mapeados
            page = 1
            while True:
                items = client.get_stock_balances(page=page, limit=100)
                if not items:
                    break

                for item in items:
                    try:
                        p_info = item.get('produto', {}) or {}
                        b_id = p_info.get('id')
                        sku = item.get('codigo') or p_info.get('codigo')

                        prod = None
                        if b_id:
                            prod = prod_map_bling.get(b_id)
                        if not prod and sku:
                            prod = prod_map_sku.get(sku.strip().upper())

                        if prod:
                            saldo = float(item.get('saldoFisico') if item.get('saldoFisico') is not None else item.get('saldoFisicoTotal', 0.0) or 0.0)
                            prod.stock = saldo
                            count += 1
                    except Exception as stock_err:
                        logger.warning(f"Erro ao processar saldo de estoque do item {item}: {stock_err}")

                try:
                    db.session.commit()
                except Exception as commit_err:
                    logger.error(f"Erro no commit de saldos de estoque página {page}: {commit_err}")
                    db.session.rollback()
                    raise commit_err

                if len(items) < 100:
                    break
                page += 1
                time.sleep(0.3)

        logger.info(f"Saldos reais de estoque sincronizados com sucesso para {count} produtos.")
        return count

    @staticmethod
    def link_orphan_order_items():
        """
        Amarra retrospectivamente itens de pedido que estejam com product_id IS NULL
        através de correspondência inteligente por SKU ou Nome do produto.
        """
        orphans = OrderItem.query.filter(OrderItem.product_id.is_(None)).all()
        if not orphans:
            return 0

        products = Product.query.all()
        sku_map = {p.sku.strip().upper(): p for p in products if p.sku}
        name_map = {p.name.strip().upper(): p for p in products if p.name}

        linked = 0
        for item in orphans:
            p = None
            if item.sku and item.sku.strip().upper() in sku_map:
                p = sku_map[item.sku.strip().upper()]
            elif item.product_name and item.product_name.strip().upper() in name_map:
                p = name_map[item.product_name.strip().upper()]

            if p:
                item.product_id = p.id
                if not item.cost_price or item.cost_price == 0:
                    item.cost_price = p.cost
                linked += 1

        if linked > 0:
            try:
                db.session.flush()
            except Exception:
                pass
            logger.info(f"Auto-correção: {linked} itens de pedido órfãos foram amarrados aos seus produtos.")
        return linked

    @staticmethod
    def sync_orders(client=None):
        client = client or BlingApiClient()
        page = 1
        count = 0

        # Pré-carrega mapas em memória para evitar centenas de queries repetidas
        # e prevenir autoflush prematuro de deleção de itens no SQLite
        try:
            products_all = Product.query.all()
            product_map = {p.bling_id: p for p in products_all if p.bling_id}
            product_sku_map = {p.sku.strip().upper(): p for p in products_all if p.sku}
            product_name_map = {p.name.strip().upper(): p for p in products_all if p.name}
            customer_map = {c.bling_id: c.id for c in Customer.query.all() if c.bling_id}
            seller_map = {}
            try:
                sellers_res = client.request('GET', '/vendedores?limite=100')
                if sellers_res and sellers_res.status_code == 200:
                    for v in sellers_res.json().get('data', []):
                        v_id = v.get('id')
                        v_name = v.get('contato', {}).get('nome') or v.get('nome')
                        if v_id and v_name:
                            seller_map[v_id] = v_name
            except Exception as s_err:
                logger.warning(f"Aviso ao consultar vendedores no Bling: {s_err}")
        except Exception as pre_err:
            logger.warning(f"Aviso no pré-carregamento para sync de pedidos: {pre_err}")
            db.session.rollback()
            product_map = {}
            product_sku_map = {}
            product_name_map = {}
            customer_map = {}
            seller_map = {}

        while True:
            items = client.get_orders(page=page, limit=100)
            if not items:
                break
            for item in items:
                try:
                    b_id = item.get('id')
                    if not b_id:
                        continue

                    order = Order.query.filter_by(bling_id=b_id).first()
                    if not order:
                        order = Order(bling_id=b_id)
                        db.session.add(order)
                    
                    order.number = str(item.get('numero', b_id))
                    data_str = item.get('data')
                    if data_str:
                        try:
                            order.order_date = date_parser.parse(str(data_str)[:10]).date()
                        except Exception:
                            pass
                    
                    order.total = float(item.get('total', 0.0) or 0.0)
                    
                    desc_obj = item.get('desconto')
                    if isinstance(desc_obj, dict):
                        order.discount = float(desc_obj.get('valor', 0.0) or 0.0)
                    elif isinstance(desc_obj, (int, float)):
                        order.discount = float(desc_obj)

                    transp_obj = item.get('transporte')
                    if isinstance(transp_obj, dict):
                        order.shipping = float(transp_obj.get('fretePorConta', 0.0) or 0.0)

                    situacao = item.get('situacao')
                    status_nome = 'Atendido'
                    if isinstance(situacao, dict):
                        status_nome = situacao.get('nome', 'Atendido')
                    elif isinstance(situacao, int):
                        status_map = {6: 'Em aberto', 9: 'Atendido', 12: 'Cancelado'}
                        status_nome = status_map.get(situacao, 'Atendido')
                    order.status = status_nome
                    
                    loja = item.get('loja')
                    order.channel = loja.get('nome', 'Loja Virtual') if isinstance(loja, dict) else 'Loja Virtual'

                    # Vendedor devidamente cadastrado no Bling (sem inventar)
                    vendedor = item.get('vendedor')
                    seller_nome = None
                    if isinstance(vendedor, dict):
                        v_id = vendedor.get('id')
                        seller_nome = vendedor.get('nome') or seller_map.get(v_id)
                        if not seller_nome and vendedor.get('contato'):
                            seller_nome = vendedor.get('contato', {}).get('nome')
                    elif isinstance(vendedor, str):
                        seller_nome = vendedor
                    order.seller_name = seller_nome

                    # Observações do pedido
                    notes_txt = item.get('observacoes') or item.get('observacaoInterna')
                    if notes_txt:
                        order.notes = str(notes_txt)

                    # Forma de pagamento
                    pay_method = 'Cartão de Crédito'
                    parcelas = item.get('parcelas', [])
                    if parcelas and isinstance(parcelas, list) and len(parcelas) > 0:
                        fp = parcelas[0].get('formaPagamento', {})
                        if isinstance(fp, dict):
                            pay_method = fp.get('descricao') or fp.get('nome') or pay_method
                        elif isinstance(fp, str):
                            pay_method = fp
                    else:
                        fp_root = item.get('formaPagamento')
                        if isinstance(fp_root, dict):
                            pay_method = fp_root.get('descricao') or fp_root.get('nome') or pay_method
                        elif isinstance(fp_root, str):
                            pay_method = fp_root

                    # Detecção inteligente de Consignado nas observações se não vier explícito
                    full_obs = f"{order.notes or ''}".lower()
                    if 'consignad' in full_obs or 'condicional' in full_obs or 'mala' in full_obs:
                        pay_method = 'Consignado'

                    order.payment_method = pay_method
                    
                    contato = item.get('contato')
                    if isinstance(contato, dict) and contato.get('id'):
                        c_id = contato.get('id')
                        if c_id in customer_map:
                            order.customer_id = customer_map[c_id]
                        else:
                            cust = Customer.query.filter_by(bling_id=c_id).first()
                            if cust:
                                customer_map[c_id] = cust.id
                                order.customer_id = cust.id

                    # Itens do pedido: busca se não vierem na listagem
                    itens_data = item.get('itens', [])
                    if not itens_data:
                        time.sleep(0.2)
                        order_details = client.get_order_details(b_id)
                        if order_details and isinstance(order_details, dict):
                            itens_data = order_details.get('itens', [])

                    if itens_data:
                        # no_autoflush impede que deleções em cascata sejam disparadas
                        # prematuramente durante buscas ou adições no SQLite
                        with db.session.no_autoflush:
                            order.items.clear()
                            for it in itens_data:
                                prod_dict = it.get('produto', {}) if isinstance(it.get('produto'), dict) else {}
                                prod_bling_id = prod_dict.get('id')
                                
                                local_prod = product_map.get(prod_bling_id) if prod_bling_id else None
                                if prod_bling_id and not local_prod:
                                    local_prod = Product.query.filter_by(bling_id=prod_bling_id).first()
                                    if local_prod:
                                        product_map[prod_bling_id] = local_prod

                                # Fallback robusto por SKU ou Nome
                                if not local_prod and it.get('codigo'):
                                    sku_code = it.get('codigo').strip().upper()
                                    local_prod = product_sku_map.get(sku_code)
                                if not local_prod and it.get('descricao'):
                                    desc_name = it.get('descricao').strip().upper()
                                    local_prod = product_name_map.get(desc_name)
                                
                                qty = float(it.get('quantidade', 1.0) or 1.0)
                                u_price = float(it.get('valor', 0.0) or 0.0)
                                
                                order_item = OrderItem(
                                    order=order,
                                    product_id=local_prod.id if local_prod else None,
                                    product_name=it.get('descricao', local_prod.name if local_prod else 'Item'),
                                    sku=it.get('codigo', local_prod.sku if local_prod else None),
                                    quantity=qty,
                                    unit_price=u_price,
                                    cost_price=local_prod.cost if local_prod else 0.0,
                                    total_price=qty * u_price
                                )
                                db.session.add(order_item)

                    db.session.commit()
                    count += 1
                except Exception as order_err:
                    logger.warning(f"Erro no pedido {item.get('id')}: {order_err}")
                    db.session.rollback()

            if len(items) < 100:
                break
            page += 1
            time.sleep(0.3)
        return count

    @staticmethod
    def sync_receivables(client=None):
        client = client or BlingApiClient()
        count = 0
        try:
            recs = client.get_receivables(page=1, limit=100)
            if not recs:
                return 0

            for item in recs:
                try:
                    b_id = item.get('id')
                    if not b_id:
                        continue
                    entry = FinancialEntry.query.filter_by(bling_id=b_id, entry_type='RECEBER').first()
                    if not entry:
                        entry = FinancialEntry(bling_id=b_id, entry_type='RECEBER')
                        db.session.add(entry)
                    
                    entry.description = item.get('historico') or 'Recebimento de Venda'
                    entry.amount = float(item.get('valor', 0.0) or 0.0)
                    
                    contato_info = item.get('contato', {})
                    entry.entity_name = contato_info.get('nome') if isinstance(contato_info, dict) else 'Cliente'

                    venc = item.get('vencimento')
                    if venc:
                        try:
                            entry.due_date = date_parser.parse(str(venc)[:10]).date()
                        except Exception:
                            pass
                    
                    emissao = item.get('dataEmissao')
                    if emissao:
                        try:
                            entry.issue_date = date_parser.parse(str(emissao)[:10]).date()
                        except Exception:
                            pass
                    
                    situacao = item.get('situacao')
                    entry.status = 'Pago' if situacao == 2 else ('Cancelado' if situacao == 3 else 'Pendente')
                    count += 1
                except Exception as rec_err:
                    logger.warning(f"Erro em conta a receber {item.get('id')}: {rec_err}")

            db.session.commit()
        except Exception as e:
            logger.error(f"Erro ao buscar contas a receber: {e}")
            db.session.rollback()
            raise e
        return count

    @staticmethod
    def sync_payables(client=None):
        client = client or BlingApiClient()
        count = 0
        try:
            pays = client.get_payables(page=1, limit=100)
            if not pays:
                return 0

            for item in pays:
                try:
                    b_id = item.get('id')
                    if not b_id:
                        continue
                    entry = FinancialEntry.query.filter_by(bling_id=b_id, entry_type='PAGAR').first()
                    if not entry:
                        entry = FinancialEntry(bling_id=b_id, entry_type='PAGAR')
                        db.session.add(entry)
                    
                    entry.description = item.get('historico') or 'Pagamento de Despesa'
                    entry.amount = float(item.get('valor', 0.0) or 0.0)
                    
                    fornecedor_info = item.get('contato', {}) or item.get('fornecedor', {})
                    entry.entity_name = fornecedor_info.get('nome') if isinstance(fornecedor_info, dict) else 'Fornecedor'

                    venc = item.get('vencimento')
                    if venc:
                        try:
                            entry.due_date = date_parser.parse(str(venc)[:10]).date()
                        except Exception:
                            pass
                    
                    emissao = item.get('dataEmissao')
                    if emissao:
                        try:
                            entry.issue_date = date_parser.parse(str(emissao)[:10]).date()
                        except Exception:
                            pass
                    
                    situacao = item.get('situacao')
                    entry.status = 'Pago' if situacao == 2 else ('Cancelado' if situacao == 3 else 'Pendente')
                    count += 1
                except Exception as pay_err:
                    logger.warning(f"Erro em conta a pagar {item.get('id')}: {pay_err}")

            db.session.commit()
        except Exception as e:
            logger.error(f"Erro ao buscar contas a pagar: {e}")
            db.session.rollback()
            raise e
        return count
