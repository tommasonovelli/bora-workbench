<#
install.ps1 - explicit-source installer for qwen-launcher 0.1 on Windows.

IMPLEMENTATION_SPEC.md sections 5.10-5.12 require a small, idempotent installer that verifies
prerequisites, pins uv 0.11.28 through its official versioned installer, and installs the tool with
CPython 3.12.13. Exactly one source remains mandatory so an install never changes version or trust
boundary because of an implicit default.
#>
[CmdletBinding()]
param(
    [string]$Wheel,
    [string]$Sha256,
    [string]$GitCommit,
    [string]$PypiVersion,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$UvVersion = '0.11.28'
$PythonVersion = '3.12.13'
$RepoUrl = 'https://github.com/tommasonovelli/qwen-launcher.git'
$UvInstallerUrl = "https://astral.sh/uv/$UvVersion/install.ps1"

# Print an actionable error to stderr without a traceback and exit with a contractual code
# (spec section 5.11: 2 = invalid input/CLI, 1 = expected operational failure).
function Stop-WithError {
    param([string]$Message, [int]$Code)
    [Console]::Error.WriteLine("install.ps1: $Message")
    exit $Code
}

function Show-Usage {
    [Console]::Error.WriteLine(@"
Usage: install.ps1 (-Wheel PATH -Sha256 HEX | -GitCommit HEX | -PypiVersion VERSION)

Exactly one explicit source is required; no version is selected implicitly.

  -Wheel PATH -Sha256 HEX   install a local wheel after verifying its 64-hex SHA-256
  -GitCommit HEX            install from a 40-hex commit of $RepoUrl
  -PypiVersion VERSION      install an explicit version that exists on PyPI
"@)
}

if ($Help) {
    Show-Usage
    exit 0
}

function Test-Hex {
    param([string]$Value, [int]$Length)
    return $Value -match "^[0-9a-fA-F]{$Length}$"
}

# Require exactly one explicit source. A missing source is an input error, never a silent PyPI
# default, so rerunning the installer cannot unexpectedly select a newer release.
$sources = 0
if ($Wheel) { $sources++ }
if ($GitCommit) { $sources++ }
if ($PypiVersion) { $sources++ }
if ($sources -ne 1) {
    Show-Usage
    Stop-WithError "select exactly one explicit install source (got $sources)" 2
}

if ($Wheel) {
    if (-not $Sha256) { Stop-WithError "-Wheel requires -Sha256 with the wheel's SHA-256" 2 }
    if (-not (Test-Hex $Sha256 64)) { Stop-WithError "-Sha256 must be 64 hexadecimal characters" 2 }
}
elseif ($Sha256) {
    Stop-WithError "-Sha256 is only valid together with -Wheel" 2
}

if ($GitCommit -and -not (Test-Hex $GitCommit 40)) {
    Stop-WithError "-GitCommit must be a full 40-character commit hash" 2
}

function Get-Sha256 {
    param([string]$Path)
    # A PowerShell 7 PSModulePath inherited by powershell.exe 5.1 can break module discovery.
    # Direct .NET hashing keeps the clean-machine installer independent of optional commands.
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $bytes = $sha256.ComputeHash($stream)
            return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
        }
        finally { $sha256.Dispose() }
    }
    finally { $stream.Dispose() }
}

# Verify the supported platform and architecture before any download or install (spec section
# 5.10: no elevation, actionable prerequisite errors).
if ($env:OS -ne 'Windows_NT') {
    Stop-WithError "unsupported OS; this installer targets Windows x86-64" 1
}
$arch = $env:PROCESSOR_ARCHITEW6432
if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
if ($arch -ne 'AMD64') {
    Stop-WithError "unsupported architecture '$arch'; x86-64 is required" 1
}

if ($Wheel) {
    if (-not (Test-Path -LiteralPath $Wheel -PathType Leaf)) {
        Stop-WithError "wheel not found: $Wheel" 1
    }
    $actual = Get-Sha256 $Wheel
    if ($actual -ne $Sha256.ToLower()) {
        Stop-WithError "SHA-256 mismatch for $Wheel (expected $($Sha256.ToLower()), got $($actual.ToLower()))" 1
    }
}

# Ensure exactly uv 0.11.28. Reuse an already-matching uv to keep reruns cheap and offline;
# otherwise download the official versioned installer to a temporary file and run it as a script
# file, with TLS enforced and never through Invoke-Expression.
function Test-UvVersion {
    param([string]$Command)
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { return $false }
    $reported = & $Command --version 2>$null
    return "$reported" -match "^uv $([regex]::Escape($UvVersion))(\s|$)"
}

$uvDir = if ($env:UV_INSTALL_DIR) { $env:UV_INSTALL_DIR } else { Join-Path $env:USERPROFILE '.local\bin' }

if (Test-UvVersion 'uv') {
    $uvBin = 'uv'
}
else {
    if (-not (Get-Command 'curl.exe' -ErrorAction SilentlyContinue)) {
        Stop-WithError "curl.exe is required to download uv $UvVersion" 1
    }
    $installerTmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "uv-$UvVersion-install.ps1")
    & curl.exe --fail --location --proto '=https' --tlsv1.2 --silent --show-error $UvInstallerUrl --output $installerTmp
    if ($LASTEXITCODE -ne 0) { Stop-WithError "could not download the official uv $UvVersion installer" 1 }
    $env:UV_INSTALL_DIR = $uvDir
    & $installerTmp
    if ($LASTEXITCODE -ne 0) { Stop-WithError "the uv $UvVersion installer failed" 1 }
    Remove-Item -LiteralPath $installerTmp -Force -ErrorAction SilentlyContinue
    $uvExe = Join-Path $uvDir 'uv.exe'
    if (Test-UvVersion 'uv') { $uvBin = 'uv' }
    elseif (Test-UvVersion $uvExe) { $uvBin = $uvExe }
    else { Stop-WithError "uv $UvVersion is not available after running its installer" 1 }
}

# Build the single explicit install target and install the tool with the pinned Python.
if ($Wheel) { $target = $Wheel }
elseif ($GitCommit) { $target = "qwen-launcher @ git+$RepoUrl@$GitCommit" }
else { $target = "qwen-launcher==$PypiVersion" }

& $uvBin @('tool', 'install', '--force', '--python', $PythonVersion, $target)
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "uv could not install the tool from the requested source" 1
}

Write-Output "install.ps1: installed qwen-launcher with uv $UvVersion and Python $PythonVersion."
Write-Output "install.ps1: re-running this installer is safe."
Write-Output "install.ps1: to remove the tool later, run: uv tool uninstall qwen-launcher"
Write-Output "install.ps1: to remove managed data, run: qwen-launcher uninstall"
