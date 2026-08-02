[CmdletBinding()]
param([ValidateSet('Llama','Model','Both','Temporary','Logs')][string]$Target = 'Both', [switch]$NonInteractive, [switch]$BackupConfiguration)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'scripts\optimus_ia_runtime.psm1') -Force
$paths = Get-OptimusIaPaths $PSScriptRoot
$map = @{ Llama=@($paths.Llama); Model=@($paths.Model); Both=@($paths.Llama,$paths.Model); Temporary=@($paths.Downloads); Logs=@($paths.LlamaLogs,$paths.InstallerLogs) }
$targets = @($map[$Target] | Where-Object { Test-Path -LiteralPath $_ })
foreach ($path in $targets) { if (-not (Test-PathInsideRoot $path $paths.Root)) { throw "Ruta insegura rechazada: $path" } }
$size = ($targets | Get-ChildItem -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Write-Host "Se liberaran aproximadamente $size bytes. OPTIMUS, datasets, casos y Gold no forman parte de esta operacion."
if (-not $NonInteractive) { $answer = Read-Host "Eliminar $Target? [S/N]"; if ($answer -notmatch '^[sS]$') { exit 2 } }
if ($BackupConfiguration -and (Test-Path $paths.RuntimeEnv)) { Move-OptimusBackup $paths.RuntimeEnv $paths 'llama_runtime_config' | Out-Null }
foreach ($path in $targets) {
    if ((Get-Item -LiteralPath $path).LinkType) { throw "No se eliminan enlaces: $path" }
    Remove-Item -LiteralPath $path -Recurse -Force
}
Initialize-OptimusIaDirectories $paths
Write-Host 'Desinstalacion local completada.'
exit 0
