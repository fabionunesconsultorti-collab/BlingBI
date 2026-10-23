# 💳 Documentação Técnica: Módulo de Contas a Pagar & Contas a Receber

## 1. Visão Geral e Finalidade
O módulo de **Contas a Pagar & Receber** do **BlingBI** fornece controle financeiro operacional e executivo de alta precisão para a gestão de compromissos a pagar e direitos a receber da empresa. O módulo conecta-se diretamente com o ecossistema ERP Bling v3 e opera com total desacoplamento arquitetural, oferecendo:

1. **Gestão Operacional de Lançamentos:** Visualização de títulos com busca textual multicampo, ordenação dinâmica, paginação e filtros padronizados por tipo, situação, período, categoria e meio de pagamento.
2. **Alertas Inteligentes de Vencimento:** Painel de notificação com detecção em tempo real de títulos em atraso, vencendo hoje e previstos para os próximos 7 dias.
3. **Calendário Interativo de Vencimentos:** Grade mensal (Domingo a Sábado) com navegação mês a mês, balões coloridos de compromissos (`- Pagar` em vermelho e `+ Receber` em verde) e somatório de saldos projetados do mês.
4. **Baixa e Liquidação Direta pelo BI:** Capacidade de quitar títulos diretamente na interface do BI, com cálculo instantâneo de descontos e juros/multas, carimbo de data e sincronização opcional com a API do Bling.
5. **Estorno e Edição:** Capacidade de reabrir títulos baixados indevidamente (estorno para `Pendente`), além de edição e exclusão de lançamentos avulsos manuais.
6. **Exportação Executiva Multiformato:** Emissão de relatórios em Excel (`.xlsx` multi-aba com formatação monetária e zebra) e PDF Executivo em formato paisagem (Landscape A4) gerados via ReportLab.

---

## 2. Arquitetura e Desacoplamento de Domínio

O módulo adota o padrão de arquitetura desacoplada do BlingBI, atendendo a todos os requisitos:

* **Isolamento de Domínio:** Toda a lógica de negócio, agrupamentos de calendário e consultas SQL residem em `app/services/accounts_service.py` (`AccountsService`).
* **Feature Toggle Integrado:** O módulo é registrado no catálogo com o identificador `'finance.accounts'` ("Aba Contas a Pagar & Receber"), permitindo ativação ou desativação instantânea nas configurações do sistema ou via controle de acesso granular de usuários.
* **Modelo de Dados Híbrido:** `FinancialEntry` (`financial_entries`) armazena lançamentos com compatibilidade total para SQLite e PostgreSQL/Supabase. Os títulos importados do Bling preservam seus `bling_id` originais, enquanto lançamentos avulsos manuais geram identificadores sintéticos únicos baseados em epoch milissegundos para evitar qualquer conflito.

### Modelo Entidade-Relacionamento (`FinancialEntry`)
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `id` | `INTEGER PRIMARY KEY` | Chave primária interna do BI |
| `bling_id` | `BIGINT UNIQUE NOT NULL` | ID oficial do título no Bling ERP ou ID sintético |
| `entry_type` | `VARCHAR(10) NOT NULL` | `PAGAR` (despesa/fornecedor) ou `RECEBER` (receita/cliente) |
| `description` | `VARCHAR(255) NOT NULL` | Descrição da operação / Histórico |
| `entity_name` | `VARCHAR(255)` | Favorecido ou Pagador (sinônimo `payee_payer`) |
| `category` | `VARCHAR(100)` | Categoria financeira (Operacional, Fornecedores, Impostos...) |
| `amount` | `FLOAT NOT NULL` | Valor nominal do título |
| `discount` | `FLOAT DEFAULT 0.0` | Desconto obtido ou concedido |
| `fine_fee` | `FLOAT DEFAULT 0.0` | Juros, multa ou acréscimo |
| `issue_date` | `DATE NOT NULL` | Data de emissão |
| `due_date` | `DATE NOT NULL` | Data de vencimento |
| `payment_date`| `DATE NULL` | Data da baixa/liquidação efetiva |
| `status` | `VARCHAR(20)` | `Pendente`, `Pago`, `Atrasado`, `Cancelado` |
| `payment_method`| `VARCHAR(100)` | Boleto, PIX, Cartão de Crédito, Transferência, etc. |
| `notes` | `TEXT NULL` | Observações da baixa, autenticação bancária e histórico |

---

## 3. Endpoints e Rotas Disponibilizadas

Todas as rotas pertencem ao blueprint `finance` com prefixo `/finance`:

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/finance/accounts` | Tela principal com alternador de lista/calendário, KPIs e filtros |
| `POST`| `/finance/accounts/settle/<id>` | Executa a baixa/liquidação direta com data, meio e descontos/multas |
| `POST`| `/finance/accounts/unsettle/<id>` | Estorna a baixa e retorna o título para a situação 'Pendente' |
| `POST`| `/finance/accounts/create` | Criação de lançamento manual avulso |
| `POST`| `/finance/accounts/update/<id>` | Edição de campos de um lançamento existente |
| `POST`| `/finance/accounts/delete/<id>` | Exclusão definitiva do registro |
| `GET` | `/finance/accounts/export/excel` | Download da planilha Excel formatada (`.xlsx`) |
| `GET` | `/finance/accounts/export/pdf` | Download do relatório executivo em PDF (`.pdf`) |
| `POST`| `/finance/accounts/sync` | Aciona a sincronização seletiva de contas a pagar e receber do Bling |

---

## 4. Métricas e KPIs Calculados

O serviço `AccountsService.get_summary_metrics()` consolida indicadores financeiros em tempo real:

1. **Total a Receber (Previsto / Pendente):**
   $$\text{Receber Pendente} = \sum (\text{amount}) \quad \text{onde } \text{entry\_type} = \text{'RECEBER'} \land \text{status} \in (\text{'Pendente'}, \text{'Atrasado'})$$
2. **Total a Pagar (Previsto / Pendente):**
   $$\text{Pagar Pendente} = \sum (\text{amount}) \quad \text{onde } \text{entry\_type} = \text{'PAGAR'} \land \text{status} \in (\text{'Pendente'}, \text{'Atrasado'})$$
3. **Saldo Líquido Previsto:**
   $$\text{Saldo Previsto} = \text{Receber Pendente} - \text{Pagar Pendente}$$
4. **Saldo Líquido Realizado (Efetivo Quitado):**
   $$\text{Saldo Realizado} = \text{Total Recebido (Pago)} - \text{Total Pago (Quitado)}$$
5. **Inadimplência Geral:**
   $$\text{Total em Atraso} = \sum (\text{amount}) \quad \text{onde } \text{status} = \text{'Atrasado'} \lor (\text{status} = \text{'Pendente'} \land \text{due\_date} < \text{hoje})$$
   $$\text{Taxa de Inadimplência (\%)} = \left(\frac{\text{Atrasado}}{\text{Total Títulos}}\right) \times 100$$
6. **Alertas Diários, Semanais e Mensais:**
   * **Hoje:** Títulos pendentes com `due_date = hoje`.
   * **Semana:** Títulos pendentes com `due_date` entre hoje e os próximos 7 dias.
   * **Mês:** Títulos pendentes com vencimento até o último dia do mês corrente.

---

## 5. Calendário Interativo de Vencimentos

A grade do calendário é gerada por `AccountsService.get_calendar_events(year, month)`:
* **Matriz de Semanas (Domingo a Sábado):** Cada semana contém 7 dias, onde dias de outros meses são preenchidos com objetos vazios e bandeira `is_current_month = False`.
* **Células dos Dias:** Indicam se o dia é hoje (`is_today`), se possui pendências em atraso (`has_overdue`) e botões coloridos para filtragem instantânea na lista de títulos.
* **Navegação Temporal:** Botões intuitivos de "Mês Anterior" e "Próximo Mês" com virada automática de ano.

---

## 6. Procedimento de Testes Automatizados

A suíte de testes `tests/test_financial_accounts.py` cobre:
* `test_accounts_service_crud_and_settlement`: Criação manual, consulta, baixa direta, estorno, edição e exclusão.
* `test_accounts_summary_metrics_and_alerts`: Validação das métricas de hoje, semana e atraso.
* `test_accounts_calendar_events`: Verificação da integridade das semanas e totais do mês.
* `test_accounts_exporter_excel_and_pdf`: Garantia da geração binária de planilhas Excel e documentos PDF.
* `test_accounts_routes`: Testes de ponta a ponta com cliente HTTP Flask para visualização, ações e exportações.

Para executar os testes:
```bash
PYTHONPATH=. venv/bin/pytest tests/test_financial_accounts.py -v
```
