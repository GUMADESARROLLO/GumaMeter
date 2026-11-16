<#
  Compila SAC Estados en un solo ejecutable: dist\SAC-Estados.exe

  Uso:   .\build.ps1              crea el entorno, instala, prueba y compila
         .\build.ps1 -SinPruebas  omite pytest

  Se detiene en el primer paso que falle.
#>
param([switch]$SinPruebas)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Paso([string]$Titulo, [scriptblock]$Accion) {
    Write-Host "`n== $Titulo ==" -ForegroundColor Cyan
    & $Accion
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR en: $Titulo (código $LASTEXITCODE)" -ForegroundColor Red
        exit 1
    }
}

$Py = ".\.venv\Scripts\python.exe"
$Uv = Get-Command uv -ErrorAction SilentlyContinue

if (-not (Test-Path $Py)) {
    Paso "Crear entorno virtual" {
        if ($Uv) { uv venv --python 3.11 .venv }
        else { python -m venv .venv }
    }
}

Paso "Comprobar versión de Python (3.11 o superior)" {
    & $Py -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
}

Paso "Instalar dependencias" {
    if ($Uv) { uv pip install --python $Py -r requirements-dev.txt }
    else { & $Py -m pip install --disable-pip-version-check -r requirements-dev.txt }
}

Paso "Generar el ícono" { & $Py tools\make_icon.py }

if (-not $SinPruebas) {
    Paso "Pruebas" { & $Py -m pytest -q }
}

# Si la app está abierta, Windows no deja reemplazar el .exe.
Get-Process -Name "SAC-Estados" -ErrorAction SilentlyContinue | Stop-Process -Force

Paso "Compilar con PyInstaller" {
    & $Py -m PyInstaller --noconfirm --clean SAC-Estados.spec
}

$Exe = Join-Path $PSScriptRoot "dist\SAC-Estados.exe"
if (-not (Test-Path $Exe)) {
    Write-Host "ERROR: no se generó $Exe" -ForegroundColor Red
    exit 1
}
$Mb = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
Write-Host "`nListo: $Exe ($Mb MB)" -ForegroundColor Green
