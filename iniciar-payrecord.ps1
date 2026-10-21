<#
    Inicia PayRecord completo con un solo comando:
    valida el entorno, asegura que MySQL este disponible, levanta el
    servidor de Django en una ventana aparte y abre el navegador cuando
    la aplicacion ya responde.

    Uso:
        powershell -ExecutionPolicy Bypass -File .\iniciar-payrecord.ps1

    O desde VS Code: Ctrl+Shift+B (tarea "Iniciar PayRecord").
#>

$ErrorActionPreference = "Stop"

function Test-Puerto {
    param([int]$Puerto)
    $conexion = Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conexion
}

# --- 1. Ubicarse en la raiz correcta del proyecto, sin importar desde donde se invoque ---
$raiz = $PSScriptRoot
Set-Location $raiz

if (-not (Test-Path (Join-Path $raiz "manage.py"))) {
    Write-Host "No se encontro manage.py en $raiz." -ForegroundColor Red
    Write-Host "Este script debe quedarse en la raiz del proyecto PayRecord." -ForegroundColor Red
    exit 1
}

$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No se encontro el entorno virtual en .venv\Scripts\python.exe." -ForegroundColor Red
    Write-Host "Crealo con:      python -m venv .venv" -ForegroundColor Yellow
    Write-Host "Instala luego:   .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path (Join-Path $raiz ".env"))) {
    Write-Host "No se encontro .env en la raiz del proyecto. Sin el, Django no puede arrancar." -ForegroundColor Red
    Write-Host "Copia .env.example a .env y completa los valores (ver docs\instalacion-en-otro-equipo.md)." -ForegroundColor Yellow
    exit 1
}

Write-Host "=== PayRecord ===" -ForegroundColor Cyan
Write-Host "Raiz del proyecto: $raiz"
Write-Host "PayRecord no usa un frontend independiente: Django sirve toda la interfaz."
Write-Host ""

# --- 2. Base de datos: MySQL debe estar disponible antes de levantar Django ---
$servicioMysql = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
if ($servicioMysql) {
    if ($servicioMysql.Status -ne "Running") {
        Write-Host "El servicio MySQL80 no esta activo. Intentando iniciarlo..." -ForegroundColor Yellow
        try {
            Start-Service -Name "MySQL80"
            Write-Host "Servicio MySQL80 iniciado." -ForegroundColor Green
        } catch {
            Write-Host "No se pudo iniciar el servicio MySQL80 automaticamente: $_" -ForegroundColor Red
            Write-Host "Inicialo manualmente (services.msc, puede requerir permisos de administrador) y vuelve a ejecutar este script." -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "MySQL80 ya esta en ejecucion." -ForegroundColor Green
    }
} else {
    Write-Host "No se encontro el servicio de Windows 'MySQL80'." -ForegroundColor Yellow
    Write-Host "Si usas MySQL de otra forma (XAMPP, Docker, instalacion manual), asegurate de que este activo en 127.0.0.1:3306 antes de continuar." -ForegroundColor Yellow
}

Write-Host "Esperando a que la base de datos responda en 127.0.0.1:3306..."
$intentos = 0
while (-not (Test-Puerto 3306) -and $intentos -lt 20) {
    Start-Sleep -Milliseconds 500
    $intentos++
}
if (-not (Test-Puerto 3306)) {
    Write-Host "La base de datos no respondio en el puerto 3306 tras 10 segundos." -ForegroundColor Red
    Write-Host "PayRecord no podra conectarse. Revisa que MySQL este corriendo y vuelve a intentar." -ForegroundColor Red
    exit 1
}
Write-Host "Base de datos disponible." -ForegroundColor Green
Write-Host ""

# --- 3. Backend Django ---
$puertoDjango = 8000
$urlApp = "http://127.0.0.1:$puertoDjango/"

if (Test-Puerto $puertoDjango) {
    Write-Host "Ya hay un servicio escuchando en 127.0.0.1:$puertoDjango -- no se inicia otro servidor." -ForegroundColor Yellow
} else {
    Write-Host "Verificando la configuracion de Django (manage.py check)..."
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) {
        Write-Host "manage.py check reporto errores. Revisa el mensaje anterior antes de continuar." -ForegroundColor Red
        exit 1
    }
    Write-Host "Configuracion valida." -ForegroundColor Green
    Write-Host ""

    Write-Host "Iniciando el servidor de Django en una ventana aparte..." -ForegroundColor Cyan
    Start-Process powershell -WindowStyle Normal -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$raiz'; & '$python' manage.py runserver 127.0.0.1:$puertoDjango"
    )

    Write-Host "Esperando a que PayRecord responda en $urlApp..."
    $intentos = 0
    while (-not (Test-Puerto $puertoDjango) -and $intentos -lt 40) {
        Start-Sleep -Milliseconds 500
        $intentos++
    }
    if (-not (Test-Puerto $puertoDjango)) {
        Write-Host "El backend no respondio en el puerto $puertoDjango tras 20 segundos." -ForegroundColor Red
        Write-Host "Revisa la ventana del servidor que se abrio: ahi deberia verse el error." -ForegroundColor Red
        exit 1
    }
    Write-Host "Backend listo." -ForegroundColor Green
}

Write-Host ""
Write-Host "PayRecord esta listo." -ForegroundColor Green
Write-Host "Aplicacion:  $urlApp"
Write-Host ""

Start-Process $urlApp

Write-Host "Para detener PayRecord: cierra la ventana del servidor, o entra en ella y presiona Ctrl+C." -ForegroundColor Cyan
