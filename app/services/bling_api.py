import base64
import time
import requests
import logging
from datetime import datetime
from app.models.setting import Setting

logger = logging.getLogger(__name__)

class BlingApiClient:
    BASE_URL = "https://api.bling.com.br/Api/v3"
    TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"
    AUTHORIZE_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"

    def __init__(self):
        self.client_id = Setting.get('bling_client_id', '')
        self.client_secret = Setting.get('bling_client_secret', '')
        self.access_token = Setting.get('bling_access_token', '')
        self.refresh_token = Setting.get('bling_refresh_token', '')

    def is_configured(self):
        token = (Setting.get('bling_access_token', '') or '').strip()
        refresh = (Setting.get('bling_refresh_token', '') or '').strip()
        cid = (Setting.get('bling_client_id', '') or '').strip()
        csecret = (Setting.get('bling_client_secret', '') or '').strip()
        return bool(token or refresh or (cid and csecret))

    def get_authorization_url(self, redirect_uri=None, state='bling_bi_auth'):
        """Gera a URL oficial do Bling para autorização OAuth 2.0."""
        cid = Setting.get('bling_client_id', self.client_id).strip()
        if not cid:
            return None
        
        # Constrói a URL de autorização oficial do Bling
        url = f"{self.AUTHORIZE_URL}?response_type=code&client_id={cid}&state={state}"
        if redirect_uri:
            url += f"&redirect_uri={redirect_uri}"
        return url

    def exchange_code_for_token(self, code, redirect_uri=None):
        """Troca o authorization code pelo access_token e refresh_token."""
        cid = Setting.get('bling_client_id', self.client_id).strip()
        csec = Setting.get('bling_client_secret', self.client_secret).strip()
        if not cid or not csec:
            return False, "Client ID ou Client Secret não configurados."

        credentials = f"{cid}:{csec}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {encoded_creds}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '1.0'
        }

        # Tentativa 1: Formato padrão oficial do Bling v3 (grant_type e code)
        data = {
            'grant_type': 'authorization_code',
            'code': code.strip()
        }

        # URLs possíveis para o token endpoint (www e api)
        endpoints = [
            "https://www.bling.com.br/Api/v3/oauth/token",
            "https://api.bling.com.br/Api/v3/oauth/token"
        ]

        last_error = ""

        # Testamos primeiro sem redirect_uri no body (conforme documentação do Bling)
        # e, se falhar, tentamos com redirect_uri
        payloads_to_try = [data]
        if redirect_uri:
            payloads_to_try.append({
                'grant_type': 'authorization_code',
                'code': code.strip(),
                'redirect_uri': redirect_uri
            })

        for payload in payloads_to_try:
            for token_url in endpoints:
                try:
                    logger.info(f"Tentando trocar token em {token_url} (com redirect_uri={bool('redirect_uri' in payload)})...")
                    response = requests.post(token_url, headers=headers, data=payload, timeout=15)
                    
                    if response.status_code == 200:
                        json_resp = response.json()
                        new_access_token = json_resp.get('access_token')
                        new_refresh_token = json_resp.get('refresh_token')

                        Setting.set('bling_access_token', new_access_token)
                        Setting.set('bling_refresh_token', new_refresh_token)
                        Setting.set('bling_token_updated_at', datetime.utcnow().isoformat())
                        Setting.set('bling_status', 'Conectado')

                        self.access_token = new_access_token
                        self.refresh_token = new_refresh_token
                        logger.info("Token gerado com sucesso!")
                        return True, "Autenticação Bling concluída com sucesso!"
                    else:
                        resp_text = response.text
                        try:
                            resp_json = response.json()
                            resp_text = resp_json.get('error', {}).get('description', resp_text)
                        except Exception:
                            pass
                        last_error = f"HTTP {response.status_code}: {resp_text}"
                        logger.warning(f"Resposta de erro do Bling: {last_error}")
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"Exceção ao trocar token no Bling ({token_url}): {e}")

        return False, f"Falha na autorização: {last_error}"

    def _get_headers(self):
        token = (self.access_token or '').strip()
        if not token:
            token = (Setting.get('bling_access_token', '') or '').strip()
        if not token and (Setting.get('bling_refresh_token', '') or '').strip():
            self.refresh_access_token()
            token = (Setting.get('bling_access_token', '') or '').strip()
        self.access_token = token
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def refresh_access_token(self):
        """Renova o access_token usando o refresh_token."""
        refresh_token = Setting.get('bling_refresh_token', self.refresh_token).strip()
        client_id = Setting.get('bling_client_id', self.client_id).strip()
        client_secret = Setting.get('bling_client_secret', self.client_secret).strip()

        if not refresh_token or not client_id or not client_secret:
            return False, "Credenciais incompletas para renovar token."

        credentials = f"{client_id}:{client_secret}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {encoded_creds}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '1.0'
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }

        endpoints = [
            "https://www.bling.com.br/Api/v3/oauth/token",
            "https://api.bling.com.br/Api/v3/oauth/token"
        ]

        for token_url in endpoints:
            try:
                response = requests.post(token_url, headers=headers, data=data, timeout=15)
                if response.status_code == 200:
                    payload = response.json()
                    new_access_token = payload.get('access_token')
                    new_refresh_token = payload.get('refresh_token', refresh_token)
                    
                    Setting.set('bling_access_token', new_access_token)
                    Setting.set('bling_refresh_token', new_refresh_token)
                    Setting.set('bling_token_updated_at', datetime.utcnow().isoformat())
                    self.access_token = new_access_token
                    self.refresh_token = new_refresh_token
                    return True, "Token renovado com sucesso."
            except Exception as e:
                logger.error(f"Erro ao renovar token Bling ({token_url}): {e}")

        return False, "Falha ao renovar token Bling."

    def request(self, method, endpoint, params=None, json_data=None, json=None, retries=2, **kwargs):
        """Executa requisição com tratamento de rate limit, renovação de token e backoff progressivo."""
        url = f"{self.BASE_URL}{endpoint}" if not endpoint.startswith('http') else endpoint
        headers = self._get_headers()
        body = json if json is not None else json_data

        req_timeout = kwargs.pop('timeout', 30)
        last_response = None

        for attempt in range(retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body,
                    timeout=req_timeout,
                    **kwargs
                )
                last_response = response

                # Token Expirado (401)
                if response.status_code == 401 and attempt < retries:
                    success, _ = self.refresh_access_token()
                    if success:
                        headers = self._get_headers()
                        continue

                # Rate Limiting (429 - Limite do Bling: 3 req/s)
                if response.status_code == 429:
                    if attempt < retries:
                        backoff = 1.8 * (attempt + 1)
                        logger.warning(
                            f"[BlingApiClient] Rate limit 429 em {method} {endpoint}. "
                            f"Aguardando {backoff:.1f}s antes da tentativa {attempt + 2}/{retries + 1}..."
                        )
                        time.sleep(backoff)
                        continue
                    else:
                        logger.warning(
                            f"[BlingApiClient] Rate limit 429 persistiu após {retries + 1} tentativas em {method} {endpoint}."
                        )
                        return response

                return response
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.error(f"[BlingApiClient] Conexão/Timeout em {method} {endpoint} (tentativa {attempt + 1}/{retries + 1}): {e}")
                if attempt == retries:
                    raise e
                time.sleep(1.5)
            except requests.RequestException as e:
                logger.error(f"[BlingApiClient] Erro na requisição Bling API ({method} {endpoint}): {e}")
                if attempt == retries:
                    raise e
                time.sleep(1)

        return last_response

    def test_connection(self):
        """Verifica se a conexão com a API Bling v3 está operando perfeitamente."""
        token = (Setting.get('bling_access_token', '') or '').strip()
        if not token:
            # Tenta renovar usando o refresh_token se disponível
            refreshed, ref_msg = self.refresh_access_token()
            if refreshed:
                token = (Setting.get('bling_access_token', '') or '').strip()
            else:
                return False, f"Nenhum Access Token configurado e não foi possível renovar: {ref_msg}"

        try:
            resp = self.request('GET', '/contatos', params={'limite': 1})
            if resp and resp.status_code == 200:
                return True, "✅ Conexão com a API Bling v3 estabelecida com sucesso!"
            elif resp and resp.status_code == 401:
                # Tenta renovar uma vez se deu 401
                refreshed, _ = self.refresh_access_token()
                if refreshed:
                    retry_resp = self.request('GET', '/contatos', params={'limite': 1})
                    if retry_resp and retry_resp.status_code == 200:
                        return True, "✅ Conexão com a API Bling v3 restabelecida com sucesso após renovar o token!"
                return False, "❌ Token inválido ou expirado. Clique em 'Conectar com Bling' para autorizar."
            elif resp:
                err_text = resp.text
                try:
                    err_json = resp.json()
                    err_text = err_json.get('error', {}).get('description', err_text)
                except Exception:
                    pass
                return False, f"Erro na API Bling (HTTP {resp.status_code}): {err_text[:100]}"
            return False, "Sem resposta da API Bling."
        except Exception as e:
            return False, f"Exceção ao conectar com a API Bling: {str(e)}"

    def get_contacts(self, page=1, limit=100):
        resp = self.request('GET', '/contatos', params={'pagina': page, 'limite': limit})
        if resp and resp.status_code == 200:
            return resp.json().get('data', [])
        return []

    def get_contact(self, contact_id: int):
        """Consulta um contato específico no Bling ERP (GET /contatos/{id})."""
        try:
            resp = self.request('GET', f'/contatos/{contact_id}')
            if resp and resp.status_code == 200:
                return resp.json().get('data', {})
        except Exception as e:
            logger.error(f"[BlingApiClient] Erro ao consultar contato {contact_id}: {e}")
        return None

    def get_products(self, page=1, limit=100, code=None, product_type=None, criteria=None):
        """
        Lista produtos da API v3 do Bling (/produtos) com suporte a paginação e filtros.
        - page: página da consulta (padrão: 1)
        - limit: registros por página (máx: 100)
        - code: SKU / código do item (filtro exato)
        - product_type: tipo do produto ('P' para simples, 'V' para variação, 'C' para composição)
        - criteria: critério de ordenação / filtro por data
        """
        params = {'pagina': page, 'limite': limit}
        if code:
            params['codigo'] = code
        if product_type:
            params['tipo'] = product_type
        if criteria:
            params['criterio'] = criteria
        resp = self.request('GET', '/produtos', params=params)
        if resp and resp.status_code == 200:
            return resp.json().get('data', [])
        return []

    def get_product_by_id(self, product_id):
        """Busca os detalhes completos de um produto específico por ID numérico do Bling."""
        resp = self.request('GET', f'/produtos/{product_id}')
        if resp and resp.status_code == 200:
            return resp.json().get('data', {})
        return {}

    def get_product_by_sku(self, sku):
        """Localiza um produto no Bling a partir do seu código / SKU."""
        items = self.get_products(code=sku, limit=1)
        return items[0] if items else None

    def get_orders(self, page=1, limit=100, date_from=None):
        params = {'pagina': page, 'limite': limit}
        if date_from:
            params['dataInicial'] = date_from
        resp = self.request('GET', '/pedidos/vendas', params=params)
        if resp and resp.status_code == 200:
            return resp.json().get('data', [])
        return []

    def get_order_details(self, order_id):
        """Busca o detalhe completo do pedido, incluindo itens de produtos."""
        resp = self.request('GET', f'/pedidos/vendas/{order_id}')
        if resp and resp.status_code == 200:
            return resp.json().get('data', {})
        return {}

    def get_receivables(self, page=1, limit=100):
        try:
            resp = self.request('GET', '/contas/receber', params={'pagina': page, 'limite': limit})
            if not resp or resp.status_code == 404:
                resp = self.request('GET', '/contas-receber', params={'pagina': page, 'limite': limit})
            if resp and resp.status_code == 200:
                return resp.json().get('data', [])
            elif resp and resp.status_code == 404:
                return []
            logger.error(f"[BlingApiClient] Falha ao consultar contas a receber (página {page}): status {getattr(resp, 'status_code', None)}")
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao consultar contas a receber: {e}")
        return None

    def get_receivable_detail(self, bling_id: int):
        """Consulta dados detalhados de uma conta a receber específica no Bling ERP (GET /contas/receber/{id})."""
        try:
            resp = self.request('GET', f'/contas/receber/{bling_id}')
            if not resp or resp.status_code == 404:
                resp = self.request('GET', f'/contas-receber/{bling_id}')
            if resp and resp.status_code == 200:
                return resp.json().get('data', {})
        except Exception as e:
            logger.error(f"[BlingApiClient] Erro ao consultar detalhe da conta a receber {bling_id}: {e}")
        return None

    def get_payables(self, page=1, limit=100):
        try:
            resp = self.request('GET', '/contas/pagar', params={'pagina': page, 'limite': limit})
            if not resp or resp.status_code == 404:
                resp = self.request('GET', '/contas-pagar', params={'pagina': page, 'limite': limit})
            if resp and resp.status_code == 200:
                return resp.json().get('data', [])
            elif resp and resp.status_code == 404:
                return []
            logger.error(f"[BlingApiClient] Falha ao consultar contas a pagar (página {page}): status {getattr(resp, 'status_code', None)}")
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao consultar contas a pagar: {e}")
        return None

    def get_payable_detail(self, bling_id: int):
        """Consulta dados detalhados de uma conta a pagar específica no Bling ERP (GET /contas/pagar/{id})."""
        try:
            resp = self.request('GET', f'/contas/pagar/{bling_id}')
            if not resp or resp.status_code == 404:
                resp = self.request('GET', f'/contas-pagar/{bling_id}')
            if resp and resp.status_code == 200:
                return resp.json().get('data', {})
        except Exception as e:
            logger.error(f"[BlingApiClient] Erro ao consultar detalhe da conta a pagar {bling_id}: {e}")
        return None

    def get_stock_balances(self, page=1, limit=100, product_ids=None, deposit_ids=None):
        """
        Consulta saldos de estoque físico e virtual da API v3 do Bling (/estoques/saldos).
        Suporta:
        - product_ids: lista com IDs dos produtos (enviado como idsProdutos[]=id1&idsProdutos[]=id2)
        - deposit_ids: lista com IDs dos depósitos (enviado como idsDepositos[]=dep1)
        - pagina / limite: para consulta paginada de saldos
        """
        if isinstance(page, (list, tuple, set)):
            product_ids = page
            page = 1

        params = {}
        if product_ids:
            if not isinstance(product_ids, (list, tuple, set)):
                product_ids = [product_ids]
            # Formato oficial da API v3 do Bling para arrays: idsProdutos[]
            params['idsProdutos[]'] = [int(p) for p in product_ids if p]
        else:
            params['pagina'] = page
            params['limite'] = limit

        if deposit_ids:
            if not isinstance(deposit_ids, (list, tuple, set)):
                deposit_ids = [deposit_ids]
            params['idsDepositos[]'] = [int(d) for d in deposit_ids if d]

        resp = self.request('GET', '/estoques/saldos', params=params)
        if resp and resp.status_code == 200:
            return resp.json().get('data', [])
        return []

    def get_product_with_stock(self, sku=None, product_id=None):
        """
        Fluxo desacoplado oficial Bling v3:
        1. Consulta dados cadastrais do produto (por SKU ou ID).
        2. Consulta saldos em /estoques/saldos usando o ID do produto.
        3. Consolida saldo_fisico e saldo_disponivel (saldoVirtual) somando os depósitos.
        """
        produto = None
        if product_id:
            produto = self.get_product_by_id(product_id)
        elif sku:
            produto = self.get_product_by_sku(sku)

        if not produto:
            return None

        p_id = produto.get('id')
        if not p_id:
            return None

        saldos = self.get_stock_balances(product_ids=[p_id])
        saldo_fisico = sum(
            float(item.get('saldoFisico') if item.get('saldoFisico') is not None else item.get('saldoFisicoTotal', 0.0) or 0.0)
            for item in saldos
        )
        saldo_virtual = sum(
            float(item.get('saldoVirtual') if item.get('saldoVirtual') is not None else item.get('saldoVirtualTotal', 0.0) or 0.0)
            for item in saldos
        )

        return {
            'id': p_id,
            'nome': produto.get('nome'),
            'codigo': produto.get('codigo'),
            'preco': float(produto.get('preco', 0.0) or 0.0),
            'preco_custo': float(produto.get('precoCusto', 0.0) or 0.0),
            'tipo': produto.get('tipo', 'P'),
            'formato': produto.get('formato', 'S'),
            'situacao': produto.get('situacao', 'A'),
            'saldo_fisico': saldo_fisico,
            'saldo_disponivel': saldo_virtual,
            'detalhes_depositos': saldos
        }

    def get_sales_channels(self):
        """
        Obtém os canais de venda e lojas virtuais configurados no Bling (/canais-venda).
        Retorna lista de dicionários com os dados de cada canal (id, descricao, tipo, situacao).
        """
        try:
            resp = self.request('GET', '/canais-venda')
            if resp and resp.status_code == 200:
                data = resp.json().get('data', [])
                logger.info(f"[BlingApiClient] {len(data)} canal(is) de venda recuperado(s) do Bling.")
                return data
            elif resp and resp.status_code != 404:
                logger.warning(f"[BlingApiClient] Erro ao buscar canais de venda: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao consultar /canais-venda: {e}")
        return []

    def get_store_products(self, loja_id: int, max_items: int = 500) -> list[dict]:
        """
        Busca os produtos vinculados a uma loja virtual ou marketplace no Bling (/produtos/lojas?idLoja=...).
        Retorna lista com IDs de vínculo (id), id do produto (produto.id), código e preço praticado na loja.
        """
        all_items = []
        page = 1
        limit = 100

        try:
            while len(all_items) < max_items:
                resp = self.request('GET', f'/produtos/lojas?idLoja={loja_id}&limite={limit}&pagina={page}', timeout=45)
                if not resp or resp.status_code != 200:
                    break

                data = resp.json().get('data', [])
                if not data:
                    break

                all_items.extend(data)
                if len(data) < limit:
                    break

                page += 1
                time.sleep(0.3)

            logger.info(f"[BlingApiClient] Loja {loja_id}: {len(all_items)} produto(s) recuperado(s) do Bling.")
        except Exception as e:
            logger.error(f"[BlingApiClient] Erro ao buscar produtos da loja {loja_id}: {e}")

        return all_items

    def get_product_store_link(self, loja_id: int, bling_product_id: int) -> dict | None:
        """
        Consulta o vínculo específico de um produto em uma loja (/produtos/lojas?idLoja=...&idProduto=...).
        """
        try:
            resp = self.request('GET', f'/produtos/lojas?idLoja={loja_id}&idProduto={bling_product_id}')
            if resp and resp.status_code == 200:
                data = resp.json().get('data', [])
                if data and len(data) > 0:
                    return data[0]
        except Exception as e:
            logger.error(f"[BlingApiClient] Erro ao consultar vínculo de produto {bling_product_id} na loja {loja_id}: {e}")
        return None

    def update_product_store_price(self, bling_product_id: int, loja_id: int, price: float, produto_loja_id: int | None = None) -> tuple[bool, str, dict]:
        """
        Atualiza o preço de venda de um produto no canal/loja selecionado no Bling.
        Utiliza PUT /produtos/lojas/{idProdutoLoja} ou POST /produtos/lojas se não houver vínculo.
        """
        try:
            rounded_price = round(float(price), 2)
            
            # 1. Se não tiver o ID do vínculo, tenta localizar via API
            if not produto_loja_id:
                link = self.get_product_store_link(loja_id, bling_product_id)
                if link and link.get('id'):
                    produto_loja_id = link.get('id')

            # 2. Se temos o ID do vínculo na loja, executa PUT
            if produto_loja_id:
                url = f'/produtos/lojas/{produto_loja_id}'
                payload = {
                    'id': int(produto_loja_id),
                    'idProdutoLoja': int(produto_loja_id),
                    'preco': rounded_price,
                    'produto': {'id': int(bling_product_id)},
                    'loja': {'id': int(loja_id)}
                }
                resp = self.request('PUT', url, json_data=payload)
                if resp and resp.status_code in (200, 204):
                    data = resp.json().get('data', {}) if resp.status_code == 200 else {'id': produto_loja_id}
                    logger.info(f"[BlingApiClient] Preço do produto {bling_product_id} na loja {loja_id} atualizado para R$ {rounded_price:.2f} (idProdutoLoja: {produto_loja_id})")
                    return True, "Preço atualizado no Bling com sucesso!", data
                else:
                    err_msg = resp.text if resp else "Sem resposta do Bling"
                    try:
                        err_json = resp.json().get('error', {})
                        err_msg = err_json.get('message', err_msg)
                        if 'fields' in err_json and err_json['fields']:
                            err_msg += " - " + err_json['fields'][0].get('msg', '')
                    except Exception:
                        pass
                    logger.warning(f"[BlingApiClient] Falha ao atualizar preço no Bling: {err_msg}")
                    return False, f"Bling API: {err_msg}", {}

            # 3. Se não existe vínculo prévio, tenta cadastrar vínculo com o preço via POST
            post_payload = {
                'preco': rounded_price,
                'produto': {'id': int(bling_product_id)},
                'loja': {'id': int(loja_id)}
            }
            resp_post = self.request('POST', '/produtos/lojas', json_data=post_payload)
            if resp_post and resp_post.status_code in (200, 201):
                data = resp_post.json().get('data', {})
                return True, "Vínculo e preço cadastrados no Bling com sucesso!", data
            else:
                err_msg = resp_post.text if resp_post else "Sem resposta"
                return False, f"Falha ao vincular produto na loja do Bling: {err_msg}", {}

        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao atualizar preço de produto na loja {loja_id}: {e}")
            return False, f"Erro interno ao atualizar preço no Bling: {str(e)}", {}

    @staticmethod
    def _extract_error_message(resp) -> str:
        """Extrai mensagem de erro legível e diagnóstica da resposta da API Bling v3."""
        if resp is None:
            return "Sem resposta do servidor Bling (tempo limite esgotado ou indisponibilidade temporária). Tente novamente em instantes."

        if resp.status_code == 429:
            return "Limite de requisições do Bling ERP atingido (HTTP 429 - Limite de 3 chamadas/segundo). Aguarde alguns segundos e tente novamente."

        if resp.status_code == 401:
            return "Autenticação expirada ou inválida no Bling (HTTP 401). Reconecte sua conta em Configurações > Integração Bling."

        if resp.status_code == 403:
            return "Permissão insuficiente na API do Bling (HTTP 403). Verifique se seu aplicativo no Bling possui permissão para Finanças."

        if resp.status_code == 404:
            return "Recurso ou lançamento financeiro não encontrado no Bling ERP (HTTP 404)."

        if resp.status_code in (500, 502, 503, 504):
            return f"Serviço do Bling temporariamente instável ou indisponível (HTTP {resp.status_code}). Tente novamente em instantes."

        msg = f"HTTP {resp.status_code}"
        try:
            resp_json = resp.json()
            err_data = resp_json.get('error', {})
            if isinstance(err_data, dict):
                description = err_data.get('description') or err_data.get('message')
                if description:
                    msg = description
                fields = err_data.get('fields', [])
                if fields and isinstance(fields, list):
                    field_msgs = [f"{f.get('element', '')}: {f.get('msg', '')}" for f in fields if isinstance(f, dict)]
                    if field_msgs:
                        msg += f" ({'; '.join(field_msgs)})"
            elif isinstance(err_data, str):
                msg = err_data
            elif resp_json.get('mensagem'):
                msg = resp_json.get('mensagem')
            elif resp_json.get('message'):
                msg = resp_json.get('message')
        except Exception:
            if resp.text:
                msg = resp.text[:250]
        return msg

    def get_payment_methods(self) -> list:
        """
        Consulta as formas de pagamento ativas no Bling (/formas-pagamentos).
        Retorna lista com id, descricao, tipoPagamento, etc.
        """
        try:
            resp = self.request('GET', '/formas-pagamentos')
            if resp and resp.status_code == 200:
                data = resp.json().get('data', [])
                logger.info(f"[BlingApiClient] {len(data)} forma(s) de pagamento recuperada(s).")
                return data
        except Exception as e:
            logger.error(f"[BlingApiClient] Erro ao consultar formas de pagamento: {e}")
        return []

    def get_revenue_expense_categories(self, tipo: int = None) -> list:
        """
        Consulta as categorias de receitas e despesas no Bling (/categorias/receitas-despesas).
        tipo: 1 para receitas, 2 para despesas (ou None para todas).
        """
        try:
            params = {}
            if tipo is not None:
                params['tipo'] = tipo
            resp = self.request('GET', '/categorias/receitas-despesas', params=params)
            if resp and resp.status_code == 200:
                data = resp.json().get('data', [])
                logger.info(f"[BlingApiClient] {len(data)} categoria(s) financeira(s) recuperada(s).")
                return data
        except Exception as e:
            logger.error(f"[BlingApiClient] Erro ao consultar categorias de receitas/despesas: {e}")
        return []

    # -------------------------------------------------------------------------
    # OPERAÇÕES DE CONTAS A PAGAR (/contas/pagar)
    # -------------------------------------------------------------------------
    def create_payable(self, payload: dict) -> tuple:
        """Criação desabilitada por regra de negócio: lançamentos devem ser feitos no Bling ERP."""
        logger.info("[BlingApiClient] Tentativa de criar conta a pagar no Bling ignorada: lançamentos são criados exclusivamente no Bling ERP.")
        return False, "Operação não permitida: novos títulos devem ser lançados diretamente no Bling ERP.", {}

    def update_payable(self, bling_id: int, payload: dict) -> tuple:
        """
        Atualiza dados de uma conta a pagar no Bling ERP (PUT /contas/pagar/{id}).
        """
        try:
            resp = self.request('PUT', f'/contas/pagar/{bling_id}', json_data=payload)
            if resp is not None and resp.status_code == 404:
                resp = self.request('PUT', f'/contas-pagar/{bling_id}', json_data=payload)
            if resp and resp.status_code in (200, 204):
                data = resp.json().get('data', {}) if resp.status_code == 200 else {'id': bling_id}
                return True, "Conta a pagar atualizada no Bling com sucesso!", data
            err_msg = self._extract_error_message(resp)
            return False, f"Bling API: {err_msg}", {}
        except requests.exceptions.Timeout:
            return False, "Bling API: Tempo limite esgotado ao atualizar conta a pagar.", {}
        except requests.exceptions.ConnectionError:
            return False, "Bling API: Falha de conexão ao atualizar conta a pagar.", {}
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao atualizar conta a pagar {bling_id}: {e}")
            return False, f"Bling API: {str(e)}", {}

    def settle_payable(self, bling_id: int, payload: dict) -> tuple:
        """
        Baixa / liquida uma conta a pagar no Bling ERP (POST /contas/pagar/{id}/baixar).
        Retorna (sucesso: bool, mensagem: str, dados: dict com borderô retornado).
        """
        try:
            resp = self.request('POST', f'/contas/pagar/{bling_id}/baixar', json_data=payload)
            if resp and resp.status_code in (200, 201, 204):
                resp_json = resp.json() if resp.content else {}
                bordero_info = resp_json.get('bordero') or resp_json.get('data', {}).get('bordero') or {}
                bordero_id = bordero_info.get('id') or resp_json.get('data', {}).get('id') or resp_json.get('id')
                logger.info(f"[BlingApiClient] Conta a pagar #{bling_id} baixada no Bling com sucesso! Borderô: {bordero_id}")
                return True, "Baixa registrada no Bling com sucesso!", {'id': bordero_id, 'bordero_id': bordero_id}
            err_msg = self._extract_error_message(resp)
            return False, f"Bling API: {err_msg}", {}
        except requests.exceptions.Timeout:
            return False, "Bling API: Tempo limite esgotado ao registrar baixa no Bling.", {}
        except requests.exceptions.ConnectionError:
            return False, "Bling API: Falha de conexão ao registrar baixa no Bling.", {}
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao baixar conta a pagar {bling_id}: {e}")
            return False, f"Bling API: {str(e)}", {}

    def delete_payable(self, bling_id: int) -> tuple:
        """Exclusão no Bling desabilitada: títulos são geridos exclusivamente no Bling ERP."""
        logger.info(f"[BlingApiClient] Tentativa de excluir conta a pagar {bling_id} no Bling ignorada.")
        return False, "Operação não permitida: a exclusão de títulos contábeis deve ser feita diretamente no Bling ERP."

    # -------------------------------------------------------------------------
    # OPERAÇÕES DE CONTAS A RECEBER (/contas/receber)
    # -------------------------------------------------------------------------
    def create_receivable(self, payload: dict) -> tuple:
        """Criação desabilitada por regra de negócio: lançamentos devem ser feitos no Bling ERP."""
        logger.info("[BlingApiClient] Tentativa de criar conta a receber no Bling ignorada: lançamentos são criados exclusivamente no Bling ERP.")
        return False, "Operação não permitida: novos títulos devem ser lançados diretamente no Bling ERP.", {}

    def update_receivable(self, bling_id: int, payload: dict) -> tuple:
        """
        Atualiza dados de uma conta a receber no Bling ERP (PUT /contas/receber/{id}).
        """
        try:
            resp = self.request('PUT', f'/contas/receber/{bling_id}', json_data=payload)
            if resp is not None and resp.status_code == 404:
                resp = self.request('PUT', f'/contas-receber/{bling_id}', json_data=payload)
            if resp and resp.status_code in (200, 204):
                data = resp.json().get('data', {}) if resp.status_code == 200 else {'id': bling_id}
                return True, "Conta a receber atualizada no Bling com sucesso!", data
            err_msg = self._extract_error_message(resp)
            return False, f"Bling API: {err_msg}", {}
        except requests.exceptions.Timeout:
            return False, "Bling API: Tempo limite esgotado ao atualizar conta a receber.", {}
        except requests.exceptions.ConnectionError:
            return False, "Bling API: Falha de conexão ao atualizar conta a receber.", {}
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao atualizar conta a receber {bling_id}: {e}")
            return False, f"Bling API: {str(e)}", {}

    def settle_receivable(self, bling_id: int, payload: dict) -> tuple:
        """
        Baixa / liquida uma conta a receber no Bling ERP (POST /contas/receber/{id}/baixar).
        Retorna (sucesso: bool, mensagem: str, dados: dict com borderô retornado).
        """
        try:
            resp = self.request('POST', f'/contas/receber/{bling_id}/baixar', json_data=payload)
            if resp and resp.status_code in (200, 201, 204):
                resp_json = resp.json() if resp.content else {}
                bordero_info = resp_json.get('bordero') or resp_json.get('data', {}).get('bordero') or {}
                bordero_id = bordero_info.get('id') or resp_json.get('data', {}).get('id') or resp_json.get('id')
                logger.info(f"[BlingApiClient] Conta a receber #{bling_id} baixada no Bling com sucesso! Borderô: {bordero_id}")
                return True, "Recebimento registrado no Bling com sucesso!", {'id': bordero_id, 'bordero_id': bordero_id}
            err_msg = self._extract_error_message(resp)
            return False, f"Bling API: {err_msg}", {}
        except requests.exceptions.Timeout:
            return False, "Bling API: Tempo limite esgotado ao registrar recebimento no Bling.", {}
        except requests.exceptions.ConnectionError:
            return False, "Bling API: Falha de conexão ao registrar recebimento no Bling.", {}
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao liquidar conta a receber {bling_id}: {e}")
            return False, f"Bling API: {str(e)}", {}

    def delete_receivable(self, bling_id: int) -> tuple:
        """Exclusão no Bling desabilitada: títulos são geridos exclusivamente no Bling ERP."""
        logger.info(f"[BlingApiClient] Tentativa de excluir conta a receber {bling_id} no Bling ignorada.")
        return False, "Operação não permitida: a exclusão de títulos contábeis deve ser feita diretamente no Bling ERP."

    def unsettle_account(self, entry_type: str, bling_id: int, bordero_id: int | None = None) -> tuple:
        """
        Estorna uma baixa no Bling ERP (reverte para Em Aberto excluindo o borderô da liquidação).
        1. Se houver id do borderô vinculado, executa DELETE /borderos/{idBordero}.
        2. Se não houver, consulta a conta (GET /contas/{tipo}/{id}) para identificar o borderô ativo.
        3. Se a exclusão do borderô retornar 403 (insufficient_scope), instrui o usuário a ativar o escopo.
        """
        try:
            base_route = '/contas/pagar' if entry_type == 'PAGAR' else '/contas/receber'

            # 1. Se já possuímos o ID do borderô registrado, tenta excluí-lo diretamente
            if bordero_id:
                try:
                    resp_bord = self.request('DELETE', f'/borderos/{bordero_id}')
                    if resp_bord and resp_bord.status_code in (200, 204):
                        logger.info(f"[BlingApiClient] Borderô #{bordero_id} da conta {bling_id} excluído com sucesso.")
                        return True, "Baixa estornada no Bling com sucesso!"
                    elif resp_bord and resp_bord.status_code == 403:
                        return False, "Bling API: Para permitir estorno de baixas, ative o escopo 'Borderôs' no seu aplicativo em developer.bling.com.br e reconecte sua conta."
                except Exception as b_err:
                    logger.warning(f"[BlingApiClient] Tentativa de remover borderô {bordero_id} falhou: {b_err}")

            # 2. Consulta a conta no Bling para obter a lista de borderos ativos
            b_id = None
            resp_det = self.request('GET', f"{base_route}/{bling_id}")
            if resp_det and resp_det.status_code == 200:
                det = resp_det.json().get('data', {})
                borderos = det.get('borderos') or []
                if borderos and isinstance(borderos, list):
                    b_id = borderos[0].get('id') if isinstance(borderos[0], dict) else borderos[0]
                elif isinstance(det.get('bordero'), dict):
                    b_id = det['bordero'].get('id')
                elif det.get('idBordero'):
                    b_id = det.get('idBordero')

            if b_id:
                resp_del_b = self.request('DELETE', f'/borderos/{b_id}')
                if resp_del_b and resp_del_b.status_code in (200, 204):
                    logger.info(f"[BlingApiClient] Borderô identificado #{b_id} excluído com sucesso.")
                    return True, "Baixa estornada no Bling ERP com sucesso!"
                elif resp_del_b and resp_del_b.status_code == 403:
                    return False, "Bling API: Para permitir estorno de baixas, ative o escopo 'Borderôs' no seu aplicativo em developer.bling.com.br e reconecte sua conta."
                err_msg = self._extract_error_message(resp_del_b)
                return False, f"Bling API: Falha ao estornar borderô no Bling ({err_msg})"

            err_msg = self._extract_error_message(resp_det) if resp_det else "Borderô da baixa não localizado"
            return False, f"Bling API: Não foi possível identificar o borderô da baixa no Bling ERP. ({err_msg})"
        except requests.exceptions.Timeout:
            return False, "Bling API: Tempo limite esgotado ao reabrir título."
        except requests.exceptions.ConnectionError:
            return False, "Bling API: Falha de conexão ao reabrir título."
        except Exception as e:
            logger.error(f"[BlingApiClient] Exceção ao estornar baixa da conta {bling_id}: {e}")
            return False, f"Bling API: {str(e)}"





