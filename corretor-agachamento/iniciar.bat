@echo off
rem Corretor de Agachamento - inicia o app no Windows (duplo clique)
chcp 65001 >nul
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    %PY% -m venv .venv || goto erro_python
)

if not exist ".venv\instalado.ok" (
    echo Instalando dependencias ^(so na primeira vez, pode levar alguns minutos^)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto erro_pip
    echo ok> ".venv\instalado.ok"
)

echo.
echo Abrindo o Corretor de Agachamento no navegador...
echo Para encerrar, feche esta janela ou aperte Ctrl+C.
echo.
".venv\Scripts\python.exe" app.py %*
pause
exit /b 0

:erro_python
echo.
echo Nao encontrei o Python. Instale o Python 3.10 ou mais recente em https://www.python.org/downloads/
echo e marque a opcao "Add python.exe to PATH" na instalacao. Depois rode este arquivo de novo.
pause
exit /b 1

:erro_pip
echo.
echo Falha ao instalar as dependencias. Verifique a conexao com a internet e rode este arquivo de novo.
pause
exit /b 1
