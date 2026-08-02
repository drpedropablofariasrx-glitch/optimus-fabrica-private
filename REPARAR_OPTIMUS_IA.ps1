[CmdletBinding()]
param([switch]$NonInteractive)
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'INSTALAR_OPTIMUS_IA.ps1'
$arguments = @('-Repair')
if ($NonInteractive) { $arguments += '-NonInteractive' }
Write-Host 'Reparacion: solo se descargaran componentes ausentes o que no superen la validacion.'
& $installer @arguments
exit $LASTEXITCODE
