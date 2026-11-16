param()

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Frontend = Join-Path $Root 'frontend'
$Backend = Join-Path $Root 'backend'

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program 执行失败，退出码：$LASTEXITCODE"
    }
}

foreach ($command in @('npm', 'uv')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "找不到 $command，请先安装并加入 PATH。"
    }
}

Push-Location $Backend
try {
    Write-Host '检查后端 Python 源码并同步锁定的依赖...'
    $env:PYTHONPYCACHEPREFIX = Join-Path $Root '.local/build-pycache'
    Invoke-Checked 'uv' @('run', '--locked', '--python', '3.13', 'python', '-m', 'compileall', '-q', 'app', 'migrations')
} finally {
    Pop-Location
}

Push-Location $Frontend
try {
    if (-not (Test-Path 'node_modules')) {
        Write-Host '安装锁定的前端依赖...'
        Invoke-Checked 'npm' @('ci', '--no-audit', '--no-fund')
    }
    $dist = Join-Path $Frontend 'dist'
    if (Test-Path $dist) {
        $deleted = Join-Path $Root '.deletedfiles'
        New-Item -ItemType Directory -Path $deleted -Force | Out-Null
        $backup = Join-Path $deleted ("frontend-dist-{0}-{1}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'), [guid]::NewGuid().ToString('N'))
        Move-Item -LiteralPath $dist -Destination $backup
    }
    Write-Host '编译前端生产版本...'
    Invoke-Checked 'npm' @('run', 'build')
    if (-not (Test-Path (Join-Path $dist 'index.html'))) {
        throw '前端构建未生成 dist/index.html。'
    }
} finally {
    Pop-Location
}

# 显式列出部署所需内容，避免将本地密钥和运行数据打进压缩包。
$releaseDir = Join-Path $Root '.local/releases'
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
$archivePath = Join-Path $releaseDir ("online-exam-system-{0}-{1}.zip" -f (Get-Date -Format 'yyyyMMdd-HHmmss'), [guid]::NewGuid().ToString('N').Substring(0, 8))
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($archivePath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    $items = @(
        @{ Path = (Join-Path $Frontend 'dist'); Name = 'frontend/dist' },
        @{ Path = (Join-Path $Backend 'app'); Name = 'backend/app' },
        @{ Path = (Join-Path $Backend 'migrations'); Name = 'backend/migrations' },
        @{ Path = (Join-Path $Backend 'alembic.ini'); Name = 'backend/alembic.ini' },
        @{ Path = (Join-Path $Backend 'pyproject.toml'); Name = 'backend/pyproject.toml' },
        @{ Path = (Join-Path $Backend 'uv.lock'); Name = 'backend/uv.lock' },
        @{ Path = (Join-Path $Backend '.python-version'); Name = 'backend/.python-version' },
        @{ Path = (Join-Path $Backend '.env.example'); Name = 'backend/.env.example' },
        @{ Path = (Join-Path $Root 'LICENSE'); Name = 'LICENSE' }
    )
    foreach ($item in $items) {
        $source = Get-Item -LiteralPath $item.Path -Force
        if ($source.PSIsContainer) {
            foreach ($file in Get-ChildItem -LiteralPath $source.FullName -File -Recurse -Force) {
                $relative = $file.FullName.Substring($source.FullName.Length).TrimStart('\', '/') -replace '\\', '/'
                if ($relative -match '(^|/)__pycache__(/|$)' -or $relative -match '\.py[co]$') { continue }
                if ($item.Name -eq 'backend/app' -and $file.Extension -ne '.py') { continue }
                if ($item.Name -eq 'backend/migrations' -and $file.Extension -notin @('.py', '.mako')) { continue }
                [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, "$($item.Name)/$relative") | Out-Null
            }
        } else {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $source.FullName, $item.Name) | Out-Null
        }
    }
} finally {
    $archive.Dispose()
}
Write-Host "打包完成：$archivePath"
