@echo off
chcp 65001 > nul
title Instalador MecatroniCar - Oficina Mecânica

echo ====================================================================
echo             MecatroniCar - Instalador Oficial
echo ====================================================================
echo.

set "SOURCE_DIR=%~dp0"
set "TARGET_DIR=%LOCALAPPDATA%\Programs\MecatroniCar"

echo [1/4] Copiando arquivos para "%TARGET_DIR%"...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
xcopy /E /Y /I "%SOURCE_DIR%*" "%TARGET_DIR%\" > nul

echo [2/4] Verificando motor Python no computador...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$py = Get-ChildItem -Path \"$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe\", \"$env:ProgramFiles\Python3*\python.exe\" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName; " ^
  "if (-not $py) { " ^
  "  Write-Host 'Instalando Python 3.12 automaticamente (aguarde ~1 minuto)...'; " ^
  "  try { winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null } catch {} " ^
  "  $py = Get-ChildItem -Path \"$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe\", \"$env:ProgramFiles\Python3*\python.exe\" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName; " ^
  "} " ^
  "if (-not $py) { " ^
  "  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
  "  $p = Join-Path $env:TEMP 'python-setup.exe'; " ^
  "  Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile $p; " ^
  "  Start-Process -FilePath $p -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 SimpleInstall=1' -Wait; " ^
  "  Remove-Item $p -Force -ErrorAction SilentlyContinue; " ^
  "  $py = Get-ChildItem -Path \"$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe\", \"$env:ProgramFiles\Python3*\python.exe\" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName; " ^
  "} " ^
  "if ($py) { " ^
  "  Write-Host '[3/4] Instalando bibliotecas necessarias (Flask, Excel)...'; " ^
  "  & $py -m pip install --disable-pip-version-check --quiet openpyxl xlrd flask; " ^
  "  Set-Location \"$env:LOCALAPPDATA\Programs\MecatroniCar\"; " ^
  "  & $py -c 'import cache, config, parser, server, updater; cache.init_db()'; " ^
  "  Write-Host '[4/4] Criando atalho na Area de Trabalho...'; " ^
  "  & $py criar_atalho_desktop.py; " ^
  "  Write-Host 'Abrindo o MecatroniCar...'; " ^
  "  Start-Process -FilePath $py -ArgumentList 'app.py' -WorkingDirectory \"$env:LOCALAPPDATA\Programs\MecatroniCar\" -WindowStyle Hidden; " ^
  "}"

echo.
echo ====================================================================
echo   Instalacao concluida com sucesso!
echo ====================================================================
timeout /t 2 > nul
exit

