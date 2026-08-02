$launcher = Join-Path $PSScriptRoot '..\ARRANCAR_LLAMA_SERVER.ps1'
. $launcher -NoRun

Describe 'ARRANCAR_LLAMA_SERVER stderr nativo' {
    It 'registra stderr informativo y no falla cuando el proceso termina en cero' {
        $log = Join-Path $TestDrive 'llama-server.log'
        $native = Join-Path $TestDrive 'native-ok.cmd'
        Set-Content -LiteralPath $native -Value "@echo off`r`necho informacion normal 1>&2`r`nexit /b 0" -Encoding Ascii
        Invoke-LlamaServerNative -FilePath $native -Arguments @() -LogPath $log | Out-Null

        (Get-Content -Raw -LiteralPath $log) | Should Match 'informacion normal'
    }

    It 'trata un codigo de salida nativo distinto de cero como error' {
        $log = Join-Path $TestDrive 'llama-server-error.log'
        $native = Join-Path $TestDrive 'native-error.cmd'
        Set-Content -LiteralPath $native -Value "@echo off`r`nexit /b 7" -Encoding Ascii
        try {
            Invoke-LlamaServerNative -FilePath $native -Arguments @() -LogPath $log
            throw 'Se esperaba un error por codigo de salida no cero.'
        } catch {
            $_.Exception.Message | Should Match 'codigo de salida 7'
        }
    }
}
