#Requires -Version 5.1
param(
    [switch]$KeepAlive,
    [ValidateSet('', 'postgres', 'redis', 'api', 'worker', 'frontend')]
    [string]$Service = '',
    [string]$PgCtl = ''
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$ProjectRoot = $PSScriptRoot
$Backend = Join-Path $ProjectRoot 'backend'
$Frontend = Join-Path $ProjectRoot 'frontend'
$Local = Join-Path $ProjectRoot '.local'
$Python = Join-Path $Backend '.venv/Scripts/python.exe'
$ApiPort = 18000
$WebPort = 5173

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        return ($client.ConnectAsync('127.0.0.1', $Port).Wait(500) -and $client.Connected)
    } catch { return $false } finally { $client.Dispose() }
}

function Get-Worker {
    $root = $ProjectRoot.Replace('\', '/').ToLowerInvariant()
    # 同时识别此脚本启动的宿主与原有 uv/ARQ 进程，不匹配其他项目的 worker。
    $processes = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='powershell.exe' OR Name='arq.exe'"
    return $processes | Where-Object {
        $command = ([string]$_.CommandLine).Replace('\', '/').ToLowerInvariant()
        $command.Contains($root) -and (
            $command.Contains('app.workers.attempts.workersettings') -or
            $command -match '-service\s+worker'
        )
    } | Select-Object -First 1
}

function Start-ServiceHost([string]$Role) {
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Service', $Role)
    if ($Role -eq 'postgres') { $arguments += @('-PgCtl', ('"' + $PgCtl + '"')) }
    # 独立隐藏窗口；stdout/stderr 分开，避免 Start-Process 对相同重定向路径的限制。
    $process = Start-Process powershell.exe -ArgumentList $arguments -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogDirectory ($Role + '.stdout.log')) `
        -RedirectStandardError (Join-Path $LogDirectory ($Role + '.stderr.log'))
    $script:Started += $process
    return $process
}

function Wait-Ready([string]$Role, [scriptblock]$Check, $Process) {
    $deadline = (Get-Date).AddSeconds(45)
    do {
        if (& $Check) { return }
        if ($Process -and $Process.HasExited) { break }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw ($Role + ' did not become ready; check ' + $LogDirectory)
}

function Test-Api {
    try {
        $response = Invoke-WebRequest ('http://127.0.0.1:' + $ApiPort + '/openapi.json') -UseBasicParsing -TimeoutSec 3
        # Windows PowerShell 对未声明 charset 的 JSON 默认解码不可靠。
        $document = [System.Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray()) | ConvertFrom-Json
        return $document.info.title -eq '在线限时考试系统 API'
    } catch { return $false }
}

function Test-Frontend {
    try {
        $health = Invoke-RestMethod ('http://127.0.0.1:' + $WebPort + '/api/health') -TimeoutSec 3
        $page = Invoke-WebRequest ('http://127.0.0.1:' + $WebPort + '/login') -UseBasicParsing -TimeoutSec 3
        return $health.status -eq 'ok' -and $page.Content.Contains('/src/main.ts')
    } catch { return $false }
}

try {
    if (-not (Test-Path -LiteralPath (Join-Path $Backend '.env'))) {
        throw '缺少 backend/.env，请先按 docs/quick-start.md 完成配置。'
    }
    if ($Service) {
        # 子宿主以前台命令维持进程生命周期，PostgreSQL 启动器也要保持存活。
        switch ($Service) {
            'postgres' {
                & $PgCtl -D (Join-Path $Local 'pgdata') -l (Join-Path $Local 'postgres.log') -o ('-h 127.0.0.1 -p ' + $env:EXAM_START_PG_PORT) -w start
                if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
                do { Start-Sleep -Seconds 5; & $PgCtl -D (Join-Path $Local 'pgdata') status *> $null } while ($LASTEXITCODE -eq 0)
            }
            'redis' {
                $configPath = (Join-Path $Local 'redis.conf').Replace('\', '/')
                $wslPath = '/mnt/' + $configPath.Substring(0, 1).ToLowerInvariant() + $configPath.Substring(2)
                $env:MSYS_NO_PATHCONV = '1'
                & wsl.exe -d Ubuntu-24.04 -- redis-server $wslPath
            }
            'api' { Set-Location $Backend; & uv run uvicorn app.main:app --host 127.0.0.1 --port $ApiPort }
            'worker' { Set-Location $Backend; & uv run arq app.workers.attempts.WorkerSettings }
            'frontend' { Set-Location $Frontend; & npm.cmd run dev -- --port $WebPort --strictPort }
        }
        exit $LASTEXITCODE
    }

    foreach ($command in @('uv', 'npm.cmd')) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw ('未找到命令 ' + $command + '，请查看 docs/quick-start.md。') }
    }
    if (-not (Test-Path -LiteralPath $Python)) { throw '请先安装后端依赖：cd backend; uv sync --locked --python 3.13' }
    if (-not (Test-Path -LiteralPath (Join-Path $Frontend 'node_modules/vite'))) { throw '请先安装前端依赖：cd frontend; npm ci' }
    $LogDirectory = Join-Path $Local ('services/' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    $Started = @()
    Set-Location $Backend
    $configuration = @'
import json
from urllib.parse import urlsplit
from app.core.config import get_settings
try:
    settings = get_settings()
    database = urlsplit(settings.database_url)
    redis = urlsplit(settings.redis_url)
    print(json.dumps({'pg_host': database.hostname, 'pg_port': database.port or 5432, 'redis_host': redis.hostname, 'redis_port': redis.port or 6379}))
except Exception as error:
    print('Configuration invalid: ' + type(error).__name__)
    raise SystemExit(1)
'@
    $configText = & $Python -c $configuration
    if ($LASTEXITCODE -ne 0) { throw 'backend/.env 配置无效，请核对 docs/quick-start.md 中的必填项。' }
    $config = $configText | ConvertFrom-Json
    if ($config.pg_host -notin @('127.0.0.1', 'localhost') -or $config.redis_host -notin @('127.0.0.1', 'localhost')) {
        throw '此脚本用于本地开发，请配置本机数据库和 Redis 地址。'
    }
    $env:EXAM_START_PG_PORT = [string]$config.pg_port

    if (Test-Port $config.pg_port) { Write-Host 'REUSED postgres' } else {
        if (-not $PgCtl) {
            $found = Get-Command pg_ctl.exe -ErrorAction SilentlyContinue
            if ($found) { $PgCtl = $found.Source } else { $PgCtl = 'D:\postgresql\bin\pg_ctl.exe' }
        }
        if (-not (Test-Path -LiteralPath $PgCtl)) { throw '找不到 pg_ctl.exe，请通过 -PgCtl 指定其绝对路径。' }
        if (-not (Test-Path -LiteralPath (Join-Path $Local 'pgdata/PG_VERSION'))) { throw '缺少 .local/pgdata，请先初始化 PostgreSQL，或启动配置中已有的数据库实例。' }
        $process = Start-ServiceHost 'postgres'
        Wait-Ready 'postgres' { Test-Port $config.pg_port } $process
        Write-Host 'STARTED postgres'
    }
    if (Test-Port $config.redis_port) { Write-Host 'REUSED redis' } else {
        if (-not (Test-Path -LiteralPath (Join-Path $Local 'redis.conf'))) { throw '缺少 .local/redis.conf，请先按 docs/quick-start.md 配置 Redis。' }
        $process = Start-ServiceHost 'redis'
        Wait-Ready 'redis' { Test-Port $config.redis_port } $process
        Write-Host 'STARTED redis'
    }

    # 连接端口不足以证明依赖可用，实际验证配置对应的数据库和 Redis，输出不含凭据。
    $dependencies = @'
import asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import Resources
async def check():
    resources = Resources(get_settings())
    try:
        async with resources.engine.connect() as connection:
            await connection.execute(text('SELECT 1'))
            revisions = (await connection.execute(text('SELECT version_num FROM alembic_version'))).scalars().all()
            if set(revisions) != set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads()):
                raise RuntimeError('MIGRATION_REQUIRED')
        await resources.redis.ping()
    finally:
        await resources.close()
try:
    asyncio.run(check())
except Exception as error:
    print('Dependencies unavailable or migration required: ' + type(error).__name__)
    raise SystemExit(1)
'@
    & $Python -c $dependencies
    if ($LASTEXITCODE -ne 0) { throw '请检查数据库／Redis 配置及迁移版本；升级命令：cd backend; uv run alembic upgrade head。' }

    if (Test-Port $ApiPort) {
        if (-not (Test-Api)) { throw '18000 端口已被其他应用占用，或现有后端未就绪。' }
        Write-Host 'REUSED api'
    } else {
        $process = Start-ServiceHost 'api'
        Wait-Ready 'api' { Test-Api } $process
        Write-Host 'STARTED api'
    }
    if (Get-Worker) { Write-Host 'REUSED worker' } else {
        $process = Start-ServiceHost 'worker'
        Wait-Ready 'worker' { Get-Worker } $process
        Start-Sleep -Seconds 1
        if ($process.HasExited) { throw ('worker 已退出，请查看日志：' + $LogDirectory) }
        Write-Host 'STARTED worker'
    }
    if (Test-Port $WebPort) {
        if (-not (Test-Frontend)) { throw '5173 端口已被其他应用占用，或前端代理未就绪。' }
        Write-Host 'REUSED frontend'
    } else {
        $process = Start-ServiceHost 'frontend'
        Wait-Ready 'frontend' { Test-Frontend } $process
        Write-Host 'STARTED frontend'
    }
    $statePath = Join-Path $Local 'service-state.json'
    if ($Started.Count -eq 0 -and (Test-Path -LiteralPath $statePath)) {
        # 重跑只更新核验时间，保留实际启动日志和宿主记录，避免指向空日志目录。
        $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
        $state.status = 'running'
        $state | Add-Member -NotePropertyName verified_at -NotePropertyValue (Get-Date).ToString('o') -Force
    } else {
        $state = @{
            status = 'running'
            started_at = (Get-Date).ToString('o')
            log_directory = $LogDirectory
            started_host_pids = @($Started | ForEach-Object { $_.Id })
            frontend = 'http://127.0.0.1:5173'
            api = 'http://127.0.0.1:18000'
        }
    }
    $state | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $statePath
    Write-Host 'READY http://127.0.0.1:5173'
    Write-Host ('Logs: ' + $state.log_directory)
    # 自动化终端需要保留启动树；普通交互式 PowerShell 无需此开关。
    if ($KeepAlive) {
        while ((Test-Port $ApiPort) -or (Test-Port $WebPort) -or (Test-Port $config.pg_port) -or (Test-Port $config.redis_port)) { Start-Sleep -Seconds 5 }
    }
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message)
    exit 1
}
