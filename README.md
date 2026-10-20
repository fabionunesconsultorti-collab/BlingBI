# 🟢 BlingBI - Business Intelligence Multi-Empresas & Painel de Decisão para Bling ERP

Um sistema completo de **Business Intelligence (BI) e Painel Executivo SaaS Multi-Empresas** desenvolvido em **Python Flask**, com suporte a **Multi-Tenancy por Base de Dados (dados 100% isolados por cliente)**, autenticação centralizada, gestão dinâmica de segmentos de mercado e interface inspirada na identidade moderna do **Bling ERP**.

---

## 🔑 Acesso Rápido & Credenciais Padrão

O sistema possui controle de acesso com perfil de **Super Administrador Geral** e **Empresas Clientes**:

- **URL de Acesso:** `http://localhost:5000/login` (ou na sua URL em nuvem no Render)
- **Usuário Administrador:** `admgeral`
- **Senha Inicial:** Definida de forma secreta via variável de ambiente `ADMIN_DEFAULT_PASSWORD` (ou na criação inicial da instância)
- **Painel Administrativo:** `/admin`
- **Recursos de Segurança:**
  - Nenhuma senha em texto claro é exibida em telas ou mantida no repositório.
  - Troca de senha autenticada em `/change-password`
  - Recuperação de senha por token com expiração em `/forgot-password`
  - Redefinição instantânea de senha de qualquer cliente pelo `admgeral`

---

## 🔐 Segurança e Variáveis de Ambiente

As credenciais do sistema são protegidas e podem ser definidas de forma confidencial através de variáveis de ambiente no servidor (Render, Railway, Docker ou local):

| Variável | Finalidade | Configuração Recomendada |
|---|---|---|
| `ADMIN_DEFAULT_PASSWORD` | Senha do Super Administrador (`admgeral`) | Definir senha forte no dashboard do servidor |
| `CLEAR_DATABASE_PASSWORD` | Senha de segurança para comandos de limpeza e carga demo | Definir senha administrativa no dashboard |
| `SECRET_KEY` | Chave criptográfica de sessão Flask | Chave aleatória gerada automaticamente |
| `SUPABASE_DB_URL` | String de conexão direta ou Pooler do Supabase (PostgreSQL) | Permite persistência 100% vitalícia e schemas isolados |
| `DATABASE_URL` | Conexão do banco Master (PostgreSQL ou Supabase) | Compatível com Render Postgres ou Supabase |
| `BLING_CLIENT_ID` | Client ID da API v3 do Bling ERP (opcional) | Configurado na tela `/integrations/` ou ambiente |
| `BLING_CLIENT_SECRET` | Client Secret da API v3 do Bling ERP (opcional) | Configurado na tela `/integrations/` ou ambiente |

---

## ⚡ Conectividade Supabase & Schemas Dedicados (100% Persistente)

Para ambientes de nuvem efêmeros (como instâncias gratuitas ou standard do Render que apagam arquivos locais ao reiniciar):
- **Isolamento por Schemas Nativos (`tenant_{username}`)**: Todas as tabelas operacionais do cliente residem em um schema dedicado dentro do Supabase PostgreSQL, mantendo isolamento absoluto de dados sem custos extras de múltiplas instâncias.
- **Assistente de Migração em 1 Clique (`/admin/migrate-supabase`)**:
  - Teste prévio de conectividade com a URL do Supabase (porta 5432 ou Transaction/Session Pooler 6543).
  - Cópia segura de todos os dados existentes de bancos SQLite locais diretamente para os schemas do Supabase.
  - Conversão automática dos clientes para utilizarem seus schemas correspondentes.
  - O sistema passa a funcionar com persistência permanente, imune a reinicializações de contêineres.

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

### 3. Produtos, Estoque & Inteligência de Preços
- **Inventário & Catálogo Unificado**: Busca geral por tamanho, cor, SKU e saldos em estoque.
- **Curva ABC (Pareto)**: Classificação 80/15/5 dos itens com maior impacto no faturamento.
- **Dias de Cobertura & Ruptura**: Previsão de dias de estoque e alertas de desabastecimento.
- **Análise de Estoque & Gestão de Preços por Canal (`/products/stock-analysis`)**:
  - Filtros cruzados por categoria, status de estoque (Ruptura/Zerado, Crítico, Equilibrado, Excesso), curva ABC, canal e faixas de preço/margem.
  - Comparativo de **Preço Base de Venda** vs **Preços por Canal** (Mercado Livre, Shopee, Amazon, Site Próprio, Loja Física).
  - Controle de **Custo Base** e **Valor Pago na Aquisição** com **edição inline direta (AJAX)** na tabela.
  - Exportação e importação em lote via planilha **Excel (.xlsx)** para atualização em massa.
- **Precificação Automática em Marketplaces (`/products/pricing`)**:
  - Motor de **Markup Reverso** parametrizável com 8 regras padrão de mercado (ML Clássico, ML Premium, Shopee, Amazon, Magalu, etc.).
  - Tratamento inteligente da **regra dos R$ 79,00** (taxas fixas por item para produtos abaixo de R$ 79 e frete grátis obrigatório do seller para produtos a partir de R$ 79).
  - **Simulador Interativo com DRE Unitário**: Cálculo em tempo real de Preço Sugerido, Impostos DAS, Comissão da Plataforma, Taxa Fixa, Frete Seller e Lucro Líquido Real (R$ e %).
  - Aplicação de preços calculados com 1 clique (individual ou em lote para múltiplos produtos selecionados).
- **Trocas & Devoluções por SKU**: Rastreamento de motivos de trocas e índice de retorno.

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

### 8. Central de Contingência & Backup Geral (`/admin/backups`)
- **Persistência Garantida em Nuvem**: Ativação transparente do banco gerenciado persistente PostgreSQL no Render (`render.yaml`), mantendo todos os clientes, segmentos e configurações salvos mesmo após reinicializações e novos deploys de contêineres.
- **Backup Completo em 1 Clique**: Gera pacotes compactados `.zip` estruturados com banco Master, bases dedicadas de todos os clientes (`data/tenants/*.db`), configurações operacionais e manifesto de integridade com hash SHA-256.
- **Rotina Programável & Rotação Automática**: Política de agendamento configurável (diário, semanal, mensal ou por intervalo de horas), horário preferencial e limite de retenção com rotação automática dos arquivos mais antigos.
- **Painel de Restauração Integrado**:
  - Restauração a partir do histórico local com verificação de segurança (digitação obrigatória da palavra `RESTAURAR`).
  - Restauração por **Upload de arquivo `.zip`** externo.
  - Modos de restauração: Total, Apenas Bases de Clientes ou Apenas Configurações e Segmentos.
  - Download individual dos backups para contingência externa.

### 9. Assistente de Migração para Supabase (`/admin/migrate-supabase`)
- **Migração em 1 Clique**: Transfere todas as bases e dados operacionais de instâncias locais/efêmeras SQLite para o Supabase (PostgreSQL).
- **Schemas Dedicados (`tenant_{username}`)**: Cada cliente recebe seu próprio schema isolado, garantindo total privacidade e alta escalabilidade.
- **Diagnóstico em Tempo Real**: Validação de conectividade e status dos schemas diretamente pelo painel administrativo.

---

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python 3.12, Flask 3.x, Flask-SQLAlchemy 3.x com `MultiTenantSession`.
- **Banco de Dados**: SQLite Multi-Bases (WAL mode) / PostgreSQL gerenciado & Supabase com Schemas.
- **Frontend**: Jinja2 Templates, Vanilla CSS Bling ERP Theme, Chart.js.
- **Exportação & Analytics**: Polars, OpenPyXL e ReportLab.
- **Testes**: Pytest (suíte de testes automatizados completa para multi-tenancy e relatórios).

---

## 🧪 Executando os Testes Automatizados

```bash
# Testes da arquitetura Multi-Usuários, Autenticação e Multi-Tenancy:
PYTHONPATH=. ./venv/bin/pytest tests/test_auth_multitenant.py -v

# Testes do Migrador Supabase e Schemas Dedicados:
PYTHONPATH=. ./venv/bin/pytest tests/test_supabase_migrator.py -v

# Testes da Central de Backup e Contingência:
PYTHONPATH=. ./venv/bin/pytest tests/test_backup_system.py -v

# Todos os testes do sistema:
PYTHONPATH=. ./venv/bin/pytest tests/ -v
```
