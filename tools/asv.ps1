<#
.SYNOPSIS
    ASV toolchain driver - headless build/flash/monitor for the ESP32 firmware.

.DESCRIPTION
    Wraps arduino-cli with the correct FQBN and board options baked in, so the
    firmware can be built and flashed from a terminal (or by an agent) without
    touching the Arduino IDE GUI.

    The partition scheme in particular MUST be min_spiffs - the default 1.2 MB
    app partition cannot hold the BLE stack plus the display libraries.

.EXAMPLE
    .\tools\asv.ps1 setup
    .\tools\asv.ps1 ports
    .\tools\asv.ps1 flash -Port COM3
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'ports', 'build', 'flash', 'monitor', 'clean', 'doctor')]
    [string]$Command = 'doctor',

    [string]$Port,

    # NOTE: must not be named -Verbose. [CmdletBinding()] already supplies that
    # common parameter, and redeclaring it is a hard error at invocation time.
    [switch]$Detailed
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# PowerShell 7.4+ turns non-zero native exit codes into terminating errors by
# default. Several calls below are expected to fail harmlessly (e.g. `config add`
# when the URL is already registered), so opt out.
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
$RepoRoot  = Split-Path -Parent $PSScriptRoot
$SketchDir = Join-Path $RepoRoot 'firmware_arduino\ASV_Firmware'
$BuildDir  = Join-Path $RepoRoot 'firmware_arduino\.build'
$Esp32Url  = 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'
$BaudRate  = 921600

# ESP32 Dev Module with every board menu option pinned. Do not change
# PartitionScheme unless you have shrunk the sketch.
$Fqbn = 'esp32:esp32:esp32:' + (@(
    'PartitionScheme=min_spiffs'
    'UploadSpeed=921600'
    'CPUFreq=240'
    'FlashFreq=80'
    'FlashSize=4M'
    'FlashMode=qio'
    'DebugLevel=none'
) -join ',')

$Libraries = @('Adafruit SSD1306', 'Adafruit GFX Library')

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step  ($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok    ($m) { Write-Host "    OK  $m" -ForegroundColor Green }
function Write-Warn2 ($m) { Write-Host "    !!  $m" -ForegroundColor Yellow }
function Write-Err   ($m) { Write-Host "    XX  $m" -ForegroundColor Red }

function Test-ArduinoCli {
    $null = Get-Command arduino-cli -ErrorAction SilentlyContinue
    return $?
}

function Assert-ArduinoCli {
    if (-not (Test-ArduinoCli)) {
        Write-Err "arduino-cli not found on PATH."
        Write-Host "    Run: .\tools\asv.ps1 setup" -ForegroundColor Yellow
        exit 1
    }
}

function Resolve-Port {
    param([string]$Requested)

    if ($Requested) { return $Requested }

    Write-Step 'No -Port given; auto-detecting'
    $json = & arduino-cli board list --format json 2>$null | ConvertFrom-Json

    # arduino-cli changed this payload shape between versions: newer builds wrap
    # the list in a "detected_ports" key, older ones return a bare array.
    $entries = @()
    if ($json) {
        if ($json.PSObject.Properties.Name -contains 'detected_ports') {
            $entries = @($json.detected_ports)
        } else {
            $entries = @($json)
        }
    }

    $candidates = @()
    foreach ($p in $entries) {
        if (-not $p) { continue }
        if ($p.PSObject.Properties.Name -contains 'port' -and $p.port) {
            if ($p.port.protocol -eq 'serial') { $candidates += $p.port.address }
        } elseif ($p.PSObject.Properties.Name -contains 'address') {
            $candidates += $p.address
        }
    }
    $candidates = @($candidates | Where-Object { $_ } | Select-Object -Unique)

    if ($candidates.Count -eq 1) {
        Write-Ok "Using $($candidates[0])"
        return $candidates[0]
    }
    if ($candidates.Count -eq 0) {
        Write-Err 'No serial ports found. Is the ESP32 plugged in?'
        exit 1
    }
    Write-Err "Multiple serial ports found: $($candidates -join ', ')"
    Write-Host '    Re-run with -Port <COMx>' -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
function Invoke-Setup {
    Write-Step 'Checking for arduino-cli'
    if (-not (Test-ArduinoCli)) {
        Write-Warn2 'Not installed. Attempting winget...'
        try {
            & winget install --id ArduinoSA.CLI -e --accept-source-agreements --accept-package-agreements
        } catch {
            Write-Err 'winget install failed.'
        }
        # winget updates PATH for new shells only; refresh this session.
        $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                    [System.Environment]::GetEnvironmentVariable('Path', 'User')

        if (-not (Test-ArduinoCli)) {
            Write-Err 'arduino-cli still not on PATH.'
            Write-Host ''
            Write-Host '    Install it manually, then re-run this command:' -ForegroundColor Yellow
            Write-Host '      https://arduino.github.io/arduino-cli/latest/installation/' -ForegroundColor Yellow
            Write-Host '    Or open a NEW terminal (winget may have installed it but not' -ForegroundColor Yellow
            Write-Host '    refreshed PATH in this one) and re-run: .\tools\asv.ps1 setup' -ForegroundColor Yellow
            exit 1
        }
    }
    Write-Ok (& arduino-cli version)

    Write-Step 'Configuring ESP32 board index'
    if (-not (Test-Path (Join-Path $env:APPDATA 'arduino-cli\arduino-cli.yaml'))) {
        & arduino-cli config init | Out-Null
    }
    # Idempotent: 'add' errors if already present, which is fine.
    & arduino-cli config add board_manager.additional_urls $Esp32Url 2>$null | Out-Null
    Write-Ok 'board index registered'

    Write-Step 'Updating package index (this downloads a few hundred MB the first time)'
    & arduino-cli core update-index
    if ($LASTEXITCODE -ne 0) { Write-Err 'core update-index failed'; exit 1 }

    Write-Step 'Installing esp32:esp32 core'
    & arduino-cli core install esp32:esp32
    if ($LASTEXITCODE -ne 0) { Write-Err 'core install failed'; exit 1 }
    Write-Ok 'esp32 core installed'

    Write-Step 'Installing libraries'
    foreach ($lib in $Libraries) {
        & arduino-cli lib install $lib
        if ($LASTEXITCODE -ne 0) { Write-Err "lib install failed: $lib"; exit 1 }
    }
    Write-Ok ($Libraries -join ', ')

    Write-Step 'Installing Python serial dependency'
    & python -m pip install --quiet pyserial
    if ($LASTEXITCODE -ne 0) { Write-Warn2 'pyserial install failed - tools/asv_serial.py will not run' }
    else { Write-Ok 'pyserial' }

    Write-Host ''
    Write-Ok 'Setup complete. Next: .\tools\asv.ps1 build'
}

function Invoke-Ports {
    Assert-ArduinoCli
    Write-Step 'Connected boards'
    & arduino-cli board list
}

function Invoke-Build {
    Assert-ArduinoCli
    if (-not (Test-Path $SketchDir)) { Write-Err "Sketch not found: $SketchDir"; exit 1 }

    Write-Step "Compiling $SketchDir"
    Write-Host "    fqbn: $Fqbn" -ForegroundColor DarkGray

    # Do not name this $args - that is an automatic variable in PowerShell.
    $cliArgs = @('compile', '--fqbn', $Fqbn, '--build-path', $BuildDir, '--warnings', 'all')
    if ($Detailed) { $cliArgs += '--verbose' }
    $cliArgs += $SketchDir

    & arduino-cli @cliArgs
    if ($LASTEXITCODE -ne 0) { Write-Err 'Compile FAILED'; exit 1 }
    Write-Ok 'Compile succeeded'
}

function Invoke-Flash {
    Assert-ArduinoCli
    $p = Resolve-Port -Requested $Port
    Invoke-Build

    Write-Step "Uploading to $p"
    & arduino-cli upload --fqbn $Fqbn --port $p --input-dir $BuildDir $SketchDir
    if ($LASTEXITCODE -ne 0) {
        Write-Err 'Upload FAILED'
        Write-Host '    If it hung at "Connecting...", hold the BOOT button on the' -ForegroundColor Yellow
        Write-Host '    ESP32 and retry. If the port is busy, close the Serial Monitor.' -ForegroundColor Yellow
        exit 1
    }
    Write-Ok "Flashed $p"
    Write-Host ''
    Write-Host '    Verify with:' -ForegroundColor DarkGray
    Write-Host "      python tools/asv_serial.py --port $p --cmd t --seconds 10" -ForegroundColor DarkGray
}

function Invoke-Monitor {
    Assert-ArduinoCli
    $p = Resolve-Port -Requested $Port
    Write-Warn2 'This blocks until Ctrl+C. For scripted use prefer tools/asv_serial.py.'
    Write-Step "Monitoring $p at $BaudRate"
    & arduino-cli monitor --port $p --config "baudrate=$BaudRate"
}

function Invoke-Clean {
    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir
        Write-Ok "Removed $BuildDir"
    } else {
        Write-Ok 'Already clean'
    }
}

function Invoke-Doctor {
    Write-Step 'ASV toolchain status'

    if (Test-ArduinoCli) { Write-Ok "arduino-cli: $(& arduino-cli version)" }
    else { Write-Err 'arduino-cli: NOT INSTALLED  -> run: .\tools\asv.ps1 setup' }

    if (Test-ArduinoCli) {
        $cores = & arduino-cli core list 2>$null | Out-String
        if ($cores -match 'esp32:esp32') { Write-Ok 'esp32 core: installed' }
        else { Write-Err 'esp32 core: MISSING -> run: .\tools\asv.ps1 setup' }

        $libs = & arduino-cli lib list 2>$null | Out-String
        foreach ($lib in $Libraries) {
            if ($libs -match [regex]::Escape($lib)) { Write-Ok "library: $lib" }
            else { Write-Err "library MISSING: $lib" }
        }
    }

    try {
        & python -c "import serial" 2>$null
        if ($LASTEXITCODE -eq 0) { Write-Ok 'python pyserial: installed' }
        else { Write-Err 'python pyserial: MISSING -> pip install pyserial' }
    } catch { Write-Err 'python: not found on PATH' }

    if (Test-Path $SketchDir) { Write-Ok "sketch: $SketchDir" }
    else { Write-Err "sketch NOT FOUND: $SketchDir" }

    Write-Host ''
    Write-Host '    Commands: setup | ports | build | flash | monitor | clean | doctor' -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
switch ($Command) {
    'setup'   { Invoke-Setup }
    'ports'   { Invoke-Ports }
    'build'   { Invoke-Build }
    'flash'   { Invoke-Flash }
    'monitor' { Invoke-Monitor }
    'clean'   { Invoke-Clean }
    'doctor'  { Invoke-Doctor }
}
