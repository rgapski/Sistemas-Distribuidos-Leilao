@echo off
REM Arquivo: start_peers.bat
REM Script para iniciar os 4 peers em janelas separadas com cores diferentes

title Launcher de Peers
color 0E

echo ========================================
echo Iniciando Sistema Distribuido
echo ========================================
echo.

echo [1/4] Iniciando PeerA (Verde)...
start "PeerA" cmd /k "title PeerA && python main.py PeerA"
timeout /t 1 /nobreak >nul

echo [2/4] Iniciando PeerB (Ciano)...
start "PeerB" cmd /k "title PeerB && python main.py PeerB"
timeout /t 1 /nobreak >nul

echo [3/4] Iniciando PeerC (Vermelho)...
start "PeerC" cmd /k "title PeerC && python main.py PeerC"
timeout /t 1 /nobreak >nul

echo [4/4] Iniciando PeerD (Roxo)...
start "PeerD" cmd /k "title PeerD && python main.py PeerD"
timeout /t 1 /nobreak >nul

echo.
echo ========================================
echo Todos os peers foram iniciados!
echo ========================================
echo.
echo Cores dos terminais:
echo   PeerA: Verde
echo   PeerB: Ciano
echo   PeerC: Vermelho
echo   PeerD: Roxo
echo.
echo Posicione as janelas manualmente conforme desejar.
echo.
echo Pressione qualquer tecla para fechar este launcher...
echo (As janelas dos peers continuarao abertas)
pause >nul