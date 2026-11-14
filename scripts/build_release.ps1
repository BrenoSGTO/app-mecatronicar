<#
.SYNOPSIS
  Gera os artefatos de release do MecatroniCar em dist\ (nunca versionados).

.DESCRIPTION
  1. Compila packaging\launcher.cs  -> dist\MecatroniCar.exe
  2. Monta dist\MecatroniCar-v<versao>.zip (arquivos do app + MecatroniCar.exe, layout plano)
     - e o asset que o updater.py baixa (download_url do version.json / GitHub Release).
  3. Compila packaging\Installer.cs embutindo o zip -> dist\Instalar-MecatroniCar.exe

  Usa o csc.exe do .NET Framework 4 que ja vem no Windows. Nao altera version.json,
  nao cria tag nem release: so gera arquivos locais.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
  powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Version 2.0.0
#>
param([string]$Version = "")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe" }
if (-not (Test-Path $csc)) { throw "csc.exe (.NET Framework 4) nao encontrado." }

if (-not $Version) { $Version = (Get-Content version.json -Raw -Encoding UTF8 | ConvertFrom-Json).version }

$dist = Join-Path $root "dist"
$stage = Join-Path $dist "stage"
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

Write-Host "[1/3] Compilando launcher (MecatroniCar.exe)..."
& $csc /nologo /target:winexe /optimize+ /win32icon:app_icon.ico `
    /out:"$dist\MecatroniCar.exe" /r:System.Windows.Forms.dll /r:System.Drawing.dll packaging\launcher.cs
if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar launcher.cs" }

Write-Host "[2/3] Montando zip de release v$Version..."
# Somente arquivos versionados necessarios em producao (sem testes, docs, planilhas de exemplo, packaging)
$files = git -c core.quotepath=off ls-files | Where-Object {
    $_ -notmatch '^(docs|packaging|planilhas_exemplo|\.issues)/' -and
    $_ -notmatch '^test_.*\.py$' -and
    $_ -notmatch '^(\.gitignore|apresentacao_pitch\.html|ROADMAP_V2\.md|RELEASE_V2\.0\.0\.md|gerar_massa_dados\.py)$' -and
    $_ -notmatch '^scripts/'
}
foreach ($f in $files) {
    $dest = Join-Path $stage $f
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Copy-Item -LiteralPath $f -Destination $dest
}
Copy-Item "$dist\MecatroniCar.exe" $stage
$zip = Join-Path $dist "MecatroniCar-v$Version.zip"
Compress-Archive -Path "$stage\*" -DestinationPath $zip -Force

Write-Host "[3/3] Compilando instalador (Instalar-MecatroniCar.exe)..."
& $csc /nologo /target:winexe /optimize+ /win32icon:app_icon.ico `
    /out:"$dist\Instalar-MecatroniCar.exe" /resource:"$zip,MecatroniCar.Package" `
    /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll `
    packaging\Installer.cs
if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar Installer.cs" }

Remove-Item $stage -Recurse -Force
Write-Host "`nPronto. Artefatos em dist\:"
Get-ChildItem $dist | ForEach-Object { "  {0}  ({1:N0} KB)" -f $_.Name, ($_.Length/1KB) }
