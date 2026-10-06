@echo off
chcp 65001 > nul
title BlingBI - Tunel HTTPS para Webhook (Windows)

echo =======================================================
echo        🌐 BlingBI - Tunel HTTPS para Webhook (Windows)
echo =======================================================
echo.
echo Escolha como deseja criar o tunel HTTPS gratuito:
echo 1) ⚡ Localtunnel (RECOMENDADO: Sem cadastro, 100%% instantaneo via npx)
echo 2) 🚀 Ngrok (Exige Authtoken gratuito)
echo.
set /p OPCAO=Digite a opcao (1 ou 2) [Padrao: 1]: 
if "%OPCAO%"=="" set OPCAO=1

if "%OPCAO%"=="1" (
    echo.
    echo =======================================================
    echo ⚡ Iniciando Localtunnel HTTPS para a porta 5000...
    echo =======================================================
    echo.
    echo 📌 INSTRUCOES PARA O BLING ERP:
    echo 1. Aguarde a linha "your url is: https://xxxx.loca.lt" abaixo.
    echo 2. A sua URL de Webhook sera:
    echo    👉 https://xxxx.loca.lt/integrations/webhook
    echo 3. Cadastre essa URL no Bling em: Preferencias > Notificacoes/Webhooks.
    echo.
    echo Pressione Ctrl + C para encerrar o tunel a qualquer momento.
    echo =======================================================
    echo.
    npx -y localtunnel --port 5000
    goto fim
)

:: Opcao 2: Ngrok
cd /d "%~dp0"
set NGROK_CMD=ngrok
where ngrok >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%~dp0ngrok.exe" (
        set NGROK_CMD="%~dp0ngrok.exe"
    ) else (
        echo [INFO] Baixando ngrok para Windows...
        curl -s -L -o ngrok.zip https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip
        tar -xf ngrok.zip
        del ngrok.zip
        set NGROK_CMD="%~dp0ngrok.exe"
    )
)

echo.
echo [CONFIGURACAO NGROK]
echo Obtenha seu token em: https://dashboard.ngrok.com/get-started/your-authtoken
echo Cole seu Authtoken abaixo (ou pressione Enter se ja configurou):
set /p TOKEN=Authtoken: 
if not "%TOKEN%"=="" (
    %NGROK_CMD% config add-authtoken %TOKEN%
    echo [SUCESSO] Authtoken salvo!
)

echo.
echo 🚀 Iniciando tunel Ngrok HTTPS para a porta 5000...
echo 📌 Copie a URL Forwarding (https://xxxx.ngrok-free.app/integrations/webhook)
echo.
%NGROK_CMD% http 5000

:fim
pause
