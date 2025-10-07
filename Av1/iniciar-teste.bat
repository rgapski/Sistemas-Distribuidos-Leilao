@echo off
REM Script para iniciar todos os componentes do sistema de leilão no Windows.
REM Execute este arquivo com um duplo-clique a partir da raiz do projeto.

echo Iniciando o sistema de leilao em janelas separadas...
echo.

REM -- Passo 1: Inicia os dois clientes TUI --
echo [1/5] Iniciando cliente_alpha...
start "Cliente Alpha" cmd /c "cd cliente_tui && python app.py cliente_alpha"

echo [2/5] Iniciando cliente_beta...
start "Cliente Beta" cmd /c "cd cliente_tui && python app.py cliente_beta"


REM -- Passo 3: Aguarda 1 segundo --
echo      Aguardando 1 segundo...
timeout /t 2 /nobreak > nul


REM -- Passo 4: Inicia o microsservico de Lances --
echo [4/5] Iniciando MS Lance...
start "MS Lance" cmd /c "cd microservices\ms_lance && python main.py"


REM -- Passo 5: Aguarda 1 segundo --
echo      Aguardando 1 segundo...
timeout /t 2 /nobreak > nul

REM -- Passo 2: Inicia o microsservico de Notificacao --
echo [3/5] Iniciando MS Notificacao...
start "MS Notificacao" cmd /c "cd microservices\ms_notification && python main.py"

REM -- Passo 5: Aguarda 1 segundo --
echo      Aguardando 1 segundo...
timeout /t 2 /nobreak > nul

REM -- Passo 6: Inicia o microsservico de Leilao (o "gatilho" do sistema) --
echo [5/5] Iniciando MS Leilao...
start "MS Leilao" cmd /c "cd microservices\ms_leilao && python main.py"

echo.
echo Sistema iniciado! Verifique as 5 novas janelas que foram abertas.
