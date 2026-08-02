[CmdletBinding()]
param([switch]$TestGeneration)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'scripts\optimus_ia_runtime.psm1') -Force
$cfg = Read-LlamaRuntimeEnv (Get-OptimusIaPaths $PSScriptRoot)
if ($cfg.OPTIMUS_LLAMA_HOST -ne '127.0.0.1') { throw 'Configuracion no segura: host distinto de localhost.' }
$base = "http://127.0.0.1:$($cfg.OPTIMUS_LLAMA_PORT)"
try { $health = Invoke-RestMethod -Uri "$base$($cfg.OPTIMUS_LLAMA_HEALTH_PATH)" -TimeoutSec 10 } catch { throw "GET /health fallo: $($_.Exception.Message)" }
try { $models = Invoke-RestMethod -Uri "$base/v1/models" -TimeoutSec 10 } catch { $models = $null; Write-Host 'Endpoint /v1/models no disponible; se mantiene /health correcto.' }
if ($models -and -not ($models.data | Where-Object { $_.id -match 'Qwen3-8B-Q4_K_M|qwen' })) { throw 'El endpoint de modelos no anuncia el modelo esperado.' }
Write-Host "Servidor local operativo en $base; health JSON valido."
if ($TestGeneration) {
    $body = @{ model = $cfg.OPTIMUS_LLAMA_MODEL; stream = $false; messages = @(@{role='system';content='Eres un asistente de prueba. Responde de forma concisa.'}, @{role='user';content='Responde unicamente: SERVIDOR LOCAL OPERATIVO /no_think'}) } | ConvertTo-Json -Depth 5
    $start = Get-Date
    $response = Invoke-RestMethod -Uri "$base/v1/chat/completions" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 120
    $content = $response.choices[0].message.content
    if (-not $content) { throw 'La prueba no clinica devolvio contenido vacio.' }
    Write-Host "Prueba no clinica correcta; latencia: $([int]((Get-Date)-$start).TotalMilliseconds) ms."
}
exit 0
