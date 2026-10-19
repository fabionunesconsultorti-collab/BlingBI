# 🟢 BlingBI - Business Intelligence Multi-Empresas & Painel de Decisão para Bling ERP

Um sistema completo de **Business Intelligence (BI) e Painel Executivo SaaS Multi-Empresas** desenvolvido em **Python Flask**, com suporte a **Multi-Tenancy por Base de Dados (dados 100% isolados por cliente)**, autenticação centralizada, gestão dinâmica de segmentos de mercado e interface inspirada na identidade moderna do **Bling ERP**.

---

## 🔑 Acesso Rápido & Credenciais Padrão

O sistema possui controle de acesso com perfil de **Super Administrador Geral** e **Empresas Clientes**:

- **URL de Acesso:** `http://localhost:5000/login` (ou na sua URL em nuvem no Render)
- **Usuário Administrador:** `admgeral`
- **Senha Inicial:** `admgeral2026`
- **Painel Administrativo:** `/admin`
- **Recursos de Segurança:**
  - Troca de senha autenticada em `/change-password`
  - Recuperação de senha por token com expiração em `/forgot-password`
  - Redefinição instantânea de senha de qualquer cliente pelo `admgeral`

---

## 🏢 Arquitetura Multi-Tenancy & Isolamento de Dados

- **Master Database**:
  - Armazena as entidades do sistema: Usuários (`master_users`), Segmentos (`master_segments`) e Tokens temporários (`master_password_resets`).
- **Tenant Database (Bases Isoladas)**:
  - Cada cliente cadastrado pelo `admgeral` opera em sua respectiva base de dados:
    - **Base Própria SQLite Dedicada (Automática)**: Criada em `data/tenants/{username}.db`, com modo WAL de alta performance.
    - **String de Conexão Externa (PostgreSQL / MySQL)**: Suporte para clientes corporativos com bancos próprios na nuvem.
- **Roteamento Transparente**:
  - O motor de conexões chaveia o banco de dados dinamicamente no contexto da requisição: os dados operacionais (pedidos, clientes, produtos e financeiro) são rigorosamente isolados.

---

## 🧩 Gestão Dinâmica de Segmentos & Telas

O `admgeral` pode cadastrar e editar **Segmentos de Mercado**, definindo quais menus e quais relatórios cada segmento terá acesso:

- **Segmentos Nativos Pré-Configurados**:
  - 👗 **Moda & Vestuário**: Módulo completo com malas condicionais, grade de cores/tamanhos e trocas.
  - 🛋️ **Movelaria & Eletrodomésticos**: Foco em ticket médio alto e canais de showroom.
  - 🍔 **Lanchonete, Bar & Restaurante**: Vendas rápidas, salão, balcão e delivery.
  - 🏠 **Utilidades Domésticas & Variedades**: Cesta com múltiplos itens e curva ABC.
  - 🧸 **Loja de Brinquedos & Lazer**: Sazonalidade, presentes e aniversariantes.
  - 🏬 **Varejo Geral Comercial**: Multicanal completo (E-commerce + Loja Física).
  - 💼 **Serviços & B2B**: Contratos recorrentes e CRM.
- **Carregamento Dinâmico**: Ao logar, o BI renderiza **apenas as telas e relatórios do segmento da empresa**.
- **Modo Auditoria ("Acessar como Empresa / Impersonate")**: O `admgeral` pode navegar pelo BI exatamente como qualquer cliente, visualizando suas telas e seus dados isolados com 1 clique.

---

## 🚀 Como Iniciar com 1 Clique

### 🪟 No Windows:
Dê um **duplo clique** no arquivo:
👉 **`iniciar.bat`**

---

### 🐧 No Linux / macOS:
Abra o terminal na pasta e execute:
```bash
./iniciar.sh
```

---

### 💻 Execução Manual:
```bash
source venv/bin/activate
python run.py
```

O sistema abrirá automaticamente no seu navegador em:
👉 **`http://127.0.0.1:5000`**

---

## 🌐 Como Ativar o Túnel HTTPS (Webhook do Bling)

Para sincronização em tempo real via Webhook em ambiente de desenvolvimento:

### 🪟 No Windows:
Dê um **duplo clique** em **`tunnel_ngrok.bat`**.

### 🐧 No Linux / macOS:
Execute **`./tunnel_ngrok.sh`**.

---

## ☁️ Como Publicar na Nuvem (Render / Railway / Docker)

O projeto já inclui `wsgi.py`, `render.yaml`, `Procfile` e `Dockerfile` configurados para deploy em 1 clique!
Consulte o guia completo em: **[DEPLOY.md](DEPLOY.md)**.

---

## 📊 Módulos e Telas do BlingBI

### 1. Dashboard 360° (Visão Geral)
- **KPIs Executivos**: Faturamento Total, Pedidos Atendidos, Ticket Médio, Previsão A Receber e A Pagar.
- **Evolução Temporal Diária**: Gráficos comparando receita e pedidos.
- **Vendas por Canal**: Mercado Livre, Shopee, Site, Loja Física e WhatsApp VIP.
- **Top 5 Produtos Mais Faturados** e **Últimos Pedidos**.

### 2. Vendas & Pedidos
- Filtros por período, canal de venda e status do pedido.
- Impressão térmica 78mm de pedidos e detalhamento de margem.
- Exportação multiformato em **Excel (.xlsx)** e **PDF**.

### 3. Produtos & Curva ABC (Pareto)
- Classificação Classe A (80%), Classe B (15%) e Classe C (5%).
- Margem Líquida por SKU e alertas de cobertura/dias de estoque.

### 4. Clientes & CRM
- Base geral de clientes e taxa de recompra (fidelização).
- Segmentação RFM de Clientes (Campeões, Fiéis, Em Risco, Hibernando).
- Top clientes por faturamento e aniversariantes do mês.

### 5. Gestão Financeira & DRE Gerencial
- Contas a Pagar e Receber (Quitado, Aberto, Atrasado).
- Índice de inadimplência e aging list.
- **DRE Sintético Gerencial por Competência** e Projeção de Fluxo de Caixa.

### 6. Central de Relatórios Estratégicos (`/reports`)
- Catálogo de relatórios dinâmicos habilitados pelo segmento da empresa.
- Exportações sob demanda em planilhas Excel formatadas e relatórios em PDF.

### 7. Integração com Bling API v3 & Webhooks
- Suporte nativo à **API v3 do Bling** (OAuth2 com renovação automática de Refresh Token).
- Botão **Testar Conexão** em tempo real e sincronização de 1 clique.
- Endpoint de Webhook em tempo real (`/integrations/webhook`).

---

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python 3.12, Flask 3.x, Flask-SQLAlchemy 3.x com `MultiTenantSession`.
- **Banco de Dados**: SQLite Multi-Bases (WAL mode) / PostgreSQL gerenciado para nuvem.
- **Frontend**: Jinja2 Templates, Vanilla CSS Bling ERP Theme, Chart.js.
- **Exportação & Analytics**: Polars, OpenPyXL e ReportLab.
- **Testes**: Pytest (suíte de testes automatizados completa para multi-tenancy e relatórios).

---

## 🧪 Executando os Testes Automatizados

```bash
# Testes da arquitetura Multi-Usuários, Autenticação e Multi-Tenancy:
PYTHONPATH=. ./venv/bin/pytest tests/test_auth_multitenant.py -v

# Todos os testes do sistema:
PYTHONPATH=. ./venv/bin/pytest tests/ -v
```
