$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$UvInstallUrl = if ($env:LEETCODE_LOCAL_CLI_UV_INSTALL_URL) {
    $env:LEETCODE_LOCAL_CLI_UV_INSTALL_URL
} else {
    "https://astral.sh/uv/install.ps1"
}
$InstallSpec = if ($env:LEETCODE_LOCAL_CLI_INSTALL_SPEC) {
    $env:LEETCODE_LOCAL_CLI_INSTALL_SPEC
} else {
    "leetcode-local-cli"
}
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
    $Uri = [Uri]$UvInstallUrl
    if ($Uri.Scheme -ne "https") {
        throw "uv 安装地址必须使用 HTTPS：$UvInstallUrl"
    }

    $InstallerPath = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) "leetcode-local-cli-install-uv-$([Guid]::NewGuid()).ps1"
    try {
        Write-Info "未检测到 uv，正在下载安装官方 uv..."
        Invoke-WebRequest -UseBasicParsing -Uri $UvInstallUrl -OutFile $InstallerPath
        & $InstallerPath
    } finally {
        Remove-Item -LiteralPath $InstallerPath -Force -ErrorAction SilentlyContinue
    }

    $UvPath = Find-Uv
    if (-not $UvPath) {
        throw "uv 安装完成后仍无法定位可执行文件"
    }
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
Write-Info "如果当前终端找不到 lc，请重新打开终端或执行：$LcPath --help"
