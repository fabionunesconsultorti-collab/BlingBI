@echo off
chcp 65001 > nul
title BlingBI - Painel Analitico Bling ERP

echo =======================================================
echo        🟢 BlingBI - Inicializador Local (Windows)
echo =======================================================

cd /d "%~dp0"

:: 1. Verifica se o Python esta instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERRO] Python nao foi encontrado no seu computador!
        echo Baixe e instale o Python em https://www.python.org/downloads/
        echo Certifique-se de marcar a opcao "Add Python to PATH" durante a instalacao.
        echo.
        pause
        exit /b 1
    )
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

:: 2. Cria o ambiente virtual caso nao exista
if not exist "venv" (
    echo [INFO] Criando ambiente virtual (venv)...
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    echo [INFO] Instalando dependencias do BlingBI...
    venv\Scripts\python -m pip install --upgrade pip
    venv\Scripts\pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b 1
    )
    echo [SUCESSO] Dependencias instaladas com sucesso!
)

:: 3. Libera a porta 5000 caso presa por execucao anterior
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do taskkill /f /pid %%a >nul 2>&1

:: 4. Inicia o servidor e abre no navegador
echo.
echo [INFO] Iniciando o servidor BlingBI...
echo O navegador abrira automaticamente em: http://127.0.0.1:5000
echo Pressione Ctrl + C no teclado para encerrar o servidor.
echo =======================================================
echo.

venv\Scripts\python.exe run.py

if %errorlevel% neq 0 (
    echo.
    echo O servidor foi finalizado ou ocorreu um erro.
    pause
)
