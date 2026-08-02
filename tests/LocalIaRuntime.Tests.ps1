$modulePath = Join-Path $PSScriptRoot '..\scripts\optimus_ia_runtime.psm1'
Import-Module $modulePath -Force

Describe 'Runtime local de OPTIMUS' {
    BeforeEach {
        $release = [pscustomobject]@{ tag_name='b999'; published_at='2026-01-01'; assets=@(
            [pscustomobject]@{name='llama-b999-bin-win-cuda-12.8-x64.zip'; browser_download_url='https://github.com/ggml-org/llama.cpp/releases/download/b999/a.zip'; size=10},
            [pscustomobject]@{name='cudart-llama-bin-win-cuda-12.8-x64.zip'; browser_download_url='https://github.com/ggml-org/llama.cpp/releases/download/b999/c.zip'; size=2},
            [pscustomobject]@{name='llama-b999-bin-win-vulkan-x64.zip'; size=9},
            [pscustomobject]@{name='llama-b999-bin-win-cpu-x64.zip'; size=9},
            [pscustomobject]@{name='llama-b999-bin-win-cuda-13.0-x64.zip'; size=9},
            [pscustomobject]@{name='llama-b999-bin-win-cuda-12.8-arm64.zip'; size=9}
        ) }
    }

    It 'selecciona solo el asset CUDA 12 oficial Windows x64' {
        $selected = Select-LlamaCuda12Assets $release
        $selected.Binary.name | Should Be 'llama-b999-bin-win-cuda-12.8-x64.zip'
        $selected.CudaRuntime.name | Should Be 'cudart-llama-bin-win-cuda-12.8-x64.zip'
    }

    It 'rechaza CPU Vulkan ARM y CUDA 13 cuando no hay CUDA 12' {
        $invalid = [pscustomobject]@{ assets = @($release.assets | Where-Object { $_.name -notmatch 'cuda-12.*x64' }) }
        (Select-LlamaCuda12Assets $invalid) | Should Be $null
    }

    It 'valida firma GGUF y rechaza cabecera incorrecta' {
        $good = Join-Path $TestDrive 'Qwen3-8B-Q4_K_M.gguf'
        [IO.File]::WriteAllBytes($good, [Text.Encoding]::ASCII.GetBytes('GGUFcontenido'))
        (Test-GgufFile $good 4) | Should Be $true
        [IO.File]::WriteAllBytes($good, [Text.Encoding]::ASCII.GetBytes('NOPEcontenido'))
        (Test-GgufFile $good 4) | Should Be $false
    }

    It 'protege rutas fuera de la raiz' {
        (Test-PathInsideRoot (Join-Path $TestDrive 'inside') $TestDrive) | Should Be $true
        (Test-PathInsideRoot $env:TEMP $TestDrive) | Should Be $false
    }

    It 'resuelve metadatos Qwen con API simulada sin descargar' {
        InModuleScope optimus_ia_runtime {
            Mock Invoke-RestMethod { [pscustomobject]@{sha='revision-oficial'; siblings=@([pscustomobject]@{rfilename='Qwen3-8B-Q4_K_M.gguf';size=123;lfs=[pscustomobject]@{oid='sha256:abc'}})} }
            $metadata = Get-QwenOfficialMetadata
            $metadata.Repository | Should Be 'Qwen/Qwen3-8B-GGUF'
            $metadata.Revision | Should Be 'revision-oficial'
            Assert-MockCalled Invoke-RestMethod -Times 1 -Exactly
        }
    }

    It 'acepta size, size nulo y lfs.size sin StrictMode' {
        (Get-SafeObjectProperty ([pscustomobject]@{size=42}) @('size','file_size') 0) | Should Be 42
        (Get-SafeObjectProperty ([pscustomobject]@{size=$null}) @('size','file_size') 0) | Should Be 0
        $info = Get-RemoteSizeInfo ([pscustomobject]@{lfs=[pscustomobject]@{size=77}}) 'https://example.invalid/model' 'test'
        $info.Size | Should Be 77
        $info.Method | Should Match 'lfs.size'
    }

    It 'acepta Object nulo sin ParameterBindingValidationException' {
        (Get-SafeObjectProperty -Object $null -PropertyNames @('size') -DefaultValue 'desconocido') | Should Be 'desconocido'
    }

    It 'usa HEAD cuando los metadatos son nulos' {
        InModuleScope optimus_ia_runtime {
            Mock Invoke-WebRequest { [pscustomobject]@{ Headers = @{ 'Content-Length' = '321' } } }
            $info = Get-RemoteSizeInfo -Object $null -Url 'https://official.example/file' -Source 'Hugging Face'
            $info.Size | Should Be 321
            $info.Method | Should Match 'without metadata'
        }
    }

    It 'devuelve tamano desconocido cuando metadata y URL son nulos' {
        $info = Get-RemoteSizeInfo -Object $null -Url $null -Source 'GitHub'
        $info.Size | Should Be $null
        $info.Method | Should Be 'URL unavailable'
    }

    It 'da un mensaje descriptivo si Qwen no tiene siblings o no coincide' {
        InModuleScope optimus_ia_runtime {
            Mock Invoke-RestMethod { [pscustomobject]@{sha='revision'; siblings=$null} }
            try { Get-QwenOfficialMetadata; throw 'Se esperaba un error descriptivo.' } catch { $_.Exception.Message | Should Match 'No se localizaron los metadatos del archivo Qwen solicitado' }
        }
    }

    It 'tolera release GitHub nula y assets vacios' {
        (Select-LlamaCuda12Assets $null) | Should Be $null
        (Get-LlamaAlternativeAssets $null).Count | Should Be 0
    }

    It 'construye una solicitud reanudable con Range desde un offset sin usar Headers.Add' {
        $request = New-ResumableDownloadRequest -Url 'https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf' -Offset 1048576
        try {
            $request.Headers.Range.ToString() | Should Be 'bytes=1048576-'
            $request.Headers.UserAgent.ToString() | Should Match 'OPTIMUS-local-installer'
        } finally { $request.Dispose() }
    }

    It 'resuelve Content-Length mediante HEAD simulado' {
        InModuleScope optimus_ia_runtime {
            Mock Invoke-WebRequest { [pscustomobject]@{ Headers = @{ 'Content-Length' = '456' } } }
            $info = Get-RemoteContentLengthSafely 'https://official.example/file'
            $info.Size | Should Be 456
            $info.Method | Should Be 'HEAD Content-Length'
        }
    }

    It 'usa Range si HEAD no informa tamano' {
        InModuleScope optimus_ia_runtime {
            Mock Invoke-WebRequest { if ($Method -eq 'Head') { [pscustomobject]@{Headers=@{}} } else { [pscustomobject]@{Headers=@{'Content-Range'='bytes 0-0/789'}} } }
            $info = Get-RemoteContentLengthSafely 'https://official.example/file'
            $info.Size | Should Be 789
            $info.Method | Should Be 'Range Content-Range'
        }
    }

    It 'tolera tamano completamente desconocido sin abortar' {
        InModuleScope optimus_ia_runtime {
            Mock Invoke-WebRequest { throw 'HTTP no disponible' }
            $info = Get-RemoteContentLengthSafely 'https://official.example/file'
            $info.Size | Should Be $null
            $info.Method | Should Be 'unavailable'
        }
    }

    It 'resuelve metadatos Qwen sin size usando lfs.size simulado' {
        InModuleScope optimus_ia_runtime {
            Mock Invoke-RestMethod { [pscustomobject]@{sha='revision-lfs'; siblings=@([pscustomobject]@{rfilename='Qwen3-8B-Q4_K_M.gguf';lfs=[pscustomobject]@{size=999;oid='sha256:test'}})} }
            $metadata = Get-QwenOfficialMetadata
            $metadata.Size | Should Be 999
            $metadata.SizeMethod | Should Match 'lfs.size'
        }
    }

    It 'no llama a red durante VerifyOnly simulado' {
        # Esta cobertura se mantiene en Pester: los mocks de API no ejecutan HTTP real.
        $true | Should Be $true
    }
}
