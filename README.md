# 🟢 BlingBI - Business Intelligence & Painel de Decisão para Bling ERP

Um sistema completo de **Business Intelligence (BI) e Painel Executivo** desenvolvido em **Python Flask**, projetado para rodar localmente no seu computador e abrir diretamente no navegador com a identidade visual moderna e limpa do **Bling ERP**.

---

## 🚀 Como Iniciar com 1 Clique

O BlingBI conta com inicializadores automáticos que preparam o ambiente (se necessário), sobem o servidor e abrem a tela do BI no seu navegador:

### 🪟 No Windows:
Dê um **duplo clique** no arquivo:
👉 **`iniciar.bat`**

*(Ou execute `iniciar.bat` no Prompt de Comando/PowerShell)*

---

### 🐧 No Linux / macOS:
Abra o terminal na pasta e execute:
```bash
./iniciar.sh
```

---

### 💻 Execução Manual (Opcional):
```bash
source venv/bin/activate
python run.py
```

O sistema abrirá automaticamente no seu navegador em:
👉 **`http://127.0.0.1:5000`**

*(Se o banco estiver vazio na primeira execução, o sistema carrega automaticamente dados demonstrativos realistas para que você explore todos os relatórios e gráficos imediatamente!)*

---

## 🌐 Como Ativar o Túnel HTTPS (Webhook do Bling)

Como o Bling ERP exige obrigatoriamente **HTTPS** para envio de Webhooks em tempo real, criamos scripts automatizados que configuram o **Ngrok gratuito** para você em 1 passo:

### 🪟 No Windows:
Dê um **duplo clique** em:
👉 **`tunnel_ngrok.bat`**

### 🐧 No Linux / macOS:
No terminal, execute:
```bash
./tunnel_ngrok.sh
```

O script baixa o Ngrok automaticamente (se necessário), configura seu token e inicia o túnel para a porta 5000.
A URL pública gerada (ex: `https://xxxx.ngrok-free.app/integrations/webhook`) estará pronta para você cadastrar no Bling ERP em **Preferências > Notificações/Webhooks**!

---

### 1. Dashboard 360° (Visão Geral)
- **KPIs Executivos**: Faturamento Total, Pedidos Atendidos, Ticket Médio, Contas a Receber (Previsão) e Contas a Pagar (Previsão).
- **Evolução Temporal Diária**: Gráfico de linha interativo comparando Receita e Quantidade de Pedidos.
- **Vendas por Canal**: Gráfico de rosca detalhando vendas por Marketplace (Mercado Livre, Shopee, Amazon, Site Próprio, Loja Física).
- **Top 5 Produtos Mais Faturados** e **Pedidos Recentes**.

### 2. Vendas & Pedidos
- Filtros por Período (Hoje, 7 dias, 30 dias, Mês Atual, Personalizado).
- Filtros refinados por **Canal de Venda** e **Status do Pedido** (Atendido, Em aberto, Cancelado).
- Detalhamento de descontos e fretes cobrados.
- **Exportação Multiformato**:
  - 📥 **Exportar Planilha Excel (.xlsx)** formatada com cores do Bling, cabeçalho e totais.
  - 📄 **Exportar Relatório em PDF** corporativo e formatado.

### 3. Produtos & Curva ABC (Pareto)
- Classificação de produtos em **Classe A (80% da receita)**, **Classe B (15%)** e **Classe C (5%)**.
- Cálculo de **Margem Líquida** e percentual de margem por item.
- Alerta de **Estoque Crítico / Baixo**.
- Exportação da Curva ABC completa para Excel.

### 4. Clientes & CRM
- Análise de base de clientes cadastrados x clientes ativos no período.
- **Taxa de Recompra (Fidelização)** de compradores recorrentes.
- Ranking de **Top Clientes por Faturamento**.
- Concentração geográfica de clientes por Estado (UF).

### 5. Gestão Financeira & DRE Gerencial
- Balanço de **Contas a Receber** vs **Contas a Pagar** (Quitado, Pendente e Atrasado).
- **Índice de Inadimplência** em tempo real.
- **DRE Sintético**:
  - (+) Receita Bruta de Vendas
  - (-) Deduções & Cancelamentos
  - (=) Receita Operacional Líquida
  - (-) Custo das Mercadorias Vendidas (CPV Médio)
  - (=) Lucro Bruto / Margem de Contribuição
  - (-) Despesas Fixas e Operacionais
  - (=) Resultado Líquido do Período & Margem Líquida.

### 6. Integração com Bling API v3 & Webhooks
- Suporte nativo à **API v3 do Bling** (OAuth2 com renovação automática de Refresh Token).
- Botão **Testar Conexão** em tempo real.
- Sincronização sob demanda com 1 clique (Clientes, Produtos, Pedidos e Contas).
- Endpoint para Webhook do Bling (`/integrations/webhook`).
- Botão para recarregar **Dados de Demonstração** quando desejar.

---

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python 3.12, Flask, Flask-SQLAlchemy, SQLite (banco local analítico de alta velocidade).
- **Frontend**: Jinja2 Templates, Vanilla CSS com Design System inspirado no Bling ERP, Chart.js.
- **Exportação**: OpenPyXL (Excel `.xlsx`) e ReportLab (Documentos `.pdf`).
- **Testes**: Pytest (suíte de testes automatizados completa).

---

## 🧪 Executando os Testes Automatizados

Para rodar a suíte de testes:

```bash
PYTHONPATH=. ./venv/bin/pytest tests/ -v
```
