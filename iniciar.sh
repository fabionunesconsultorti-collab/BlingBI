#!/usr/bin/env bash

# ==============================================================================
# BlingBI - Script de Inicialização Facilitada (Linux / macOS)
# ==============================================================================

set -e

# Garante que o script execute no diretório onde ele está localizado
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "======================================================="
echo "       🟢 BlingBI - Inicializador Local (Linux)        "
echo "======================================================="

# 1. Verifica se o Python 3 está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Erro: Python 3 não foi encontrado no sistema."
    echo "Instale o Python 3 e tente novamente."
    exit 1
fi

# 2. Cria o ambiente virtual caso não exista
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual (venv)..."
    python3 -m venv venv
    echo "⬇️  Instalando dependências do projeto..."
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
    echo "✅ Dependências instaladas com sucesso!"
fi

# 3. Libera a porta 5000 caso esteja presa por execução anterior
if command -v fuser &> /dev/null; then
    fuser -k 5000/tcp 2>/dev/null || true
fi

# 4. Executa a aplicação com o Python do venv
echo "🚀 Iniciando BlingBI..."
echo "A interface abrirá automaticamente no seu navegador padrão."
echo "Para encerrar o servidor a qualquer momento, pressione Ctrl + C."
echo "======================================================="

./venv/bin/python run.py
