$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$InstallSpec = if ($env:LEETCODE_LOCAL_CLI_INSTALL_SPEC) {
    $env:LEETCODE_LOCAL_CLI_INSTALL_SPEC
} else {
    "leetcode-local-cli"
}
$UvDocsUrl = "https://docs.astral.sh/uv/"
if ($InstallSpec.IndexOf("http://", [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
    throw "包安装地址必须使用 HTTPS：$InstallSpec"
}

function Write-Info([string]$Message) {
    Write-Host "[leetcode-local-cli] $Message"
}

function Find-Uv {
    $Command = Get-Command uv -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $Candidates = @()
    if ($env:UV_INSTALL_DIR) {
        $Candidates += Join-Path $env:UV_INSTALL_DIR "uv.exe"
    }
    if ($HOME) {
        $Candidates += Join-Path $HOME ".local/bin/uv.exe"
        $Candidates += Join-Path $HOME ".cargo/bin/uv.exe"
    }

    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            return $Candidate
        }
    }
    return $null
}

$UvPath = Find-Uv
if (-not $UvPath) {
    throw "未检测到 uv。请先按照 uv 官方文档安装：$UvDocsUrl"
}

Write-Info "使用 uv：$UvPath"
Write-Info "正在安装：$InstallSpec"
& $UvPath tool install --force $InstallSpec
if ($LASTEXITCODE -ne 0) {
    throw "uv tool install 执行失败，退出码：$LASTEXITCODE"
}

if ($env:LEETCODE_LOCAL_CLI_NO_MODIFY_PATH -ne "1") {
    & $UvPath tool update-shell *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "无法自动更新 PATH；请执行 '$UvPath tool update-shell'"
    }
}

$ToolBinOutput = & $UvPath tool dir --bin
if ($LASTEXITCODE -ne 0) {
    throw "无法读取 uv 工具命令目录"
}
$ToolBinDir = ($ToolBinOutput | Select-Object -Last 1).Trim()
$LcPath = Join-Path $ToolBinDir "lc.exe"
if (-not (Test-Path -LiteralPath $LcPath -PathType Leaf)) {
    $LcPath = Join-Path $ToolBinDir "lc"
}
if (-not (Test-Path -LiteralPath $LcPath -PathType Leaf)) {
    throw "安装完成，但未找到 lc：$ToolBinDir"
}

$InstalledVersion = & $LcPath --version
if ($LASTEXITCODE -ne 0) {
    throw "lc 版本检查失败，退出码：$LASTEXITCODE"
}
Write-Info "安装成功：$InstalledVersion"

if ($env:LEETCODE_LOCAL_CLI_NO_INIT -eq "1") {
    Write-Info "已跳过工作区配置；稍后可执行：$LcPath init"
} elseif (
    [Environment]::UserInteractive -and
    -not [Console]::IsInputRedirected -and
    -not [Console]::IsOutputRedirected
) {
    Write-Info "开始配置工作区"
    & $LcPath init
    if ($LASTEXITCODE -ne 0) {
        throw "lc 已安装，但工作区配置未完成；请稍后执行：$LcPath init"
    }
} else {
    Write-Info "当前环境不可交互，已跳过工作区配置；请执行：$LcPath init"
}

Write-Info "如果当前终端找不到 lc，请重新打开终端或执行：$LcPath --help"
