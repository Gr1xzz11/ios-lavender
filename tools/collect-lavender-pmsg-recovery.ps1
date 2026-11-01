#requires -Version 5.1
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_.:-]+$')][string]$Serial,
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$OutDir,
    [ValidateRange(1,600)][int]$TimeoutSeconds = 90
)
$ErrorActionPreference = 'Stop'
$adbPath = (Get-Command adb -CommandType Application -ErrorAction Stop).Source
$capturePath = [IO.Path]::GetFullPath($OutDir)
if ([IO.File]::Exists($capturePath)) { throw "Output path is a file: $capturePath" }
# Preserve partial and completed attempts. Never overwrite earlier evidence.
if ([IO.Directory]::Exists($capturePath)) {
    $capturePath = Join-Path $capturePath ('attempt-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
$captureDir = [IO.Directory]::CreateDirectory($capturePath)
$results = New-Object 'System.Collections.Generic.List[object]'

function ConvertTo-WindowsArgument([AllowEmptyString()][string]$Value) {
    # Windows CreateProcess/CRT quoting, including quotes and trailing backslashes.
    # ProcessStartInfo.ArgumentList does not exist in Windows PowerShell 5.1/.NET Framework.
    $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Save-AdbBytes([string[]]$AdbArguments, [string]$Name) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $adbPath
    $info.Arguments = (($AdbArguments | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join ' ')
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $proc = New-Object Diagnostics.Process
    $proc.StartInfo = $info
    $stream = $null
    $timedOut = $false
    try {
        if (-not $proc.Start()) { throw "Failed to start adb for $Name" }
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        $stream = [IO.File]::Create((Join-Path $capturePath $Name))
        $copyTask = $proc.StandardOutput.BaseStream.CopyToAsync($stream)
        if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
            $timedOut = $true
            $proc.Kill() # Stop the local adb client only; no remote action.
            $proc.WaitForExit()
        }
        [void]$copyTask.GetAwaiter().GetResult()
        $stderrText = $stderrTask.GetAwaiter().GetResult()
        $exitCode = $proc.ExitCode
        $stream.Dispose()
        $stream = $null
        [IO.File]::WriteAllText((Join-Path $capturePath "$Name.stderr.txt"), [string]$stderrText)
        [IO.File]::WriteAllText((Join-Path $capturePath "$Name.exit.txt"), [string]$exitCode)
        $bytes = (Get-Item -LiteralPath (Join-Path $capturePath $Name)).Length
        $result = [pscustomobject]@{ Name=$Name; Arguments=$AdbArguments; ExitCode=$exitCode; Bytes=$bytes; TimedOut=$timedOut }
        $results.Add($result)
        if ($exitCode -ne 0 -or $timedOut) {
            Write-Warning "$Name failed (exit=$exitCode, timeout=$timedOut); stderr and partial stdout preserved."
        } elseif ($bytes -eq 0) {
            Write-Warning "$Name returned empty stdout (exit=0); recorded as empty, not as a valid record."
        }
        return $result
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $proc.Dispose()
    }
}

function Save-Remote([string]$Command, [string]$Name) {
    # This recovery lacks a usable binary-clean shell-v2 path. exec-out is binary
    # clean but merges stderr and loses remote exit status. FD 3 streams stdout;
    # command substitution captures stderr, then a unique trailer carries status.
    # Shell substitution removes trailing newlines from stderr (not from stdout).
    $token = 'RN7_CAPTURE_' + [Guid]::NewGuid().ToString('N')
    $template = @'
{ capture_err=$( { __COMMAND__; } 2>&1 1>&3); capture_rc=$?; printf '\n__TOKEN__:%s:%s:END__TOKEN__\n' "$capture_rc" "$(printf '%s' "$capture_err" | base64 | tr -d '\r\n')"; } 3>&1
'@
    $remote = $template.Replace('__COMMAND__',$Command).Replace('__TOKEN__',$token)
    $result = Save-AdbBytes -AdbArguments @('-s', $Serial, 'exec-out', $remote) -Name $Name
    $result | Add-Member -NotePropertyName TransportExitCode -NotePropertyValue $result.ExitCode
    $result | Add-Member -NotePropertyName FramingValid -NotePropertyValue $false
    $path = Join-Path $capturePath $Name
    $file = [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite)
    try {
        $tailSize = [int][Math]::Min(65536,$file.Length)
        $tail = New-Object byte[] $tailSize
        [void]$file.Seek(-$tailSize,[IO.SeekOrigin]::End)
        $read = $file.Read($tail,0,$tailSize)
        $tailText = [Text.Encoding]::ASCII.GetString($tail,0,$read)
        $match = [regex]::Match($tailText, "`n${token}:([0-9]+):([A-Za-z0-9+/=]*):END${token}`n$")
        if ($result.TransportExitCode -eq 0 -and -not $result.TimedOut -and $match.Success) {
            $result.ExitCode = [int]$match.Groups[1].Value
            $remoteError = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($match.Groups[2].Value))
            $file.SetLength($file.Length - $read + $match.Index)
            $result.Bytes = $file.Length
            $result.FramingValid = $true
            [IO.File]::AppendAllText((Join-Path $capturePath "$Name.stderr.txt"),$remoteError)
        } else {
            # Preserve unparsed stdout as evidence, but never claim it is a valid capture.
            $result.ExitCode = -1
            [IO.File]::AppendAllText((Join-Path $capturePath "$Name.stderr.txt"),'Missing/invalid remote status trailer; output is unvalidated.')
        }
        [IO.File]::WriteAllText((Join-Path $capturePath "$Name.exit.txt"),[string]$result.ExitCode)
    } finally { $file.Dispose() }
    if ($result.ExitCode -ne 0) { Write-Warning "$Name remote capture failed (exit=$($result.ExitCode)); see stderr." }
    elseif ($result.Bytes -eq 0) { Write-Warning "$Name returned empty stdout (exit=0)." }
    return $result
}

$completed = $false
try {
    $state = Save-AdbBytes -AdbArguments @('-s', $Serial, 'get-state') -Name 'adb-state.txt'
    $stateText = [IO.File]::ReadAllText((Join-Path $capturePath 'adb-state.txt')).Trim()
    if ($state.ExitCode -ne 0 -or $state.TimedOut -or $stateText -ne 'recovery') {
        throw "Expected selected device in recovery, got '$stateText'; see adb-state.txt.stderr.txt."
    }
    [void](Save-AdbBytes -AdbArguments @('devices','-l') -Name 'adb-devices.txt')
    [IO.File]::WriteAllText((Join-Path $capturePath 'host.txt'), "PowerShell=$($PSVersionTable.PSVersion)`r`nEdition=$($PSVersionTable.PSEdition)`r`nADB=$adbPath`r`nCaptured=$(Get-Date -Format o)`r`n")
    # Separate commands retain each exit code; a later successful command cannot hide a failure.
    $commands = [ordered]@{
        'uname.txt'='uname -a'
        'id.txt'='id'
        'getprop.txt'='getprop'
        'version.txt'='cat /proc/version'
        'cmdline.txt'='cat /proc/cmdline'
        'uptime.txt'='cat /proc/uptime'
        'config.gz'='cat /proc/config.gz'
        'iomem.txt'='cat /proc/iomem'
        'pstore-list.txt'='ls -la /sys/fs/pstore'
        'pmsg-device.txt'='ls -l /dev/pmsg0'
        'devmem.txt'='ls -l /dev/mem'
        'mounts.txt'='cat /proc/mounts'
        'dmesg.txt'='dmesg'
        'pmsg.bin'='cat /sys/fs/pstore/pmsg-ramoops-0'
        'console.bin'='cat /sys/fs/pstore/console-ramoops-0'
        'recovery-node.txt'='ls -l /dev/block/by-name/recovery'
        'recovery-realpath.txt'='readlink -f /dev/block/by-name/recovery'
        'recovery-size.txt'='blockdev --getsize64 /dev/block/by-name/recovery'
        'recovery-partition.img'='cat /dev/block/by-name/recovery'
    }
    foreach ($item in $commands.GetEnumerator()) { [void](Save-Remote -Command $item.Value -Name $item.Key) }
    foreach ($parameter in @('mem_address','mem_size','console_size','pmsg_size','record_size','ftrace_size','ecc','mem_type')) {
        [void](Save-Remote -Command "cat /sys/module/ramoops/parameters/$parameter" -Name "ramoops-$parameter.txt")
    }
    $completed = $true
} finally {
    # Save a manifest even when a required check or a local IO operation fails.
    $manifest = [pscustomobject]@{ Completed=$completed; PowerShell=[string]$PSVersionTable.PSVersion; Results=@($results.ToArray()) }
    [IO.File]::WriteAllText((Join-Path $capturePath 'capture.json'), ($manifest | ConvertTo-Json -Depth 6))
    Get-ChildItem -LiteralPath $capturePath -File | Where-Object { $_.Name -ne 'SHA256.csv' } |
        Get-FileHash -Algorithm SHA256 | Select-Object Path,Hash |
        Export-Csv -LiteralPath (Join-Path $capturePath 'SHA256.csv') -NoTypeInformation
}
Write-Output $capturePath
