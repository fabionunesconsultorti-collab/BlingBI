#!/usr/bin/env bash

# ==============================================================================
# BlingBI - Túnel HTTPS para Webhook (Linux / macOS)
# Suporta Localtunnel (sem cadastro) e Ngrok (com Authtoken)
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "======================================================="
echo "       🌐 BlingBI - Túnel HTTPS para Webhook           "
echo "======================================================="
echo ""
# Detecta npx
NPX_BIN="npx"
if ! command -v npx &> /dev/null; then
    for cand in ~/.nvm/versions/node/*/bin/npx /usr/local/bin/npx /usr/bin/npx; do
        if [ -f "$cand" ]; then
            NPX_BIN="$cand"
            break
        fi
    done
fi

OPCAO="${1:-}"
if [ -z "$OPCAO" ]; then
    echo "Escolha como deseja criar o túnel HTTPS gratuito:"
    echo "1) ⚡ Localtunnel (RECOMENDADO: Sem cadastro, 100% instantâneo)"
    echo "2) 🚀 Ngrok (Exige conta gratuita e Authtoken)"
    echo ""
    read -t 15 -p "Digite a opção (1 ou 2) [Padrão: 1]: " OPCAO || true
    OPCAO=${OPCAO:-1}
fi

if [ "$OPCAO" = "1" ] || [ "$OPCAO" = "--localtunnel" ]; then
    echo ""
    echo "======================================================="
    echo "⚡ Iniciando Localtunnel HTTPS para a porta 5000..."
    echo "======================================================="
    echo ""
    echo "📌 INSTRUÇÕES PARA O BLING ERP:"
    echo "1. Aguarde a linha 'your url is: https://xxxx.loca.lt' abaixo."
    echo "2. A URL para o seu Webhook no Bling será:"
    echo "   👉 https://xxxx.loca.lt/integrations/webhook"
    echo "3. Cadastre essa URL no Bling em: Preferências > Notificações/Webhooks."
    echo "4. Cole essa URL também na tela de Configurações do BlingBI."
    echo ""
    echo "Pressione Ctrl + C para encerrar o túnel."
    echo "======================================================="
    echo ""
    $NPX_BIN -y localtunnel --port 5000
    exit 0
fi

# Opção 2: Ngrok
NGROK_BIN=""
if command -v ngrok &> /dev/null; then
    NGROK_BIN="ngrok"
elif [ -f "./ngrok" ]; then
    NGROK_BIN="./ngrok"
else
    echo "⬇️  Baixando Ngrok oficial..."
    curl -s -O https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
    tar -xzf ngrok-v3-stable-linux-amd64.tgz
    rm -f ngrok-v3-stable-linux-amd64.tgz
    chmod +x ngrok
    NGROK_BIN="./ngrok"
fi

echo ""
echo "🔑 O Ngrok exige um Authtoken gratuito."
echo "Pegue seu token em: https://dashboard.ngrok.com/get-started/your-authtoken"
echo "Cole seu authtoken do Ngrok abaixo (ou pressione Enter se já adicionou):"
read -r user_token
if [ -n "$user_token" ]; then
    $NGROK_BIN config add-authtoken "$user_token"
    echo "✅ Authtoken configurado com sucesso!"
fi

echo ""
echo "======================================================="
echo "🚀 Iniciando túnel Ngrok HTTPS para a porta 5000..."
echo "📌 Copie a URL 'Forwarding' (https://xxxx.ngrok-free.app/integrations/webhook)"
echo "======================================================="
echo ""

$NGROK_BIN http 5000
