# Reads each video's length from Windows (no extra software needed) into durations.json.
# Cached by path + size + modified time, so re-runs only read new or changed files.
# Run:  powershell -ExecutionPolicy Bypass -File get-durations.ps1     then: python build.py
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$out = Join-Path $PSScriptRoot 'durations.json'
$exts = '.mp4', '.mkv', '.m4v', '.avi', '.flv', '.mov', '.webm', '.wmv'

$cache = @{}
if (Test-Path -LiteralPath $out) {
    (Get-Content -LiteralPath $out -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $cache[$_.Name] = $_.Value }
}

$shell = New-Object -ComObject Shell.Application
$folders = @{}
$result = [ordered]@{}
$read = 0; $missing = 0
$files = Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {
    $exts -contains $_.Extension.ToLower() -and $_.FullName -notlike "$PSScriptRoot*" }

foreach ($f in $files) {
    $rel = $f.FullName.Substring($root.Length + 1).Replace('\', '/')
    $stamp = "$($f.Length):$($f.LastWriteTimeUtc.Ticks)"
    $c = $cache[$rel]
    if ($c -and $c.s -eq $stamp) { $result[$rel] = $c; continue }
    $secs = $null
    try {
        if (-not $folders.ContainsKey($f.DirectoryName)) { $folders[$f.DirectoryName] = $shell.Namespace($f.DirectoryName) }
        $item = $folders[$f.DirectoryName].ParseName($f.Name)
        $ticks = $item.ExtendedProperty('System.Media.Duration')
        if ($ticks) { $secs = [math]::Round([double]$ticks / 1e7) }
    } catch { }
    if (-not $secs) { $missing++ }
    $result[$rel] = [ordered]@{ d = $secs; s = $stamp }
    $read++
    if ($read % 200 -eq 0) { Write-Host "  read $read files..." }
}

$result | ConvertTo-Json -Depth 3 -Compress | Set-Content -LiteralPath $out -Encoding UTF8
Write-Host "$($files.Count) videos: $read read now, $($files.Count - $read) from cache, $missing with no length available"
