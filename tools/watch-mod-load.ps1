<#
.SYNOPSIS
    Watch (or restart) Cities: Skylines so you can see how the CS1-to-BeamNG exporter mod loads.

.DESCRIPTION
    Cities: Skylines scans the LocalMods folder and compiles .cs mods ONCE, at startup.
    This script makes that moment visible:

      * shows the mod folder contents and whether the .cs file is where the game expects it
      * tails Cities_Data\output_log.txt and highlights only the lines that matter
        (source scan, compiler errors, assembly load)
      * -Restart closes the game, resets the log and relaunches it so the scan happens again
      * -Build compiles the .cs to a .dll with the game's own bundled compiler and drops it
        into the mod folder, bypassing the in-game auto-compiler entirely

.PARAMETER GamePath
    Cities: Skylines install folder. Auto-detected from common locations if omitted.

.PARAMETER Restart
    Close the game (if running), archive the old log, then relaunch it.

.PARAMETER Build
    Compile mod\CS1ToBeamNGExporter.cs into the mod folder using the game's Mono compiler,
    then exit. Use this if the in-game compiler reports errors.

.PARAMETER Follow
    Keep watching the log until you press Ctrl+C. Without it the script prints the relevant
    lines already in the log and exits, which is enough to diagnose a failed load.

.EXAMPLE
    .\tools\watch-mod-load.ps1 -Restart
    Restart the game and watch the mod load.

.EXAMPLE
    .\tools\watch-mod-load.ps1 -Build
    Build the mod DLL directly into the LocalMods folder.
#>

[CmdletBinding()]
param(
    [string] $GamePath,
    [switch] $Restart,
    [switch] $Build,
    [switch] $Follow
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------------------
#  Paths
# ---------------------------------------------------------------------------------------
$repoRoot = Split-Path -Parent $PSScriptRoot
$modSource = Join-Path $repoRoot 'mod\CS1ToBeamNGExporter.cs'
$modRoot = Join-Path $env:LOCALAPPDATA 'Colossal Order\Cities_Skylines\Addons\Mods'
$modFolder = Join-Path $modRoot 'CS1ToBeamNGExporter'

function Write-Head([string] $text) {
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ('=' * 78) -ForegroundColor DarkCyan
}

function Write-Ok([string] $text) { Write-Host "  [ok]   $text" -ForegroundColor Green }
function Write-Bad([string] $text) { Write-Host "  [FAIL] $text" -ForegroundColor Red }
function Write-Info([string] $text) { Write-Host "  [info] $text" -ForegroundColor Gray }
function Write-Warn2([string] $text) { Write-Host "  [warn] $text" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------------------
#  Locate the game
# ---------------------------------------------------------------------------------------
function Find-GamePath {
    if ($GamePath) {
        if (Test-Path (Join-Path $GamePath 'Cities.exe')) { return $GamePath }
        throw "No Cities.exe in '$GamePath'."
    }

    $candidates = @(
        'E:\games\epic games\CitiesSkylines',
        'C:\Program Files (x86)\Steam\steamapps\common\Cities_Skylines',
        'D:\SteamLibrary\steamapps\common\Cities_Skylines',
        'E:\SteamLibrary\steamapps\common\Cities_Skylines',
        'D:\Steam\steamapps\common\Cities_Skylines'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path (Join-Path $candidate 'Cities.exe')) { return $candidate }
    }

    # Any drive: <drive>\...\steamapps\common\Cities_Skylines
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem).Root) {
        $guess = Join-Path $drive 'SteamLibrary\steamapps\common\Cities_Skylines'
        if (Test-Path (Join-Path $guess 'Cities.exe')) { return $guess }
    }

    throw "Could not find Cities.exe. Pass -GamePath 'E:\path\to\CitiesSkylines'."
}

$game = Find-GamePath
$logPath = Join-Path $game 'Cities_Data\output_log.txt'
$managed = Join-Path $game 'Cities_Data\Managed'
$compiledMods = Join-Path $game 'Cities_Data\Mods'

# ---------------------------------------------------------------------------------------
#  -Build : compile with csc.exe against the game's own assemblies, into the mod folder
# ---------------------------------------------------------------------------------------
if ($Build) {
    Write-Head 'Building CS1ToBeamNGExporter.dll for the mod folder'

    # NOTE: the game's bundled Mono C# compiler (Mono\lib\mono\unity\smcs.exe) CANNOT be run
    # standalone -- it immediately needs System.CodeDom.Compiler, which the shipped Mono
    # profile does not contain, so it dies with a ReflectionTypeLoadException.  The Windows
    # .NET Framework compiler works fine when pointed at the game's own reference assemblies,
    # which is what we do here (this is the exact invocation used to verify the mod).
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if (-not (Test-Path $csc)) {
        $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
    }
    if (-not (Test-Path $csc)) {
        throw "Could not find the .NET Framework C# compiler (csc.exe). Use the game's own auto-compile instead: leave only the .cs file in the mod folder."
    }

    if (-not (Test-Path $modSource)) { throw "Missing source: $modSource" }
    if (-not (Test-Path $modFolder)) {
        New-Item -ItemType Directory -Path $modFolder -Force | Out-Null
        Write-Info "created $modFolder"
    }

    $dll = Join-Path $modFolder 'CS1ToBeamNGExporter.dll'
    $refs = @('mscorlib.dll', 'System.dll', 'System.Core.dll', 'UnityEngine.dll',
              'Assembly-CSharp.dll', 'ColossalManaged.dll', 'ICities.dll') |
        ForEach-Object { "/r:$managed\$_" }

    Write-Info "compiler : $csc"
    Write-Info "output   : $dll"

    & $csc /nologo /target:library /nostdlib+ /noconfig @refs /out:"$dll" $modSource

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dll)) {
        Write-Bad 'Compilation failed. Errors are printed above.'
        exit 1
    }

    Write-Ok "built $([math]::Round((Get-Item $dll).Length / 1KB, 1)) KB"

    # The game compiles EVERY .cs it finds under the mod folder (recursively, so hiding one in
    # a subfolder does not help) and would then see the same classes twice.  A pre-built DLL
    # therefore has to be the only thing in there.  The master copy of the source lives in the
    # repo at mod\CS1ToBeamNGExporter.cs, so nothing is lost.
    $sources = Get-ChildItem -LiteralPath $modFolder -Recurse -File -Force | Where-Object { $_.Extension -eq '.cs' }
    foreach ($source in $sources) {
        Remove-Item $source.FullName -Force
        Write-Info "removed $($source.Name) from the mod folder (a .dll and a .cs cannot coexist)"
    }

    # Clean up the now-empty backup folder from earlier versions of this script.
    $stale = Join-Path $modFolder 'source-backup'
    if (Test-Path $stale) {
        Remove-Item $stale -Recurse -Force
        Write-Info 'removed stale source-backup\ folder'
    }

    Write-Ok 'Mod folder now contains the DLL only.'
    Write-Info 'Restore source-mode any time by copying mod\CS1ToBeamNGExporter.cs back in and deleting the .dll.'
    Write-Info 'Now fully restart the game (or run this script with -Restart).'
    exit 0
}

# ---------------------------------------------------------------------------------------
#  Show current state
# ---------------------------------------------------------------------------------------
Write-Head 'Cities: Skylines :: CS1-to-BeamNG exporter mod status'

Write-Info "game        : $game"
Write-Info "log         : $logPath"
Write-Info "mod folder  : $modFolder"
Write-Host ''

if (-not (Test-Path $modFolder)) {
    Write-Bad "The mod folder does not exist. Create it and copy the .cs file in:"
    Write-Host "         $modFolder" -ForegroundColor Yellow
} else {
    $files = Get-ChildItem -LiteralPath $modFolder -File -Force
    if ($files.Count -eq 0) {
        Write-Bad 'The mod folder is EMPTY. Copy mod\CS1ToBeamNGExporter.cs into it.'
    } else {
        foreach ($file in $files) {
            Write-Ok ("{0,-34} {1,9:N0} bytes" -f $file.Name, $file.Length)
        }

        $hasSource = $files | Where-Object { $_.Extension -eq '.cs' }
        $hasDll = $files | Where-Object { $_.Extension -eq '.dll' }

        if ($hasDll -and $hasSource) {
            Write-Bad 'BOTH a .cs and a .dll are present -- the game would compile the source and then'
            Write-Host '         see the same classes twice. Keep only one of them:' -ForegroundColor Red
            Write-Host '           - keep the .cs  -> the game compiles it at startup (delete the .dll)' -ForegroundColor Yellow
            Write-Host '           - keep the .dll -> fastest and most reliable (delete the .cs)' -ForegroundColor Yellow
        } elseif ($hasDll) {
            Write-Ok 'DLL only -- the game loads it directly, nothing to compile.'
        } elseif ($hasSource) {
            Write-Ok 'source only -- the game will compile it at startup.'
        } else {
            Write-Bad 'Neither a .cs nor a .dll is present.'
        }

        if ((Get-ChildItem -LiteralPath $modFolder -Directory -Force | Where-Object { $_.Name -eq 'source-backup' })) {
            Write-Info 'source-backup\ holds the .cs used by the last -Build (safe to restore by moving it up).'
        }
    }
}

Write-Host ''
if (Test-Path $compiledMods) {
    $built = Get-ChildItem -LiteralPath $compiledMods -File -Force | Where-Object { $_.Name -like 'CS1ToBeamNG*' }
    if ($built) {
        foreach ($item in $built) { Write-Ok "compiled output: $($item.FullName)" }
    } else {
        Write-Info 'No CS1ToBeamNG*.dll in Cities_Data\Mods yet (the game has not compiled it).'
    }
} else {
    Write-Info 'Cities_Data\Mods does not exist yet (the game creates it when it compiles a source mod).'
}

# ---------------------------------------------------------------------------------------
#  -Restart : close the game, archive the log, relaunch
# ---------------------------------------------------------------------------------------
if ($Restart) {
    Write-Head 'Restarting the game'

    $running = Get-Process -Name 'Cities' -ErrorAction SilentlyContinue
    if ($running) {
        Write-Info "closing $($running.Count) running Cities.exe process(es)..."
        $running | ForEach-Object { $_.CloseMainWindow() | Out-Null }
        Start-Sleep -Seconds 3
        Get-Process -Name 'Cities' -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 2
        Write-Ok 'game closed'
    } else {
        Write-Info 'game was not running'
    }

    if (Test-Path $logPath) {
        $archive = Join-Path $game ("Cities_Data\output_log.previous-{0:yyyyMMdd-HHmmss}.txt" -f (Get-Date))
        Move-Item $logPath $archive -Force
        Write-Info "archived old log -> $(Split-Path -Leaf $archive)"
    }

    Write-Info 'launching Cities.exe ...'
    Start-Process -FilePath (Join-Path $game 'Cities.exe') -WorkingDirectory $game
    Write-Ok 'game launching. Give it ~30 seconds, then watch below.'

    # Wait for the log to appear so the tail below has something to read.
    $waited = 0
    while (-not (Test-Path $logPath) -and $waited -lt 120) {
        Start-Sleep -Seconds 2
        $waited += 2
    }

    Write-Host ''
}

# ---------------------------------------------------------------------------------------
#  Tail the log, highlighting the lines that matter
# ---------------------------------------------------------------------------------------
Write-Head 'Watching the log for mod load / compile activity'

$patterns = @{
    'No source files found' = 'Red'
    'error CS'              = 'Red'
    'Compilation failed'    = 'Red'
    'Exception'             = 'Red'
    'compil'                = 'Yellow'
    'CS1ToBeamNG'           = 'Green'
    '\[Mods - Internal\]'   = 'DarkGray'
}

if (-not (Test-Path $logPath)) {
    Write-Warn2 "No log yet at $logPath"
    Write-Info 'Start the game, then run this script again.'
    exit 1
}

Write-Info "reading $logPath"
if ($Follow) { Write-Info 'press Ctrl+C to stop' }
Write-Host ''

# Print the mod-relevant lines that are already there, so there is immediate feedback.
$existing = Select-String -Path $logPath -Pattern 'CS1ToBeamNG|No source files found|error CS' -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host '  --- mod-related lines already in the log ---' -ForegroundColor DarkGray
    foreach ($match in $existing) {
        $colour = if ($match.Line -match 'error CS|No source files found') { 'Red' } else { 'Green' }
        Write-Host "  $($match.LineNumber): $($match.Line.Trim())" -ForegroundColor $colour
    }
    Write-Host ''
} else {
    Write-Warn2 'Nothing about this mod is in the log yet.'
    Write-Info 'That usually means the game has not been restarted since you copied the file in.'
    Write-Host ''
}

if (-not $Follow) {
    Write-Info 'Run with -Follow to watch live, or -Restart to relaunch the game and watch.'
    exit 0
}

$lastLength = (Get-Item $logPath).Length
while ($true) {
    Start-Sleep -Seconds 1

    $current = Get-Item $logPath -ErrorAction SilentlyContinue
    if (-not $current) { continue }

    if ($current.Length -lt $lastLength) {
        # The game truncated/recreated the log (a restart happened).
        $lastLength = 0
        Write-Host '  --- log restarted ---' -ForegroundColor DarkGray
    }

    if ($current.Length -gt $lastLength) {
        try {
            $stream = [System.IO.File]::Open($logPath, 'Open', 'Read', 'ReadWrite')
            $stream.Seek($lastLength, 'Begin') | Out-Null
            $reader = New-Object System.IO.StreamReader($stream)
            $chunk = $reader.ReadToEnd()
            $reader.Close()
            $stream.Close()
            $lastLength = $current.Length
        } catch {
            continue
        }

        foreach ($line in ($chunk -split "`r?`n")) {
            $trimmed = $line.Trim()
            if (-not $trimmed) { continue }
            if ($trimmed -match 'Filename: C:/buildslave') { continue }

            foreach ($pattern in $patterns.Keys) {
                if ($trimmed -match $pattern) {
                    Write-Host "  $trimmed" -ForegroundColor $patterns[$pattern]
                    break
                }
            }
        }
    }
}
