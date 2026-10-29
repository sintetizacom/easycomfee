# Chamado pelo uninstall.bat: mostra o que sera apagado, pede confirmacao, fecha o
# EasyComfee e o ComfyUI desta pasta e apaga os atalhos. A pasta em si o .bat apaga
# no fim (um script nao apaga a pasta de onde esta rodando).
# Saida 0 = pode apagar a pasta; 1 = cancelado.
param([Parameter(Mandatory = $true)][string]$Raiz,
      # So para teste: outras pastas de atalhos no lugar de Area de Trabalho / Menu Iniciar / Inicializar.
      [string[]]$PastasAtalhos)
$ErrorActionPreference = 'Continue'
$Raiz = (Resolve-Path -LiteralPath $Raiz).Path.TrimEnd('\')

function Dentro([string]$caminho) {
    if (-not $caminho) { return $false }
    try { $c = [IO.Path]::GetFullPath($caminho).TrimEnd('\') } catch { return $false }
    return $c -eq $Raiz -or $c.StartsWith($Raiz + '\', [StringComparison]::OrdinalIgnoreCase)
}

# ComfyUI e modelos: so vao junto se estiverem dentro desta pasta (os que o install.bat baixou).
$cfg = $null
try { $cfg = Get-Content -LiteralPath (Join-Path $Raiz 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
$comfy = if ($cfg) { [string]$cfg.comfy_dir } else { '' }

Write-Host ''
Write-Host 'This removes EasyComfee from this PC:' -ForegroundColor Yellow
Write-Host "  - the folder $Raiz"
Write-Host '  - the EasyComfee shortcuts (Desktop, Start menu, start with Windows)'
if ($comfy -and (Dentro $comfy)) {
    Write-Host '  - the ComfyUI that setup downloaded into this folder, with its models' -ForegroundColor Yellow
    Write-Host '    and the images, videos and audio you generated (ComfyUI\...\output).' -ForegroundColor Yellow
    Write-Host '    Copy anything you want to keep before going on.' -ForegroundColor Yellow
} elseif ($comfy) {
    Write-Host "Your own ComfyUI at $comfy is NOT touched (nor its models and outputs)."
}
Write-Host 'Git, Python, Node.js and the Visual C++ Redistributable stay installed;'
Write-Host 'remove them in Settings > Apps if nothing else uses them.'
Write-Host ''
$resposta = Read-Host 'Type YES to remove EasyComfee'
if ($resposta -ne 'YES' -and $resposta -ne 'yes') { Write-Host 'Nothing was removed.'; exit 1 }

# 1. Fecha o que roda desta pasta: o servidor (python da .venv), o ComfyUI portatil
#    (python_embeded) e a janela "ComfyUI" (cmd com python_embeded na linha de comando).
#    O cmd deste proprio uninstall.bat tambem cita a pasta: por isso so cmd com python_embeded.
$processos = Get-CimInstance Win32_Process
foreach ($p in $processos) {
    $exe = [string]$p.ExecutablePath
    $linha = [string]$p.CommandLine
    $doApp = ($exe -and (Dentro $exe)) -or
             ($p.Name -eq 'cmd.exe' -and $linha -like "*$Raiz*" -and $linha -like '*python_embeded*')
    if ($doApp -and $p.ProcessId -ne $PID) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

# 2. Atalhos que apontam para esta pasta (o do inicio com o Windows usa wscript/pythonw,
#    entao confere alvo, argumentos e pasta de trabalho).
$shell = New-Object -ComObject WScript.Shell
$pastas = if ($PastasAtalhos) { $PastasAtalhos } else {
    @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'),
      [Environment]::GetFolderPath('Startup')) }
foreach ($d in $pastas) {
    foreach ($nome in @('EasyComfee.lnk', 'EasyComfee - ComfyUI.lnk')) {
        $lnk = Join-Path $d $nome
        if (-not (Test-Path -LiteralPath $lnk)) { continue }
        $s = $shell.CreateShortcut($lnk)
        if ((Dentro $s.TargetPath) -or (Dentro $s.WorkingDirectory) -or ($s.Arguments -like "*$Raiz*")) {
            Remove-Item -LiteralPath $lnk -Force -ErrorAction SilentlyContinue
            Write-Host "Removed shortcut: $lnk"
        }
    }
}
exit 0
