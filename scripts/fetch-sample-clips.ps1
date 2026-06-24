# Download a small set of sample clips into data/clips/ for the Week 2 demo.
#
# The guaranteed source is OpenCV's BSD-licensed `vtest.avi` (pedestrian
# surveillance footage). Each of the four demo cameras gets its own clip file so
# you can drop in your own footage per camera later. Extra public clips are
# fetched best-effort to add visual variety; if a download fails we fall back to
# vtest.avi so the demo always has something to play.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$clipsDir = Join-Path (Get-Location) "data/clips"
New-Item -ItemType Directory -Force -Path $clipsDir | Out-Null

function Get-File($url, $dest) {
    try {
        Write-Host "Downloading $url"
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 120
        if ((Get-Item $dest).Length -lt 1024) {
            throw "downloaded file too small"
        }
        return $true
    } catch {
        Write-Warning "Failed to download $url : $($_.Exception.Message)"
        if (Test-Path $dest) { Remove-Item $dest -Force }
        return $false
    }
}

# 1) Guaranteed base clip (BSD-licensed, OpenCV samples).
$base = Join-Path $clipsDir "vtest.avi"
if (-not (Test-Path $base)) {
    $ok = Get-File "https://github.com/opencv/opencv/raw/master/samples/data/vtest.avi" $base
    if (-not $ok) {
        Write-Error "Could not download the base clip (vtest.avi). Place a clip at $base manually and re-run."
    }
}

# 2) Best-effort extra clips (used for variety if they succeed).
$extras = @{
    "people-768.avi" = "https://github.com/opencv/opencv_extra/raw/master/testdata/cv/video/768x576.avi"
}
foreach ($name in $extras.Keys) {
    $dest = Join-Path $clipsDir $name
    if (-not (Test-Path $dest)) { Get-File $extras[$name] $dest | Out-Null }
}

# 3) Materialize one clip file per demo camera. Prefer an extra clip where we
#    have one, otherwise fall back to the guaranteed base clip.
$peopleAlt = Join-Path $clipsDir "people-768.avi"
$alt = $base
if (Test-Path $peopleAlt) { $alt = $peopleAlt }
$cameraSources = @{
    "cam-dock-1.avi"  = $base
    "cam-dock-2.avi"  = $alt
    "cam-lobby-1.avi" = $base
    "cam-lot-1.avi"   = $alt
}
foreach ($name in $cameraSources.Keys) {
    $dest = Join-Path $clipsDir $name
    Copy-Item $cameraSources[$name] $dest -Force
    Write-Host "Prepared $name"
}

Write-Host ""
Write-Host "Clips ready in data/clips/:"
Get-ChildItem $clipsDir -Filter "cam-*.avi" | ForEach-Object { Write-Host "  $($_.Name) ($([math]::Round($_.Length/1MB,2)) MB)" }
Write-Host ""
Write-Host "Tip: replace any cam-*.avi with your own footage for that camera, then rebuild the sampler image."
