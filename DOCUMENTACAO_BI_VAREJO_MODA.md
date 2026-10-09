# 👗 Documentação Técnica: Módulo BI Varejo de Moda & Customer Success (CS)

## 1. Visão Geral e Finalidade
Este módulo implementa uma **pipeline de dados analítica de alta performance em Python e Polars** integrada ao **BlingBI**, estruturada em **4 Blocos Estratégicos** desenhados sob medida para o varejo de moda (vestuário, calçados e acessórios) e alinhados diretamente à operação de Customer Success e Vendas.

O objetivo principal é transformar dados transacionais do ERP em inteligência acionável para o time de loja e vendas consultivas (WhatsApp, malas de prova, reativação de carteira e controle de qualidade de modelagem).

---

## 2. Arquitetura e Engenharia de Dados

### Motor Analítico: Polars (`pl.DataFrame` e `pl.LazyFrame`)
* **Processamento Vetorizado em Rust:** Elimina gargalos de CPU e limitações do GIL (*Global Interpreter Lock*).
* **Eficiência de Memória com Apache Arrow:** Permite agregações analíticas complexas com uso reduzido de memória RAM.
* **Lazy Evaluation:** Otimização antecipada de planos lógicos (filtros e projeções antes de carregar dados).

### Modelagem Dimensional (Star Schema)
```
       [dim_clientes]       [dim_produtos]       [dim_vendedores]
              \                   |                   /
               \                  |                  /
              [fato_vendas_itens] / [fato_condicionais]
                       |                   |
               [fato_devolucoes]   [fato_satisfacao]
```

---

## 3. Os 4 Blocos Estratégicos de Relatórios

### 👤 BLOCO 1: Perfil e Comportamento de Compra
1. **Histórico de Compras por Cliente (Moda Estatística):**
   * Agrupamento analítico por cliente.
   * Cálculo da **Moda** (valor mais frequente) das variáveis:
     * `preferred_size` (Tamanho mais comprado: P, M, G, 38, 40...)
     * `preferred_color` (Paleta de cor preferida)
     * `preferred_style` (Estilo predominante: Casual, Alfaiataria, Festa...)
   * Total de peças, faturamento acumulado e ticket médio individual.
2. **Curva ABC de Clientes (Regra 80/20 de Pareto):**
   * Ordenação decrescente de faturamento por cliente com soma cumulativa (`cum_sum()`).
   * **Classe A**: Responsáveis pelos primeiros **80%** da receita da loja.
   * **Classe B**: Próximos **15%** (80% a 95%).
   * **Classe C**: **5%** restantes (cauda longa).
   * Resumo executivo com contagem de clientes e share de faturamento por classe.
3. **Relatório de Aniversariantes do Mês:**
   * Extração temporal do mês da data de nascimento (`birth_date`).
   * Cálculo dos dias restantes para o aniversário ou se já ocorreu.
   * Contato e preferências prontos para o time de CS disparar vouchers comemorativos.

---

### 👗 BLOCO 2: Movimentação e Preferências de Moda
1. **Relatório de Condicionais (Conversão da Bag):**
   * Rastreamento de peças enviadas para prova em casa (`items_sent`), peças faturadas (`items_invoiced`) e devolvidas (`items_returned`).
   * **Taxa de Conversão da Bag**:
     $$\text{Conversão} = \left(\frac{\text{Peças Faturadas}}{\text{Peças Enviadas}}\right) \times 100$$
   * Desempenho por Vendedora (quem converte melhor) e ranking por Cliente.
2. **Produtos Mais Vendidos (Ranking por Categoria):**
   * Window function analítica no Polars:
     `pl.col("total_revenue").rank(descending=True).over("category")`
   * Top 5 peças mais vendidas dentro de cada categoria (Vestidos, Alfaiataria, Jeanswear, etc.).
3. **Relatório de Trocas e Devoluções:**
   * **Taxa de Devolução por SKU**:
     $$\text{Taxa Devolução} = \left(\frac{\text{Qtd Devolvida}}{\text{Qtd Vendida}}\right) \times 100$$
   * Distribuição analítica por motivo da devolução (ex: *Modelagem pequena*, *Tamanho não serviu*, *Defeito de costura*), direcionando ajustes de modelagem com fornecedores.

---

### 🎯 BLOCO 3: Desempenho do Atendimento (KPIs)
1. **Peças por Atendimento (P.A. Médio):**
   * Média de peças vendidas por pedido atendido:
     $$\text{P.A.} = \frac{\sum \text{Peças Vendidas}}{\text{Total de Pedidos}}$$
   * Benchmark da loja vs resultado por consultora de vendas.
2. **Ticket Médio por Vendedor e por Cliente:**
   * Faturamento médio por transação gerada pela vendedora.
   * Identificação de clientes com maior ticket médio histórico.
3. **Taxa de Conversão por Vendedor:**
   * Cruzamento entre atendimentos iniciados (`SellerAttendance`) e pedidos convertidos:
     $$\text{Conversão Comercial} = \left(\frac{\text{Atendimentos Convertidos}}{\text{Total Atendimentos}}\right) \times 100$$

---

### 💎 BLOCO 4: Relacionamento e Fidelização (CRM)
1. **Relatório de Clientes Inativos (Recência de Compra):**
   * Cálculo de dias decorridos desde a última compra (`days_inactive = hoje - ultima_compra`).
   * Segmentação em 4 faixas de risco:
     * 🟢 **Ativo**: $< 60$ dias
     * 🟡 **Atenção**: $60$ a $90$ dias (momento de apresentar nova coleção)
     * 🟠 **Inativo**: $91$ a $180$ dias (risco iminente de perda)
     * 🔴 **Churn**: $> 180$ dias (necessita campanha agressiva de reativação)
   * Link direto para abertura de conversa no WhatsApp (`wa.me`) com tamanho e estilo favoritos do cliente.
2. **Índice de Recompra (Cohort Analysis):**
   * Agrupamento por safra do mês da primeira compra.
   * Matriz de retenção percentual nos meses subsequentes.
3. **Pesquisas de Satisfação (NPS & CSAT):**
   * **Net Promoter Score (NPS)**:
     $$\text{NPS Score} = \% \text{Promotores (9-10)} - \% \text{Detratores (0-6)}$$
   * **CSAT Médio**: Escala de 1 a 5 estrelas com feed de depoimentos qualitativos recentes.

---

## 4. Endpoints & Rotas HTTP

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/fashion/` | Painel principal do módulo com abas estratégicas (`tab=block1`, `block2`, `block3`, `block4`), filtros refinados e gráficos representativos. |
| `GET/POST`| `/fashion/seed-demo` | Popula ou enriquece a base com dados realistas de demonstração de moda. |
| `GET` | `/fashion/export/abc` | Exporta a planilha Excel `.xlsx` da Curva ABC de clientes formatada. |
| `GET` | `/fashion/export/abc/pdf` | Exporta o relatório executivo da Curva ABC em formato `.pdf` via ReportLab. |
| `GET` | `/fashion/export/bags` | Exporta relatório de malas condicionais em planilha `.xlsx`. |
| `GET` | `/fashion/export/bags/pdf` | Exporta relatório de malas condicionais em `.pdf`. |
| `GET` | `/fashion/export/kpis/pdf` | Exporta o relatório de desempenho do atendimento e vendas (P.A., Ticket, Conversão) em `.pdf`. |
| `GET` | `/fashion/export/inactives`| Exporta a lista de clientes inativos para CRM/WhatsApp em `.xlsx`. |
| `GET` | `/fashion/export/inactives/pdf` | Exporta a lista de recência e clientes em risco de churn em `.pdf`. |

---

## 5. Filtros Disponíveis nos Relatórios

* **Filtro Global de Período**: Hoje, Ontem, Últimos 7 dias, Últimos 30 dias, Este Mês, Mês Anterior e Personalizado.
* **Filtro por Vendedora / Consultora**: Todas ou seleção individual (`Camila Duarte`, `Mariana Rios`, `Beatriz Santos`, `Lucas Mendes`).
* **Filtro por Categoria de Moda**: Todas ou categorias específicas (`Vestidos`, `Alfaiataria`, `Jeanswear`, etc.).
* **Filtro por Classe ABC** (Bloco 1): Todas as Classes, Classe A, Classe B ou Classe C.
* **Filtro por Mês de Aniversário** (Bloco 1): Seleção de qualquer um dos 12 meses do ano.
* **Filtro por Motivo de Devolução** (Bloco 2): Filtragem analítica por motivo da troca/devolução.
* **Filtro por Faixa de Recência** (Bloco 4): Ativo (<60d), Atenção (60-90d), Inativo (91-180d) e Churn (>180d).

---

## 6. Gráficos Representativos Implementados (Chart.js)

* **Bloco 1**: Rosca de Receita por Classe ABC, Barra de Tamanhos Mais Comprados (Moda) e Barra de Aniversariantes por Semana.
* **Bloco 2**: Barra comparativa de Malas Condicionais (Enviadas vs Faturadas) e Rosca de Motivos de Devolução.
* **Bloco 3**: Barra de P.A. por Consultora com linha de benchmark da loja e Barra de Taxa de Conversão Comercial (%).
* **Bloco 4**: Rosca de Faixas de Recência/Risco, Rosca de NPS (Promotores vs Detratores) e Barra de Volume Financeiro (LTV) em Risco.

---

## 7. Testes Automatizados

A suíte de testes em `tests/test_fashion_bi.py` cobre todos os 4 blocos, filtros, gráficos e exportações:

```bash
PYTHONPATH=. ./venv/bin/pytest tests/ -v
```

Resultado dos testes: **100% de sucesso (7 testes específicos + 22 testes gerais da aplicação = 29 testes passando).**
