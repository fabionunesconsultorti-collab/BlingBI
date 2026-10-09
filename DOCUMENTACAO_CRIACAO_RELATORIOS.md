# Manual de Engenharia: Criação e Gestão de Relatórios Encapsulados (BlingBI)

Este documento é a referência técnica oficial para desenvolvedores e analistas criarem, empacotarem, exportarem e importarem novos módulos de relatórios e painéis no **BlingBI**.

---

## 1. Princípio Arquitetural: Desacoplamento Total

No BlingBI, a arquitetura é estritamente dividida em duas camadas independentes:

```
┌────────────────────────────────────────────────────────┐
│             CAMADA DE DADOS & INTEGRAÇÃO               │
│  - Bling API v3 Client                                 │
│  - Pipeline de Sincronização & Webhooks                │
│  - SQLite (WAL Mode) / PostgreSQL                      │
│  - BiDataLibrary (Data Access Layer & Polars)          │
└──────────────────────────┬─────────────────────────────┘
                           │ Consumo estrito via Biblioteca de Dados
                           ▼
┌────────────────────────────────────────────────────────┐
│            MOTOR DE RELATÓRIOS MODULARES               │
│  - ReportRegistry (Descoberta & Ciclo de Vida)         │
│  - ReportPackageManager (Importação/Exportação .ZIP)   │
│  - BaseReportModule (Contrato Padronizado)             │
│  - Pacotes Encapsulados (app/reports/modules/<id>/)    │
│  - Catálogo Dinâmico (/reports/hub)                    │
└────────────────────────────────────────────────────────┘
```

### Regras de Ouro:
1. **Zero Acoplamento com APIs Externas**: Um módulo de relatório **nunca** se comunica diretamente com a API do Bling ou com tarefas de sincronização. Ele consome exclusivamente a `BiDataLibrary`.
2. **Independência de Execução**: Se um relatório falhar ou for desativado via switch (*toggle*), nenhuma outra parte do sistema é afetada.
3. **Autonomia de Empacotamento**: Cada relatório contém seu manifesto, sua engine analítica e seus templates dentro de sua própria pasta.

---

## 2. A Biblioteca de Dados (`BiDataLibrary`)

Localizada em `app/services/bi_data_library.py`, a `BiDataLibrary` é a interface unificada de acesso e extração analítica. Ela converte entidades relacionais em **DataFrames Polars**, otimizados para cálculos multivariados em alta velocidade.

### 2.1. Métodos Disponíveis

#### `BiDataLibrary.parse_date_filter(period, start_str=None, end_str=None) -> (date, date)`
Converte palavras-chave de filtro em tupla `(data_inicio, data_fim)`:
- Valores suportados: `'today'`, `'yesterday'`, `'last_7_days'`, `'last_30_days'`, `'this_month'`, `'last_month'`, `'last_90_days'`, `'last_365_days'`, `'all'`, `'custom'`.

#### `BiDataLibrary.get_orders_df(start_date, end_date, channel=None, status=None) -> pl.DataFrame`
Retorna todos os pedidos da janela temporal com o cliente associado.
- **Colunas principais**: `id`, `bling_id`, `order_number`, `order_date`, `customer_id`, `customer_name`, `total`, `discount`, `shipping`, `net_amount`, `status`, `channel`, `seller`.

#### `BiDataLibrary.get_order_items_df(start_date, end_date, channel=None, status='Atendido') -> pl.DataFrame`
Retorna itens vendidos ao nível de linha com o custo de catálogo do produto correspondente.
- **Colunas principais**: `item_id`, `order_id`, `order_number`, `order_date`, `channel`, `status`, `seller`, `product_id`, `product_code`, `product_name`, `product_category`, `quantity`, `unit_price`, `total_price`, `cost_price`, `total_cost`.

#### `BiDataLibrary.get_products_df(category=None) -> pl.DataFrame`
Retorna catálogo de SKUs e posição atual de estoque.
- **Colunas principais**: `id`, `code`, `name`, `category`, `stock_quantity`, `price`, `cost_price`, `stock_value`.

#### `BiDataLibrary.get_customers_df() -> pl.DataFrame`
Retorna histórico cadastral e métricas de compras acumuladas por cliente.
- **Colunas principais**: `id`, `bling_id`, `name`, `email`, `phone`, `city`, `state`, `total_orders`, `total_spent`, `last_order_date`.

#### `BiDataLibrary.get_financial_entries_df(start_date=None, end_date=None, entry_type=None) -> pl.DataFrame`
Retorna contas a pagar e receber.
- `entry_type`: `'R'` (Receber), `'P'` (Pagar) ou `None` (ambos).
- **Colunas principais**: `id`, `entry_type`, `category`, `amount`, `due_date`, `payment_date`, `status`, `description`.

#### `BiDataLibrary.get_summary_kpis(start_date, end_date) -> dict`
Retorna faturamento bruto, total de pedidos e ticket médio consolidado da janela temporal.

---

## 3. Anatomia de um Módulo Encapsulado

Todo relatório deve residir em seu próprio diretório em `app/reports/modules/<report_id>/`:

```
app/reports/modules/<report_id>/
├── manifest.json              # Metadados, autor, cores, tags e permissões
├── engine.py                 # Subclasse de BaseReportModule (lógica analítica e views)
├── templates/                # (Opcional) Templates Jinja2 isolados do módulo
│   └── view.html
└── static/                   # (Opcional) CSS/JS específicos
```

---

### 3.1. O Arquivo `manifest.json`

Alimenta automaticamente os cards da **Central de Relatórios** (`/reports/hub`):

```json
{
  "id": "vendas_vendedores",
  "name": "Performance por Vendedor & Metas",
  "category": "comercial",
  "description": "Acompanhamento de volume faturado, ticket médio, comissões estimadas e atingimento de metas da equipe comercial.",
  "version": "1.0.0",
  "author": "Equipe BI",
  "icon": "users",
  "color": "#0284C7",
  "tags": ["Vendas", "Vendedores", "Metas", "Comissões"],
  "export_formats": ["excel", "pdf"],
  "default_period": "last_30_days",
  "legacy_url": null
}
```

#### Campos do Manifesto:
- `id` *(obrigatório)*: Identificador único em minúsculas com underscores.
- `name` *(obrigatório)*: Título amigável exibido no painel.
- `category` *(obrigatório)*: Setor funcional (`comercial`, `produtos`, `clientes`, `financeiro`, `moda`, `personalizado`).
- `description` *(obrigatório)*: Resumo executivo de 1 a 2 frases.
- `version`: Semântica da versão (ex: `1.0.0`).
- `author`: Nome do autor ou time criador.
- `color`: Cor hexadecimal para cartões, gráficos e bordas (ex: `#008B54`, `#3B82F6`, `#EC4899`).
- `tags`: Palavras-chave pesquisáveis na barra de busca do catálogo.
- `export_formats`: Lista de formatos suportados: `["excel", "pdf"]`.
- `default_period`: Período inicial carregado (`last_30_days`, `this_month`, etc.).

---

### 3.2. A Classe `engine.py`

Deve conter uma classe que herda de `BaseReportModule`:

```python
from datetime import date
from io import BytesIO
from typing import Dict, Any, Tuple
from flask import render_template
import polars as pl

from app.reports.base import BaseReportModule
from app.services.bi_data_library import BiDataLibrary
from app.services.exporter import BiExporter

class VendedoresReportModule(BaseReportModule):
    """Módulo de Performance da Equipe de Vendas."""

    def get_data(self, start_date: date, end_date: date, **filters) -> Dict[str, Any]:
        """Extrai dados brutos via BiDataLibrary e agrega com Polars."""
        df_orders = BiDataLibrary.get_orders_df(start_date, end_date, status='Atendido')
        
        if df_orders.is_empty():
            return {
                'sellers': [],
                'summary': {'total_revenue': 0.0, 'total_orders': 0}
            }

        # Agregação por Vendedor usando Polars
        sellers_summary = (
            df_orders.group_by('seller')
            .agg([
                pl.count('id').alias('orders_count'),
                pl.sum('total').alias('revenue'),
                pl.mean('total').alias('avg_ticket')
            ])
            .sort('revenue', descending=True)
            .to_dicts()
        )

        return {
            'sellers': sellers_summary,
            'summary': {
                'total_revenue': float(df_orders['total'].sum() or 0.0),
                'total_orders': int(df_orders.height)
            }
        }

    def render(self, request_args: Dict[str, Any]) -> str:
        """Renderiza a interface do relatório."""
        period = request_args.get('period', self.metadata.default_period)
        start_str = request_args.get('start_date')
        end_str = request_args.get('end_date')

        start_date, end_date = BiDataLibrary.parse_date_filter(period, start_str, end_str)
        report_data = self.get_data(start_date, end_date)

        return render_template(
            'reports/meu_relatorio.html',
            sellers=report_data['sellers'],
            summary=report_data['summary'],
            period=period,
            start_date=start_date,
            end_date=end_date,
            report_module=self
        )

    def export_excel(self, request_args: Dict[str, Any]) -> Tuple[BytesIO, str]:
        """Gera planilha Excel para download."""
        start_date, end_date = BiDataLibrary.parse_date_filter(request_args.get('period', 'last_30_days'))
        report_data = self.get_data(start_date, end_date)
        
        # Gerar planilha via openpyxl ou Polars write_excel
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Vendas por Vendedor"
        ws.append(["Vendedor", "Pedidos", "Faturamento", "Ticket Médio"])
        for s in report_data['sellers']:
            ws.append([s['seller'], s['orders_count'], s['revenue'], s['avg_ticket']])
        
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        filename = f"Relatorio_Vendedores_{start_date.strftime('%Y%m%d')}.xlsx"
        return buffer, filename
```

---

## 4. Passo a Passo: Criando um Novo Relatório em 5 Minutos

Vamos criar um relatório prático chamado **"Vendas por Região e Estado"** (`sales_by_state`):

### Passo 1: Criar a pasta do módulo
```bash
mkdir -p app/reports/modules/sales_by_state
```

### Passo 2: Criar `manifest.json`
Crie o arquivo `app/reports/modules/sales_by_state/manifest.json`:
```json
{
  "id": "sales_by_state",
  "name": "Vendas por Estado & Região",
  "category": "comercial",
  "description": "Distribuição geográfica do faturamento e concentração de clientes por Unidade Federativa (UF).",
  "version": "1.0.0",
  "author": "Equipe BI",
  "icon": "map-pin",
  "color": "#6366F1",
  "tags": ["Geografia", "Estados", "Logística", "Fretes"],
  "export_formats": ["excel"],
  "default_period": "last_30_days"
}
```

### Passo 3: Criar `engine.py`
Crie o arquivo `app/reports/modules/sales_by_state/engine.py` consumindo os DataFrames da `BiDataLibrary` e renderizando o resultado.

### Passo 4: Atualizar / Recarregar a Aplicação
O sistema varre os módulos automaticamente ao iniciar, ou você pode chamar em runtime:
```python
from app.reports.registry import report_registry
report_registry.reload()
```
Pronto! O novo relatório aparecerá imediatamente na tela `/reports/hub`, pesquisável e com toggle ativo.

---

## 5. Importação e Exportação de Pacotes (.ZIP)

O BlingBI inclui um mecanismo nativo de portabilidade de módulos:

### 5.1. Exportando um Relatório
1. Acesse o **Catálogo de Relatórios** em `/reports/hub`.
2. No card do relatório desejado, clique no ícone **Baixar Pacote (.ZIP)** no canto inferior direito.
3. O sistema gerará um arquivo compactado (ex: `report_module_multichannel_1.0.0.zip`) contendo seu manifesto, código e templates.

### 5.2. Importando um Novo Relatório
1. No cabeçalho da **Central de Relatórios**, clique no botão **"Importar Pacote (.ZIP)"**.
2. Selecione o arquivo `.zip` fornecido por outro time ou ambiente.
3. O sistema:
   - Valida a ausência de vulnerabilidades de descompactação (*Path Traversal*).
   - Verifica a existência e formato de `manifest.json` e `engine.py`.
   - Extrai o módulo para `app/reports/modules/<id>/`.
   - Registra o módulo em tempo de execução sem reiniciar o servidor.

---

## 6. Boas Práticas e Padrões de Design

### 6.1. Performance com Polars
- Evite loops `for` em Python puro para cálculos tabulares sobre pedidos e itens.
- Utilize sempre as operações nativas do Polars: `df.group_by().agg()`, `df.filter()`, `df.select()`.

### 6.2. Tratamento Gracioso de Bases Vazias
Sempre trate o caso em que a loja ainda não possui dados no período:
```python
if df.is_empty():
    return {'rows': [], 'summary': {'total': 0.0}}
```

### 6.3. Padronização Visual no Jinja2
- Utilize as classes do Design System do BlingBI (`.card`, `.btn-primary`, `.table`, `.form-control`).
- Formatação de moedas e números com os filtros nativos do template:
  - `{{ valor|currency }}` -> Ex: `R$ 1.540,00`
  - `{{ quantidade|number }}` -> Ex: `1.250`

---

## 7. Gestão Granular de Abas, Dashboards e Gráficos (`FeatureRegistry`)

Além dos módulos de relatórios encapsulados, **todas as abas de navegação setorial, visões analíticas e blocos de gráficos** do BlingBI operam de forma 100% independente, com capacidade de ativação e desativação granular (*toggle on/off*).

### 7.1. Catálogo Mestre (`FEATURES_CATALOG`)
Localizado em `app/core/feature_registry.py`, o catálogo cataloga formalmente cada elemento visual do sistema distribuído por setores:
- **Dashboard 360°**: `dashboard.kpis`, `dashboard.sales_timeline`, `dashboard.channels_pie`, `dashboard.top_products`, `dashboard.recent_orders`
- **Vendas & Comercial**: `sales.overview`, `sales.multichannel`, `sales.sellers`, `sales.conditional_bags`
- **Produtos & Estoque**: `products.overview`, `products.abc`, `products.stock_coverage`, `products.returns`
- **Clientes & CRM**: `customers.overview`, `customers.rfm`, `customers.abc`, `customers.profiles`, `customers.birthdays`, `customers.nps`
- **Financeiro & Controladoria**: `finance.overview`, `finance.dre`, `finance.cash_flow`, `finance.aging`, `finance.cash_statement`
- **Moda & Vestuário**: `fashion.block1`, `fashion.block2`, `fashion.block3`, `fashion.block4`

### 7.2. Proteção Nativa de Rotas (`@requires_feature`)
Qualquer rota correspondente a uma aba pode ser protegida de forma declarativa:
```python
from app.core.feature_registry import requires_feature

@bp.route('/sellers')
@requires_feature('sales.sellers')
def sellers():
    ...
```
Se a funcionalidade for desativada, requisições diretas de URL são redirecionadas com segurança para o dashboard exibindo uma notificação amigável, impedindo erros 404/500 ou telas quebradas.

### 7.3. Renderização Condicional em Templates
Disponível globalmente em todos os templates Jinja2 via `is_feature_enabled`:
```html
{% if is_feature_enabled('sales.sellers') %}
<a href="{{ url_for('sales.sellers') }}">Vendedores</a>
{% endif %}
```

### 7.4. Painel de Controle e API REST
No topo da **Central de Relatórios** (`/reports/hub`), a aba **"Abas, Dashboards & Gráficos"** oferece switches interativos para ligar e desligar qualquer item em tempo real, com persistência na tabela de configurações (`Setting`) e API JSON em `POST /reports/manage/features/toggle`.

