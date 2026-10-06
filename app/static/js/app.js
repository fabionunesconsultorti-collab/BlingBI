// Funções de Interação e AJAX para BlingBI

function setAllSyncCheckboxes(val) {
    ['chkSyncOrders', 'chkSyncProducts', 'chkSyncCustomers', 'chkSyncReceivables', 'chkSyncPayables'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.checked = val;
    });
}

function setFinanceCheckboxes(val) {
    ['chkSyncReceivables', 'chkSyncPayables'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.checked = val;
    });
}

document.addEventListener('DOMContentLoaded', function () {
    // 1. Manipulação do Seletor de Período
    const periodSelect = document.getElementById('periodSelect');
    const customDateRange = document.getElementById('customDateRange');

    if (periodSelect) {
        periodSelect.addEventListener('change', function () {
            if (this.value === 'custom') {
                if (customDateRange) customDateRange.style.display = 'flex';
            } else {
                if (customDateRange) customDateRange.style.display = 'none';
                this.form.submit();
            }
        });
    }

    // 2. Teste de Conexão com a API Bling
    const btnTestConn = document.getElementById('btnTestConnection');
    const connStatusMsg = document.getElementById('connStatusMsg');

    if (btnTestConn) {
        btnTestConn.addEventListener('click', function () {
            btnTestConn.disabled = true;
            btnTestConn.innerText = 'Testando...';
            if (connStatusMsg) connStatusMsg.innerText = '';

            fetch('/integrations/test-connection', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    btnTestConn.disabled = false;
                    btnTestConn.innerText = 'Testar Conexão';
                    if (connStatusMsg) {
                        connStatusMsg.innerText = data.message;
                        connStatusMsg.style.color = data.success ? '#059669' : '#dc2626';
                    }
                })
                .catch(err => {
                    btnTestConn.disabled = false;
                    btnTestConn.innerText = 'Testar Conexão';
                    if (connStatusMsg) {
                        connStatusMsg.innerText = 'Erro ao contatar servidor: ' + err;
                        connStatusMsg.style.color = '#dc2626';
                    }
                });
        });
    }

    // 2.1 Controle Automático do Túnel HTTPS para Webhook
    const btnToggleTunnel = document.getElementById('btnToggleTunnel');
    const txtWebhookUrl = document.getElementById('txtWebhookUrl');
    const txtTunnelFeedback = document.getElementById('txtTunnelFeedback');
    const badgeTunnelStatus = document.getElementById('badgeTunnelStatus');

    if (btnToggleTunnel) {
        btnToggleTunnel.addEventListener('click', function () {
            const isCurrentlyActive = btnToggleTunnel.innerText.includes('Parar');

            if (isCurrentlyActive) {
                // Parar túnel
                btnToggleTunnel.disabled = true;
                btnToggleTunnel.innerText = 'Encerrando...';
                if (txtTunnelFeedback) txtTunnelFeedback.innerText = '';

                fetch('/integrations/tunnel/stop', { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        btnToggleTunnel.disabled = false;
                        btnToggleTunnel.innerText = '⚡ Criar Túnel HTTPS Automático';
                        btnToggleTunnel.className = 'btn btn-primary';
                        if (badgeTunnelStatus) {
                            badgeTunnelStatus.className = 'badge badge-info';
                            badgeTunnelStatus.innerText = '⚪ Túnel Inativo';
                        }
                        if (txtTunnelFeedback) {
                            txtTunnelFeedback.innerText = 'Túnel encerrado.';
                            txtTunnelFeedback.style.color = '#64748b';
                        }
                    })
                    .catch(err => {
                        btnToggleTunnel.disabled = false;
                        btnToggleTunnel.innerText = '🔴 Parar Túnel HTTPS';
                        alert('Erro ao parar túnel: ' + err);
                    });
            } else {
                // Iniciar túnel
                btnToggleTunnel.disabled = true;
                btnToggleTunnel.innerText = '⏳ Gerando túnel HTTPS seguro...';
                if (txtTunnelFeedback) {
                    txtTunnelFeedback.innerText = 'Aguarde até 10 segundos...';
                    txtTunnelFeedback.style.color = '#0284c7';
                }

                fetch('/integrations/tunnel/start', { method: 'POST' })
                    .then(res => res.json())
                    .then(data => {
                        btnToggleTunnel.disabled = false;
                        if (data.success && data.url) {
                            if (txtWebhookUrl) {
                                txtWebhookUrl.value = data.url;
                                txtWebhookUrl.style.borderColor = '#10b981';
                                txtWebhookUrl.style.backgroundColor = '#ecfdf5';
                                txtWebhookUrl.style.transition = 'all 0.3s ease';
                            }
                            btnToggleTunnel.innerText = '🔴 Parar Túnel HTTPS';
                            btnToggleTunnel.className = 'btn btn-outline';
                            if (badgeTunnelStatus) {
                                badgeTunnelStatus.className = 'badge badge-success';
                                badgeTunnelStatus.innerText = '🟢 Túnel Ativo';
                            }
                            if (txtTunnelFeedback) {
                                txtTunnelFeedback.innerText = '✅ Túnel HTTPS ativo! URL preenchida e salva automaticamente.';
                                txtTunnelFeedback.style.color = '#059669';
                            }
                        } else {
                            btnToggleTunnel.innerText = '⚡ Criar Túnel HTTPS Automático';
                            if (txtTunnelFeedback) {
                                txtTunnelFeedback.innerText = 'Erro: ' + (data.message || 'Falha ao gerar');
                                txtTunnelFeedback.style.color = '#dc2626';
                            }
                        }
                    })
                    .catch(err => {
                        btnToggleTunnel.disabled = false;
                        btnToggleTunnel.innerText = '⚡ Criar Túnel HTTPS Automático';
                        if (txtTunnelFeedback) {
                            txtTunnelFeedback.innerText = 'Erro: ' + err;
                            txtTunnelFeedback.style.color = '#dc2626';
                        }
                    });
            }
        });
    }

    // 3. Sistema de Sincronização em Tempo Real com Modal de Progresso
    const syncButtons = document.querySelectorAll('.btn-trigger-sync');
    const syncModal = document.getElementById('syncProgressModal');
    const syncSpinner = document.getElementById('syncModalSpinner');
    const syncTitle = document.getElementById('syncModalTitle');
    const syncSubtitle = document.getElementById('syncModalSubtitle');
    const syncSummary = document.getElementById('syncModalSummary');
    const syncActions = document.getElementById('syncModalActions');

    const stepAuth = document.getElementById('step-auth');
    const stepContacts = document.getElementById('step-contacts');
    const stepProducts = document.getElementById('step-products');
    const stepOrders = document.getElementById('step-orders');
    const stepFinance = document.getElementById('step-finance');

    function resetSyncModal(options) {
        if (!syncModal) return;
        syncSpinner.style.display = 'block';
        syncTitle.innerText = 'Sincronizando com o Bling ERP';
        syncSubtitle.innerText = 'Aguarde enquanto importamos seus dados atualizados...';
        syncSummary.style.display = 'none';
        syncActions.style.display = 'none';

        if (stepAuth) { stepAuth.className = 'sync-step-item active'; stepAuth.innerHTML = '<span>🔄</span> Validando token da API Bling v3...'; }
        
        if (stepContacts) {
            stepContacts.style.display = options.customers ? 'flex' : 'none';
            stepContacts.className = 'sync-step-item';
            stepContacts.innerHTML = '<span>⚪</span> Importando contatos e clientes';
        }
        if (stepProducts) {
            stepProducts.style.display = options.products ? 'flex' : 'none';
            stepProducts.className = 'sync-step-item';
            stepProducts.innerHTML = '<span>⚪</span> Importando catálogo de produtos e estoque';
        }
        if (stepOrders) {
            stepOrders.style.display = options.orders ? 'flex' : 'none';
            stepOrders.className = 'sync-step-item';
            stepOrders.innerHTML = '<span>⚪</span> Importando pedidos de vendas e itens';
        }
        if (stepFinance) {
            stepFinance.style.display = (options.receivables || options.payables) ? 'flex' : 'none';
            stepFinance.className = 'sync-step-item';
            stepFinance.innerHTML = '<span>⚪</span> Importando contas a pagar e receber';
        }
    }

    function triggerSync() {
        if (!syncModal) return;

        // Coleta seleção de módulos dos checkboxes (se estiverem na tela, senão padrão true)
        const chkOrders = document.getElementById('chkSyncOrders');
        const chkProducts = document.getElementById('chkSyncProducts');
        const chkCustomers = document.getElementById('chkSyncCustomers');
        const chkReceivables = document.getElementById('chkSyncReceivables');
        const chkPayables = document.getElementById('chkSyncPayables');

        const options = {
            orders: chkOrders ? chkOrders.checked : true,
            products: chkProducts ? chkProducts.checked : true,
            customers: chkCustomers ? chkCustomers.checked : true,
            receivables: chkReceivables ? chkReceivables.checked : true,
            payables: chkPayables ? chkPayables.checked : true
        };

        if (!options.orders && !options.products && !options.customers && !options.receivables && !options.payables) {
            alert('Por favor, marque pelo menos uma caixa de seleção para sincronizar.');
            return;
        }

        resetSyncModal(options);
        syncModal.classList.add('active');

        // Animação dos passos selecionados
        setTimeout(() => {
            if (stepAuth) { stepAuth.className = 'sync-step-item done'; stepAuth.innerHTML = '<span>✅</span> Conexão e tokens validados'; }
            if (options.customers && stepContacts) { stepContacts.className = 'sync-step-item active'; stepContacts.innerHTML = '<span>🔄</span> Importando contatos e clientes...'; }
        }, 1000);

        setTimeout(() => {
            if (options.customers && stepContacts) { stepContacts.className = 'sync-step-item done'; stepContacts.innerHTML = '<span>✅</span> Contatos e clientes importados'; }
            if (options.products && stepProducts) { stepProducts.className = 'sync-step-item active'; stepProducts.innerHTML = '<span>🔄</span> Importando produtos e estoque...'; }
        }, 3000);

        setTimeout(() => {
            if (options.products && stepProducts) { stepProducts.className = 'sync-step-item done'; stepProducts.innerHTML = '<span>✅</span> Produtos e estoque importados'; }
            if (options.orders && stepOrders) { stepOrders.className = 'sync-step-item active'; stepOrders.innerHTML = '<span>🔄</span> Importando pedidos e itens de venda...'; }
        }, 6000);

        setTimeout(() => {
            if (options.orders && stepOrders) { stepOrders.className = 'sync-step-item done'; stepOrders.innerHTML = '<span>✅</span> Pedidos e itens processados'; }
            if ((options.receivables || options.payables) && stepFinance) { stepFinance.className = 'sync-step-item active'; stepFinance.innerHTML = '<span>🔄</span> Importando contas a pagar e receber...'; }
        }, 9000);

        fetch('/integrations/sync-now', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(options)
        })
        .then(res => res.json())
        .then(data => {
            syncSpinner.style.display = 'none';

            if (data.success) {
                syncTitle.innerText = '🎉 Sincronização Concluída com Sucesso!';
                syncSubtitle.innerText = 'Seus dados foram atualizados e processados pelo motor analítico.';

                [stepAuth, stepContacts, stepProducts, stepOrders, stepFinance].forEach(el => {
                    if (el && el.style.display !== 'none') el.className = 'sync-step-item done';
                });

                const d = data.details || {};
                let summaryHtml = `<b>Resumo da Sincronização:</b><br>`;
                if (d.orders !== undefined) summaryHtml += `• <b>${d.orders}</b> Pedidos de venda importados<br>`;
                if (d.products !== undefined) summaryHtml += `• <b>${d.products}</b> Produtos e saldos de estoque<br>`;
                if (d.customers !== undefined) summaryHtml += `• <b>${d.customers}</b> Clientes e contatos<br>`;
                if (d.receivables !== undefined) summaryHtml += `• <b>${d.receivables}</b> Contas a receber<br>`;
                if (d.payables !== undefined) summaryHtml += `• <b>${d.payables}</b> Contas a pagar<br>`;

                syncSummary.innerHTML = summaryHtml;
                syncSummary.style.display = 'block';
                syncSummary.style.background = '#ecfdf5';
                syncSummary.style.borderColor = '#a7f3d0';
                syncSummary.style.color = '#065f46';

                syncActions.style.display = 'flex';
            } else {
                syncTitle.innerText = '❌ Falha na Sincronização';
                syncSubtitle.innerText = 'Não foi possível concluir a importação com o Bling.';

                syncSummary.innerHTML = `<b>Detalhe do erro:</b><br>${data.message}`;
                syncSummary.style.display = 'block';
                syncSummary.style.background = '#fef2f2';
                syncSummary.style.borderColor = '#fecaca';
                syncSummary.style.color = '#991b1b';

                syncActions.innerHTML = `<button type="button" class="btn btn-outline" onclick="document.getElementById('syncProgressModal').classList.remove('active');">Fechar</button>`;
                syncActions.style.display = 'flex';
            }
        })
        .catch(err => {
            syncSpinner.style.display = 'none';
            syncTitle.innerText = '❌ Erro de Comunicação';
            syncSubtitle.innerText = 'Ocorreu um erro ao processar a requisição com o servidor local.';

            syncSummary.innerHTML = `<b>Erro:</b> ${err}`;
            syncSummary.style.display = 'block';
            syncSummary.style.background = '#fef2f2';
            syncSummary.style.borderColor = '#fecaca';
            syncSummary.style.color = '#991b1b';

            syncActions.innerHTML = `<button type="button" class="btn btn-outline" onclick="document.getElementById('syncProgressModal').classList.remove('active');">Fechar</button>`;
            syncActions.style.display = 'flex';
        });
    }

    syncButtons.forEach(btn => {
        btn.addEventListener('click', triggerSync);
    });

    // 4. Carregar Dados Demo
    const btnSeedDemo = document.getElementById('btnSeedDemo');
    if (btnSeedDemo) {
        btnSeedDemo.addEventListener('click', function () {
            if (!confirm('Deseja popular o banco de dados com dados de teste e demonstração do Bling?')) return;
            
            btnSeedDemo.disabled = true;
            btnSeedDemo.innerText = 'Carregando Dados...';

            fetch('/integrations/seed-demo', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    btnSeedDemo.disabled = false;
                    btnSeedDemo.innerText = 'Carregar Dados de Demonstração';
                    if (data.success) {
                        window.location.href = '/';
                    } else {
                        alert('Falha ao carregar demo: ' + data.message);
                    }
                })
                .catch(err => {
                    btnSeedDemo.disabled = false;
                    btnSeedDemo.innerText = 'Carregar Dados de Demonstração';
                    alert('Erro: ' + err);
                });
        });
    }

    // 5. Zerar Base de Dados com Senha de Segurança
    const btnClearDemo = document.getElementById('btnClearDemo');
    const clearDatabaseModal = document.getElementById('clearDatabaseModal');
    const clearDbPasswordInput = document.getElementById('clearDbPasswordInput');
    const clearDbErrorMsg = document.getElementById('clearDbErrorMsg');
    const btnCancelClearDb = document.getElementById('btnCancelClearDb');
    const btnConfirmClearDb = document.getElementById('btnConfirmClearDb');

    if (btnClearDemo && clearDatabaseModal) {
        btnClearDemo.addEventListener('click', function () {
            clearDatabaseModal.classList.add('active');
            if (clearDbPasswordInput) {
                clearDbPasswordInput.value = '';
                clearDbPasswordInput.focus();
            }
            if (clearDbErrorMsg) {
                clearDbErrorMsg.style.display = 'none';
                clearDbErrorMsg.innerText = '';
            }
        });

        if (btnCancelClearDb) {
            btnCancelClearDb.addEventListener('click', function () {
                clearDatabaseModal.classList.remove('active');
            });
        }

        function executeClearDatabase() {
            const password = clearDbPasswordInput ? clearDbPasswordInput.value.trim() : '';
            if (!password) {
                if (clearDbErrorMsg) {
                    clearDbErrorMsg.innerText = 'Por favor, informe a senha de segurança.';
                    clearDbErrorMsg.style.display = 'block';
                }
                if (clearDbPasswordInput) clearDbPasswordInput.focus();
                return;
            }

            if (clearDbErrorMsg) {
                clearDbErrorMsg.style.display = 'none';
            }

            btnConfirmClearDb.disabled = true;
            btnConfirmClearDb.innerText = 'Validando e Zerando...';

            fetch('/integrations/clear-demo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: password })
            })
            .then(res => res.json().then(data => ({ status: res.status, data: data })))
            .then(result => {
                btnConfirmClearDb.disabled = false;
                btnConfirmClearDb.innerText = 'Confirmar e Zerar Base';

                if (result.status === 200 && result.data.success) {
                    clearDatabaseModal.classList.remove('active');
                    alert('✅ ' + result.data.message);
                    window.location.reload();
                } else {
                    const msg = (result.data && result.data.message) ? result.data.message : 'Falha ao validar senha.';
                    if (clearDbErrorMsg) {
                        clearDbErrorMsg.innerText = '❌ ' + msg;
                        clearDbErrorMsg.style.display = 'block';
                    } else {
                        alert('❌ ' + msg);
                    }
                    if (clearDbPasswordInput) {
                        clearDbPasswordInput.select();
                        clearDbPasswordInput.focus();
                    }
                }
            })
            .catch(err => {
                btnConfirmClearDb.disabled = false;
                btnConfirmClearDb.innerText = 'Confirmar e Zerar Base';
                if (clearDbErrorMsg) {
                    clearDbErrorMsg.innerText = 'Erro ao processar: ' + err;
                    clearDbErrorMsg.style.display = 'block';
                } else {
                    alert('Erro ao processar: ' + err);
                }
            });
        }

        if (btnConfirmClearDb) {
            btnConfirmClearDb.addEventListener('click', executeClearDatabase);
        }

        if (clearDbPasswordInput) {
            clearDbPasswordInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    executeClearDatabase();
                }
            });
        }
    }
});
