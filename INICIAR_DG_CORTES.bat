@echo off
setlocal
cd /d "%~dp0"
echo =====================================
echo      DG CORTES - SERVIDOR LOCAL
 echo =====================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale o Python e marque Add Python to PATH.
  pause
  exit /b 1
)
py -c "import flask, PIL, dotenv" >nul 2>nul
if errorlevel 1 (
  echo Instalando as dependencias do projeto...
  py -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Nao foi possivel instalar as dependencias.
    pause
    exit /b 1
  )
)
echo Abrindo http://127.0.0.1:5000 ...
start "" "http://127.0.0.1:5000"
py app.py
pause
