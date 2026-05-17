$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $root ".venv\Scripts\python.exe"
$out = Join-Path $root "uvicorn.out.log"
$err = Join-Path $root "uvicorn.err.log"

if (-not (Test-Path $python)) {
    throw "Python virtualenv not found at $python"
}

if ($env:PATH -and $env:Path -and $env:PATH -eq $env:Path) {
    Remove-Item Env:PATH -ErrorAction SilentlyContinue
}

$existing = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000") `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $out `
        -RedirectStandardError $err
}

Start-Sleep -Seconds 5
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5
