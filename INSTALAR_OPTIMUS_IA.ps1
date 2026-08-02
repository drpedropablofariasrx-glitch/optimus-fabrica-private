[CmdletBinding()]
param(
    [switch]$NonInteractive, [switch]$SkipLlama, [switch]$SkipModel, [switch]$ForceRedownload,
    [switch]$Repair, [switch]$VerifyOnly, [switch]$StartServerAfterInstall, [switch]$RunNonClinicalTest,
    [switch]$NoCudaFallback
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'scripts\optimus_ia_runtime.psm1') -Force
$paths = Get-OptimusIaPaths $PSScriptRoot
Initialize-OptimusIaDirectories $paths
$log = New-InstallerLog $paths
$defaultLlamaArchiveEstimateBytes = 1GB
$defaultQwenEstimateBytes = 6GB

try {
    Test-OptimusWindowsX64 | Out-Null
    $gpu = Get-OptimusGpuInfo
    $release = if ($SkipLlama) { $null } else { Get-OfficialLlamaRelease }
    $selection = if ($release) { Select-LlamaCuda12Assets $release } else { $null }
    if (-not $SkipLlama -and -not $selection) {
        $alternatives = (Get-LlamaAlternativeAssets $release) -join ', '
        throw "No existe un asset Windows x64 CUDA 12 compatible. Alternativas: $alternatives"
    }
    $qwen = if ($SkipModel) { $null } else { Get-QwenOfficialMetadata }
    $estimated = 3GB
    if ($selection) {
        $binaryUrl = Get-SafeObjectProperty $selection.Binary @('browser_download_url') ''
        $binarySize = Get-RemoteSizeInfo $selection.Binary $binaryUrl 'GitHub'
        if ($null -eq $binarySize.Size) { $binarySize = [pscustomobject]@{ Size = $defaultLlamaArchiveEstimateBytes; Method = 'safe llama.cpp estimate' }; Write-InstallerLog $log 'No se pudo obtener el tamaño remoto del asset de llama.cpp. Se utilizara una estimacion segura.' }
        $estimated += [int64]$binarySize.Size * 2
        Write-InstallerLog $log "Tamano llama.cpp: $($binarySize.Size) ($($binarySize.Method)); propiedades: $($selection.Binary.PSObject.Properties.Name -join ',')"
        if ($selection.CudaRuntime) {
            $cudaUrl = Get-SafeObjectProperty $selection.CudaRuntime @('browser_download_url') ''
            $cudaSize = Get-RemoteSizeInfo $selection.CudaRuntime $cudaUrl 'GitHub'
            if ($null -eq $cudaSize.Size) { $cudaSize = [pscustomobject]@{ Size = $defaultLlamaArchiveEstimateBytes; Method = 'safe CUDA runtime estimate' }; Write-InstallerLog $log 'No se pudo obtener el tamaño remoto de CUDA runtime. Se utilizara una estimacion segura.' }
            $estimated += [int64]$cudaSize.Size
            Write-InstallerLog $log "Tamano CUDA runtime: $($cudaSize.Size) ($($cudaSize.Method)); propiedades: $($selection.CudaRuntime.PSObject.Properties.Name -join ',')"
        }
    }
    if ($qwen) {
        $qwenSize = Get-SafeObjectProperty $qwen @('Size') $null
        if ($null -eq $qwenSize -or [int64]$qwenSize -le 0) { $qwenSize = $defaultQwenEstimateBytes; Write-InstallerLog $log 'No se pudo obtener el tamaño remoto del modelo Qwen. Se utilizara una estimacion segura de 6 GB.' }
        $estimated += [int64]$qwenSize
        Write-InstallerLog $log "Tamano Qwen: $qwenSize ($($qwen.SizeMethod)); propiedades: $($qwen.PSObject.Properties.Name -join ',')"
    }
    $space = Test-OptimusDiskSpace ($estimated + 3GB) $paths.Root
    Write-InstallerLog $log "GPU NVIDIA: $($gpu.Nvidia); nombre: $($gpu.Name); driver: $($gpu.Driver)"
    if ($selection) { Write-InstallerLog $log "llama.cpp release $(Get-SafeObjectProperty $release @('tag_name') 'desconocida') ($(Get-SafeObjectProperty $release @('published_at') 'fecha desconocida')); asset: $(Get-SafeObjectProperty $selection.Binary @('name') 'sin nombre'); URL: $(Get-SafeObjectProperty $selection.Binary @('browser_download_url') 'sin URL')" }
    if ($qwen) { Write-InstallerLog $log "Qwen: $($qwen.Repository)/$($qwen.FileName); revision: $($qwen.Revision); URL: $($qwen.Url)" }
    Write-InstallerLog $log "Disco $($space.Drive): libre=$($space.FreeBytes), requerido=$($space.RequiredBytes), suficiente=$($space.Sufficient)"
    if (-not $space.Sufficient) { throw 'Espacio insuficiente: se requiere el total estimado mas 3 GB de margen.' }
    if ($VerifyOnly) { Write-InstallerLog $log 'VerifyOnly completado: no se descargo ni modifico nada.'; exit 0 }
    if (-not $NonInteractive) { $answer = Read-Host 'Continuar con la instalacion? [S/N]'; if ($answer -notmatch '^[sS]$') { Write-InstallerLog $log 'Instalacion cancelada por el usuario.'; exit 2 } }

    if (-not $SkipLlama) {
        $archive = Join-Path $paths.Downloads (Get-SafeObjectProperty $selection.Binary @('name') 'llama_cpp_asset.zip')
        if ($ForceRedownload -and (Test-Path $archive)) { Move-OptimusBackup $archive $paths 'forced_download' | Out-Null }
        if (-not (Test-Path $archive)) { Get-DownloadFile (Get-SafeObjectProperty $selection.Binary @('browser_download_url') '') $archive | Out-Null }
        $archives = @($archive)
        if ($selection.CudaRuntime) { $cuda = Join-Path $paths.Downloads (Get-SafeObjectProperty $selection.CudaRuntime @('name') 'llama_cuda_runtime.zip'); if (-not (Test-Path $cuda)) { Get-DownloadFile (Get-SafeObjectProperty $selection.CudaRuntime @('browser_download_url') '') $cuda | Out-Null }; $archives += $cuda }
        $server = Expand-LlamaInstallation $archives $paths
        Write-InstallerLog $log "llama-server validado: $($server.FullName)"
    } else { $server = Get-ChildItem -Path $paths.Llama -Filter llama-server.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 }

    if (-not $SkipModel) {
        $valid = (Test-Path $paths.Model) -and (Test-GgufFile $paths.Model)
        if ($ForceRedownload -or -not $valid) {
            if (Test-Path $paths.Model) { Move-OptimusBackup $paths.Model $paths 'invalid_or_forced_model' | Out-Null }
            Get-DownloadFile $qwen.Url $paths.Model | Out-Null
        }
        if (-not (Test-GgufFile $paths.Model)) { throw 'El modelo descargado no supera la validacion GGUF.' }
        Write-InstallerLog $log "Modelo GGUF validado: $($paths.Model); SHA256=$(Get-Sha256 $paths.Model)"
    }
    if (-not $server) { throw 'No se encontro llama-server.exe para crear la configuracion.' }
    Write-LlamaRuntimeEnv $paths $server.FullName
    Write-InstallerLog $log "Configuracion local creada: $($paths.RuntimeEnv)"
    if ($StartServerAfterInstall) { & (Join-Path $PSScriptRoot 'ARRANCAR_LLAMA_SERVER.ps1') }
    if ($RunNonClinicalTest) { & (Join-Path $PSScriptRoot 'COMPROBAR_LLAMA_SERVER.ps1') -TestGeneration }
    Write-InstallerLog $log 'Instalacion finalizada correctamente. OPTIMUS no se ha iniciado.'
    exit 0
} catch {
    Write-InstallerLog $log "ERROR: $($_.Exception.Message)"
    Write-Host "Informe: $log"
    exit 1
}
