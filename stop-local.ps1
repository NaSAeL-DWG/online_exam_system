#Requires -Version 5.1
param(
    [switch]$WhatIf,
    [string]$PgCtl = ''
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$ProjectRoot = $PSScriptRoot
$StartScript = Join-Path $ProjectRoot 'start-local.ps1'
$Backend = Join-Path $ProjectRoot 'backend'
$Local = Join-Path $ProjectRoot '.local'
$Python = Join-Path $Backend '.venv/Scripts/python.exe'
$Failures = @()

function Get-ManagedHosts([string]$Role) {
    # 同时核对脚本绝对路径与角色，避免仅凭 PID 或端口误关其他程序。
    $scriptPath = $StartScript.Replace('\', '/').ToLowerInvariant()
    @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object {
        $command = ([string]$_.CommandLine).Replace('\', '/').ToLowerInvariant()
        $command.Contains($scriptPath) -and $command -match ('(?i)(?:^|\s)-service\s+' + [regex]::Escape($Role) + '(?:\s|$)')
    })
}

function Stop-HostTree($HostProcess, [string]$Role) {
    # 再次核验 PID，避免枚举与停止之间 PID 已被系统复用。
    $current = @(Get-ManagedHosts $Role | Where-Object { $_.ProcessId -eq $HostProcess.ProcessId })
    if ($current.Count -eq 0) { return }
    & taskkill.exe /PID $HostProcess.ProcessId /T /F | Out-Null
    if ($LASTEXITCODE -ne 0 -and @(Get-ManagedHosts $Role | Where-Object { $_.ProcessId -eq $HostProcess.ProcessId }).Count -gt 0) {
        throw "无法停止 $Role 宿主 PID $($HostProcess.ProcessId)。"
    }
}

function Stop-ManagedRole([string]$Role) {
    $hosts = @(Get-ManagedHosts $Role)
    if ($hosts.Count -eq 0) {
        Write-Host "未发现本脚本启动的 $Role，跳过。"
        return
    }
    foreach ($hostProcess in $hosts) {
        Write-Host "$(if ($WhatIf) { '将停止' } else { '正在停止' }) $Role（宿主 PID $($hostProcess.ProcessId)）"
        if ($WhatIf) { continue }
        switch ($Role) {
            'postgres' {
                $ctl = $PgCtl
                if (-not $ctl -and $hostProcess.CommandLine -match '(?i)-PgCtl\s+(?:"([^"]+)"|(\S+))') {
                    $ctl = if ($Matches[1]) { $Matches[1] } else { $Matches[2] }
                }
                if (-not $ctl) { throw '无法确定启动 PostgreSQL 时使用的 pg_ctl，请通过 -PgCtl 指定。' }
                & $ctl -D (Join-Path $Local 'pgdata') status *> $null
                if ($LASTEXITCODE -eq 0) {
                    & $ctl -D (Join-Path $Local 'pgdata') -m fast -w stop
                    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL 未能正常停止。' }
                } elseif ($LASTEXITCODE -ne 3) {
                    throw '无法确认 PostgreSQL 数据目录的运行状态。'
                }
                Stop-HostTree $hostProcess $Role
            }
            'redis' {
                if (-not (Test-Path -LiteralPath $Python)) { throw '找不到后端 Python，无法读取 Redis 配置并正常关闭。' }
                # 通过现有配置认证并正常关闭 Redis，不在命令行或日志中暴露密码。
                $shutdown = @'
import asyncio
import shlex
from pathlib import Path
from urllib.parse import urlsplit
from redis.asyncio import Redis
from app.core.config import get_settings

async def main():
    url = get_settings().redis_url
    address = urlsplit(url)
    config_path = Path('../.local/redis.conf')
    port = 6379
    for line in config_path.read_text(encoding='utf-8').splitlines():
        parts = shlex.split(line, comments=True)
        if parts and parts[0].lower() == 'include':
            raise RuntimeError('Redis 配置包含 include，无法安全确认端口')
        if len(parts) >= 2 and parts[0].lower() == 'port':
            port = int(parts[1])
    if address.hostname not in ('127.0.0.1', 'localhost') or (address.port or 6379) != port:
        raise RuntimeError('Redis 地址与启动配置不一致')
    client = Redis.from_url(url)
    try:
        await client.ping()
        await client.shutdown()
    finally:
        await client.aclose()

asyncio.run(main())
'@
                Push-Location $Backend
                try { $shutdown | & $Python - } finally { Pop-Location }
                if ($LASTEXITCODE -ne 0) { throw 'Redis 未能正常停止；请检查 backend/.env 和 Redis 状态。' }
                $deadline = (Get-Date).AddSeconds(15)
                while (@(Get-ManagedHosts $Role | Where-Object { $_.ProcessId -eq $hostProcess.ProcessId }).Count -gt 0) {
                    if ((Get-Date) -ge $deadline) { throw 'Redis 宿主未退出，请检查 Redis 状态。' }
                    Start-Sleep -Milliseconds 500
                }
            }
            default { Stop-HostTree $hostProcess $Role }
        }
    }
}

foreach ($role in @('frontend', 'worker', 'api')) {
    try { Stop-ManagedRole $role } catch {
        $Failures += "${role}: $($_.Exception.Message)"
        Write-Host "停止失败：$($Failures[-1])"
    }
}

if ($Failures.Count -eq 0) {
    foreach ($role in @('redis', 'postgres')) {
        try { Stop-ManagedRole $role } catch {
            $Failures += "${role}: $($_.Exception.Message)"
            Write-Host "停止失败：$($Failures[-1])"
        }
    }
} else {
    Write-Host '应用服务未全部停止，保留 Redis 和 PostgreSQL。'
}

if ($Failures.Count -gt 0) { exit 1 }
if ($WhatIf) { Write-Host '预览完成，未停止服务。'; exit 0 }

$statePath = Join-Path $Local 'service-state.json'
if (Test-Path -LiteralPath $statePath) {
    try {
        $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
        $state | Add-Member -NotePropertyName status -NotePropertyValue 'managed_services_stopped' -Force
        $state | Add-Member -NotePropertyName stopped_at -NotePropertyValue (Get-Date).ToString('o') -Force
        $state | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $statePath
    } catch {
        Write-Warning '服务已停止，但无法更新 .local/service-state.json。'
    }
}
Write-Host '本项目由启动脚本管理的服务已停止；启动时复用的服务不受影响。'
