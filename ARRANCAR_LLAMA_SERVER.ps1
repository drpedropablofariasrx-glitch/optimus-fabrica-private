[CmdletBinding()]
param([switch]$NoRun)

function Invoke-LlamaServerNative {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory = $false)][AllowEmptyCollection()][string[]]$Arguments = @(),
        [Parameter(Mandatory)][string]$LogPath
    )

    # El .cmd une stderr y stdout antes de que Windows PowerShell 5.1 pueda crear
    # NativeCommandError. La invocacion sigue siendo directa y Ctrl+C llega al proceso.
    $wrapperPath = Join-Path $env:TEMP ('optimus_llama_server_{0}_{1}.cmd' -f $PID, [guid]::NewGuid().ToString('N'))
    $exitCode = $null
    try {
        $commandParts = (@($FilePath) + @($Arguments)) | ForEach-Object { '"{0}"' -f $_.Replace('"', '""') }
        $wrapperContent = "@echo off`r`n$($commandParts -join ' ') 2>&1`r`nexit /b %ERRORLEVEL%`r`n"
        Set-Content -LiteralPath $wrapperPath -Value $wrapperContent -Encoding Ascii
        & $wrapperPath | Tee-Object -FilePath $LogPath
        $exitCode = $LASTEXITCODE
    } finally {
        if (Test-Path -LiteralPath $wrapperPath) { Remove-Item -LiteralPath $wrapperPath -Force }
    }
    if ($exitCode -ne 0) { throw "llama-server finalizo con codigo de salida $exitCode." }
}

if ($NoRun) { return }

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'scripts\optimus_ia_runtime.psm1') -Force
$paths = Get-OptimusIaPaths $PSScriptRoot
$cfg = Read-LlamaRuntimeEnv $paths
if ($cfg.OPTIMUS_LLAMA_HOST -ne '127.0.0.1') { throw 'Por seguridad el servidor debe limitarse a 127.0.0.1.' }
if (-not (Test-Path -LiteralPath $cfg.OPTIMUS_LLAMA_SERVER_EXE)) { throw 'No existe llama-server.exe.' }
if (-not (Test-GgufFile $cfg.OPTIMUS_LLAMA_MODEL_PATH)) { throw 'El modelo GGUF no es valido.' }
$port = [int]$cfg.OPTIMUS_LLAMA_PORT
$listener = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($listener) { throw "El puerto $port ya esta ocupado; compruebelo antes de iniciar." }
$help = & $cfg.OPTIMUS_LLAMA_SERVER_EXE '--help' 2>&1 | Out-String
$args = @('-m', $cfg.OPTIMUS_LLAMA_MODEL_PATH, '--host', '127.0.0.1', '--port', $port, '-c', $cfg.OPTIMUS_LLAMA_CTX_SIZE, '-ngl', $cfg.OPTIMUS_LLAMA_GPU_LAYERS, '-t', $cfg.OPTIMUS_LLAMA_THREADS)
if ($cfg.OPTIMUS_LLAMA_DISABLE_THINKING -eq 'true' -and $help -match '(?m)--reasoning') { $args += '--reasoning'; $args += 'off' }
if ($cfg.OPTIMUS_LLAMA_FLASH_ATTENTION -eq 'true' -and $help -match '(?m)--flash-attn') { $args += '--flash-attn'; $args += 'on' }
$log = Join-Path $paths.LlamaLogs ('llama_server_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
Write-Host "Iniciando llama-server solo en 127.0.0.1:$port. Detenga con Ctrl+C. Log: $log"
Invoke-LlamaServerNative -FilePath $cfg.OPTIMUS_LLAMA_SERVER_EXE -Arguments $args -LogPath $log
exit 0
