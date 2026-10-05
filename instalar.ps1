# Instalador del kit de edicion de video (Windows).
# Uso: abrir PowerShell en esta carpeta y correr:
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
$ErrorActionPreference = "Stop"
$kit = $PSScriptRoot
$claude = Join-Path $env:USERPROFILE ".claude"
$skills = Join-Path $claude "skills"
$agents = Join-Path $claude "agents"
New-Item -ItemType Directory -Force $skills, $agents | Out-Null

Write-Host "== Revisando programas necesarios =="
$faltan = @()
foreach ($p in @("git", "node", "npm", "python")) {
    if (-not (Get-Command $p -ErrorAction SilentlyContinue)) { $faltan += $p }
}
if ($faltan.Count -gt 0) {
    Write-Host "Faltan: $($faltan -join ', ')" -ForegroundColor Yellow
    Write-Host "Instalalos con:" -ForegroundColor Yellow
    Write-Host "  winget install Git.Git OpenJS.NodeJS.LTS Python.Python.3.12 Gyan.FFmpeg"
    Write-Host "Despues cerra y abri PowerShell de nuevo y volve a correr este instalador."
    exit 1
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "Aviso: falta FFmpeg (lo usa HyperFrames). Instalalo con: winget install Gyan.FFmpeg" -ForegroundColor Yellow
}

Write-Host "== 1/4 Skills oficiales de HyperFrames (motion graphics) =="
npx -y skills add heygen-com/hyperframes -g -a claude-code -s '*' -y --copy

Write-Host "== 2/4 Skill editor-videos-1porciento + agente editor =="
$dest = Join-Path $skills "editor-videos-1porciento"
$marca = Join-Path $dest "MARCA.md"
$marcaVieja = $null
if (Test-Path $marca) { $marcaVieja = Get-Content $marca -Raw -Encoding UTF8 }
Copy-Item -Recurse -Force (Join-Path $kit "skills\editor-videos-1porciento") $skills
if ($marcaVieja) { Set-Content $marca $marcaVieja -Encoding UTF8 -NoNewline }   # no pisar tu marca
$ag = Join-Path $agents "editor.md"
if (Test-Path $ag) { Copy-Item $ag "$ag.bak" -Force }
Copy-Item -Force (Join-Path $kit "agents\editor.md") $agents

Write-Host "== 3/4 Librerias de Python (subtitulos, Whisper) =="
python -m pip install -r (Join-Path $dest "scripts\requirements.txt")

Write-Host "== 4/4 Kit de video de Nate Herk (edicion larga, cortes, storytelling) =="
$nate = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "hyperframes-student-kit"
if (-not (Test-Path $nate)) { git clone https://github.com/nateherkai/hyperframes-student-kit.git $nate }
Push-Location $nate
npm ci
npm run setup
Pop-Location

Write-Host ""
Write-Host "LISTO." -ForegroundColor Green
Write-Host "Cerra y volve a abrir Claude (Claude Code / app de escritorio) para que cargue los skills."
Write-Host "Primer paso: decile a Claude 'completa mi MARCA.md del skill editor-videos-1porciento'."
Write-Host "Kit de Nate Herk en: $nate (abri esa carpeta en Claude Code para usar /edit-video, /short-form-edit, etc.)"
