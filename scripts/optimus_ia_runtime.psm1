Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:OfficialLlamaApi = 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest'
$script:OfficialQwenApi = 'https://huggingface.co/api/models/Qwen/Qwen3-8B-GGUF'
$script:QwenRepository = 'Qwen/Qwen3-8B-GGUF'
$script:QwenFileName = 'Qwen3-8B-Q4_K_M.gguf'
$script:DefaultQwenEstimateBytes = 6GB
$script:DefaultLlamaArchiveEstimateBytes = 1GB

function Get-SafeObjectProperty {
    param(
        [Parameter(Mandatory = $false)][AllowNull()][object]$Object,
        [Parameter(Mandatory = $true)][string[]]$PropertyNames,
        $DefaultValue = $null
    )
    if ($null -eq $Object) { return $DefaultValue }
    foreach ($propertyName in $PropertyNames) {
        if ($Object -is [Collections.IDictionary] -and $Object.Contains($propertyName) -and $null -ne $Object[$propertyName]) {
            return $Object[$propertyName]
        }
        $property = $Object.PSObject.Properties[$propertyName]
        if ($null -ne $property -and $null -ne $property.Value) { return $property.Value }
    }
    return $DefaultValue
}

function Get-RemoteContentLengthSafely {
    param([Parameter(Mandatory = $false)][AllowNull()][string]$Url)
    if ([string]::IsNullOrWhiteSpace($Url)) { return [pscustomobject]@{ Size = $null; Method = 'URL unavailable' } }
    $headers = @{ 'User-Agent' = 'OPTIMUS-local-installer' }
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Head -Headers $headers -MaximumRedirection 5 -UseBasicParsing -ErrorAction Stop
        $length = Get-SafeObjectProperty $response.Headers @('Content-Length', 'content-length') $null
        if ($null -ne $length -and [int64]$length -gt 0) { return [pscustomobject]@{ Size = [int64]$length; Method = 'HEAD Content-Length' } }
    } catch { }
    try {
        $response = Invoke-WebRequest -Uri $Url -Headers (@{ 'User-Agent' = 'OPTIMUS-local-installer'; Range = 'bytes=0-0' }) -MaximumRedirection 5 -UseBasicParsing -ErrorAction Stop
        $contentRange = Get-SafeObjectProperty $response.Headers @('Content-Range', 'content-range') $null
        if ($contentRange -match '/(\d+)$') { return [pscustomobject]@{ Size = [int64]$Matches[1]; Method = 'Range Content-Range' } }
        $length = Get-SafeObjectProperty $response.Headers @('Content-Length', 'content-length') $null
        if ($null -ne $length -and [int64]$length -gt 1) { return [pscustomobject]@{ Size = [int64]$length; Method = 'Range Content-Length' } }
    } catch { }
    return [pscustomobject]@{ Size = $null; Method = 'unavailable' }
}

function Get-RemoteSizeInfo {
    param([Parameter(Mandatory = $false)][AllowNull()][object]$Object, [Parameter(Mandatory = $false)][AllowNull()][string]$Url, [string]$Source = 'remote')
    if ($null -eq $Object) {
        $remote = Get-RemoteContentLengthSafely $Url
        if ($remote.Size) { $remote.Method = "$Source $($remote.Method) without metadata" }
        return $remote
    }
    $direct = Get-SafeObjectProperty $Object @('size', 'size_bytes', 'filesize', 'file_size') $null
    if ($null -ne $direct -and [int64]$direct -gt 0) { return [pscustomobject]@{ Size = [int64]$direct; Method = "$Source property" } }
    $lfs = Get-SafeObjectProperty $Object @('lfs') $null
    $lfsSize = Get-SafeObjectProperty $lfs @('size', 'size_bytes', 'filesize', 'file_size') $null
    if ($null -ne $lfsSize -and [int64]$lfsSize -gt 0) { return [pscustomobject]@{ Size = [int64]$lfsSize; Method = "$Source lfs.size" } }
    $xet = Get-SafeObjectProperty $Object @('xetFileData', 'xet_file_data') $null
    $xetSize = Get-SafeObjectProperty $xet @('size', 'size_bytes', 'filesize', 'file_size') $null
    if ($null -ne $xetSize -and [int64]$xetSize -gt 0) { return [pscustomobject]@{ Size = [int64]$xetSize; Method = "$Source xetFileData.size" } }
    return Get-RemoteContentLengthSafely $Url
}

function Get-OptimusProjectRoot {
    param([string]$StartPath = $PSScriptRoot)
    $path = (Resolve-Path $StartPath).Path
    while ($true) {
        if ((Test-Path (Join-Path $path '00_APP\optimus_app.py')) -and (Test-Path (Join-Path $path 'README.md'))) { return $path }
        $parent = Split-Path -Parent $path
        if ($parent -eq $path -or -not $parent) { throw 'No se encontro la raiz de OPTIMUS.' }
        $path = $parent
    }
}

function Get-OptimusIaPaths {
    param([string]$Root = (Get-OptimusProjectRoot))
    return [ordered]@{
        Root = $Root; Runtime = Join-Path $Root 'runtime'; Llama = Join-Path $Root 'runtime\llama_cpp'
        Downloads = Join-Path $Root 'runtime\downloads'; Backups = Join-Path $Root 'runtime\backups'
        ModelDir = Join-Path $Root 'models\qwen'; Model = Join-Path $Root ('models\qwen\' + $script:QwenFileName)
        LlamaLogs = Join-Path $Root 'logs\llama_cpp'; InstallerLogs = Join-Path $Root 'logs\installer'
        LocalConfig = Join-Path $Root 'config\local'; RuntimeEnv = Join-Path $Root 'config\local\llama_runtime.env'
    }
}

function Initialize-OptimusIaDirectories {
    param([hashtable]$Paths = (Get-OptimusIaPaths))
    @($Paths.Runtime, $Paths.Llama, $Paths.Downloads, $Paths.Backups, $Paths.ModelDir, $Paths.LlamaLogs, $Paths.InstallerLogs, $Paths.LocalConfig) |
        ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }
}

function New-InstallerLog {
    param([hashtable]$Paths = (Get-OptimusIaPaths))
    Initialize-OptimusIaDirectories $Paths
    return Join-Path $Paths.InstallerLogs ('install_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
}

function Write-InstallerLog {
    param([string]$LogPath, [string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 's'), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Host $Message
}

function Test-OptimusWindowsX64 {
    if ($env:OS -ne 'Windows_NT') { throw 'Este instalador solo admite Windows.' }
    if ([Environment]::Is64BitOperatingSystem -ne $true) { throw 'Se requiere Windows x64.' }
    return $true
}

function Get-OptimusGpuInfo {
    $info = [ordered]@{ Nvidia = $false; Driver = $null; Name = $null }
    $command = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($command) {
        try {
            $rows = & $command.Source '--query-gpu=name,driver_version' '--format=csv,noheader' 2>$null
            if ($LASTEXITCODE -eq 0 -and $rows) {
                $parts = $rows[0].Split(',').Trim()
                $info.Nvidia = $true; $info.Name = $parts[0]; $info.Driver = $parts[1]
            }
        } catch { }
    }
    return [pscustomobject]$info
}

function Get-OfficialLlamaRelease {
    param([string]$ApiUrl = $script:OfficialLlamaApi)
    return Invoke-RestMethod -Uri $ApiUrl -Headers @{ 'User-Agent' = 'OPTIMUS-local-installer' } -TimeoutSec 30
}

function Select-LlamaCuda12Assets {
    param([Parameter(Mandatory = $false)][AllowNull()][object]$Release)
    $assets = @(Get-SafeObjectProperty $Release @('assets') @())
    $candidate = @($assets | Where-Object {
        $_.name -match '^llama-.*-bin-win-cuda-12\..*-x64\.zip$' -and $_.name -notmatch '(cpu|vulkan|arm|hip|sycl|openvino|cuda-13)'
    } | Sort-Object name | Select-Object -First 1)
    if ($candidate.Count -eq 0) { return $null }
    $runtime = @($assets | Where-Object {
        $_.name -match '^cudart-llama-bin-win-cuda-12\..*-x64\.zip$' -and $_.name -notmatch '(cpu|vulkan|arm|hip|sycl|openvino|cuda-13)'
    } | Sort-Object name | Select-Object -First 1)
    return [pscustomobject]@{ Binary = $candidate[0]; CudaRuntime = if ($runtime) { $runtime[0] } else { $null }; Release = $Release }
}

function Get-LlamaAlternativeAssets {
    param([Parameter(Mandatory = $false)][AllowNull()][object]$Release)
    return @(Get-SafeObjectProperty $Release @('assets') @() | Where-Object { $_.name -match 'win.*x64.*zip|win.*zip' } | ForEach-Object { $_.name })
}

function Get-QwenOfficialMetadata {
    param([string]$ApiUrl = $script:OfficialQwenApi)
    $metadata = Invoke-RestMethod -Uri $ApiUrl -Headers @{ 'User-Agent' = 'OPTIMUS-local-installer' } -TimeoutSec 30
    $siblings = @(Get-SafeObjectProperty $metadata @('siblings') @())
    $matches = @($siblings | Where-Object { (Get-SafeObjectProperty $_ @('rfilename', 'filename') '') -eq $script:QwenFileName })
    if ($matches.Count -eq 0) { throw "No se localizaron los metadatos del archivo Qwen solicitado ($script:QwenFileName) en $script:QwenRepository." }
    $file = $matches[0]
    $url = "https://huggingface.co/$($script:QwenRepository)/resolve/main/$($script:QwenFileName)?download=true"
    $sizeInfo = Get-RemoteSizeInfo $file $url 'Hugging Face'
    return [pscustomobject]@{
        Repository = $script:QwenRepository; FileName = $script:QwenFileName; Revision = Get-SafeObjectProperty $metadata @('sha', 'revision') $null
        Size = $sizeInfo.Size; SizeMethod = $sizeInfo.Method; LfsOid = Get-SafeObjectProperty (Get-SafeObjectProperty $file @('lfs') $null) @('oid') $null; Url = $url
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-GgufFile {
    param([Parameter(Mandatory)][string]$Path, [Int64]$MinimumBytes = 1073741824)
    if ((Split-Path -Leaf $Path) -ne $script:QwenFileName -or [IO.Path]::GetExtension($Path) -ne '.gguf') { return $false }
    if (-not (Test-Path -LiteralPath $Path) -or (Get-Item -LiteralPath $Path).Length -lt $MinimumBytes) { return $false }
    $stream = [IO.File]::OpenRead($Path)
    try { $header = New-Object byte[] 4; [void]$stream.Read($header, 0, 4); return ([Text.Encoding]::ASCII.GetString($header) -eq 'GGUF') }
    finally { $stream.Dispose() }
}

function Test-PathInsideRoot {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Root)
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([char]'\') + '\'
    $pathFull = [IO.Path]::GetFullPath($Path)
    return $pathFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)
}

function Move-OptimusBackup {
    param([Parameter(Mandatory)][string]$Path, [hashtable]$Paths = (Get-OptimusIaPaths), [string]$Label = 'backup')
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    if (-not (Test-PathInsideRoot $Path $Paths.Root)) { throw 'Ruta fuera de la raiz de OPTIMUS rechazada.' }
    $destination = Join-Path $Paths.Backups ('{0}_{1}_{2}' -f $Label, (Split-Path -Leaf $Path), (Get-Date -Format 'yyyyMMdd_HHmmss'))
    Move-Item -LiteralPath $Path -Destination $destination
    return $destination
}

function Test-OptimusDiskSpace {
    param([Int64]$RequiredBytes, [string]$TargetPath)
    $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($TargetPath))
    $drive = Get-PSDrive -Name $root.TrimEnd([char[]]@([char]58, [char]92))
    $free = Get-SafeObjectProperty $drive @('Free') $null
    if ($null -eq $free -or [int64]$free -le 0) {
        $disk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$($root.TrimEnd([char]92))'" -ErrorAction SilentlyContinue
        $free = Get-SafeObjectProperty $disk @('FreeSpace') $null
    }
    if ($null -eq $free) { throw "No se pudo determinar el espacio libre de $root." }
    return [pscustomobject]@{ Drive = $root; FreeBytes = [Int64]$free; RequiredBytes = $RequiredBytes; Sufficient = ([Int64]$free -ge $RequiredBytes) }
}

function New-ResumableDownloadRequest {
    param([Parameter(Mandatory)][string]$Url, [Int64]$Offset = 0)
    Add-Type -AssemblyName System.Net.Http
    $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $Url)
    $request.Headers.UserAgent.ParseAdd('OPTIMUS-local-installer')
    if ($Offset -gt 0) {
        $request.Headers.Range = [System.Net.Http.Headers.RangeHeaderValue]::new([Nullable[long]]$Offset, [Nullable[long]]$null)
    }
    return $request
}

function Get-DownloadFile {
    param([Parameter(Mandatory)][string]$Url, [Parameter(Mandatory)][string]$Destination, [string]$ExpectedSha256)
    $part = "$Destination.part"
    $offset = if (Test-Path -LiteralPath $part) { [int64](Get-Item -LiteralPath $part).Length } else { [int64]0 }
    $request = $null
    $client = $null
    $response = $null
    try {
        $request = New-ResumableDownloadRequest $Url $offset
        $client = [System.Net.Http.HttpClient]::new()
        try {
            $response = $client.SendAsync($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) { throw "HTTP $([int]$response.StatusCode)" }
            $append = $offset -gt 0 -and [int]$response.StatusCode -eq 206
            $mode = if ($append) { [IO.FileMode]::Append } else { [IO.FileMode]::Create }
            $source = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
            $target = [IO.File]::Open($part, $mode, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try { $source.CopyTo($target) } finally { $target.Dispose(); $source.Dispose() }
        } finally { if ($response) { $response.Dispose() }; if ($client) { $client.Dispose() }; if ($request) { $request.Dispose() } }
    } catch { throw "Descarga fallida: $($_.Exception.Message)" }
    if ($ExpectedSha256 -and (Get-Sha256 $part) -ne $ExpectedSha256.ToLowerInvariant()) { throw 'El hash SHA-256 no coincide.' }
    Move-Item -LiteralPath $part -Destination $Destination -Force
    return Get-Item -LiteralPath $Destination
}

function Expand-LlamaInstallation {
    param([Parameter(Mandatory)][string[]]$Archives, [hashtable]$Paths = (Get-OptimusIaPaths))
    $newPath = Join-Path $Paths.Runtime 'llama_cpp_new'
    if (Test-Path -LiteralPath $newPath) { Move-OptimusBackup $newPath $Paths 'failed_or_previous_new' | Out-Null }
    New-Item -ItemType Directory -Force -Path $newPath | Out-Null
    foreach ($archive in $Archives) { Expand-Archive -LiteralPath $archive -DestinationPath $newPath -Force }
    $server = Get-ChildItem -Path $newPath -Filter 'llama-server.exe' -Recurse | Select-Object -First 1
    if (-not $server) { Move-OptimusBackup $newPath $Paths 'invalid_llama' | Out-Null; throw 'El paquete no contiene llama-server.exe.' }
    & $server.FullName '--version' | Out-Null
    if ($LASTEXITCODE -ne 0) { Move-OptimusBackup $newPath $Paths 'invalid_llama' | Out-Null; throw 'llama-server.exe --version fallo.' }
    if (Test-Path -LiteralPath $Paths.Llama) { Move-OptimusBackup $Paths.Llama $Paths 'llama_cpp' | Out-Null }
    Move-Item -LiteralPath $newPath -Destination $Paths.Llama
    return Get-ChildItem -Path $Paths.Llama -Filter 'llama-server.exe' -Recurse | Select-Object -First 1
}

function Write-LlamaRuntimeEnv {
    param([hashtable]$Paths = (Get-OptimusIaPaths), [Parameter(Mandatory)][string]$ServerPath, [int]$Threads = 8)
    $example = @(
        'OPTIMUS_PROVIDER=llama_cpp', 'OPTIMUS_LLAMA_BASE_URL=http://127.0.0.1:8080', 'OPTIMUS_LLAMA_MODEL=Qwen3-8B-Q4_K_M',
        'OPTIMUS_LLAMA_SERVER_EXE=<ruta_absoluta_a_llama-server.exe>', 'OPTIMUS_LLAMA_MODEL_PATH=<ruta_absoluta_al_GGUF>',
        'OPTIMUS_LLAMA_HOST=127.0.0.1', 'OPTIMUS_LLAMA_PORT=8080', 'OPTIMUS_LLAMA_CTX_SIZE=4096', 'OPTIMUS_LLAMA_GPU_LAYERS=99',
        'OPTIMUS_LLAMA_THREADS=8', 'OPTIMUS_LLAMA_MAX_TOKENS=1800', 'OPTIMUS_LLAMA_TIMEOUT_SECONDS=120',
        'OPTIMUS_LLAMA_DISABLE_THINKING=true', 'OPTIMUS_LLAMA_FLASH_ATTENTION=true', 'OPTIMUS_LLAMA_HEALTH_PATH=/health'
    )
    Set-Content -LiteralPath (Join-Path $Paths.LocalConfig 'llama_runtime.example.env') -Value $example -Encoding UTF8
    $actual = $example | ForEach-Object { $_ -replace '<ruta_absoluta_a_llama-server.exe>', $ServerPath -replace '<ruta_absoluta_al_GGUF>', $Paths.Model -replace 'OPTIMUS_LLAMA_THREADS=8', "OPTIMUS_LLAMA_THREADS=$Threads" }
    Set-Content -LiteralPath $Paths.RuntimeEnv -Value $actual -Encoding UTF8
}

function Read-LlamaRuntimeEnv {
    param([hashtable]$Paths = (Get-OptimusIaPaths))
    if (-not (Test-Path -LiteralPath $Paths.RuntimeEnv)) { throw 'No existe config/local/llama_runtime.env. Ejecute el instalador.' }
    $values = @{}
    Get-Content -LiteralPath $Paths.RuntimeEnv | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') { $values[$Matches[1].Trim()] = $Matches[2].Trim() }
    }
    return $values
}

Export-ModuleMember -Function *
