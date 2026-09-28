# Local launcher -> runs the WHOLE clip pipeline on the cloud (Hostinger) and downloads the result.
# Nothing heavy runs locally: this only syncs the small scripts, triggers the cloud run, and scp's the mp4 back.
# Usage:  powershell -File cloud_clip.ps1 c4-live-events  [outNameSuffix]
param([Parameter(Mandatory=$true)][string]$Clip, [string]$Suffix = "v1")
$ErrorActionPreference = "Stop"
# --- CONFIGURE THESE for your server (see config.example.json) ---
$key = "$env:USERPROFILE\.ssh\YOUR_SSH_KEY"          # path to your private key
$srv = "root@YOUR_SERVER_IP"                          # your render box
$ca  = "/home/youruser/clip-assembly"                 # server work dir (source, transcript, scripts, assets)
$hp  = "/home/youruser/remotion-editor"               # your Remotion project dir
# -----------------------------------------------------------------
$d   = Split-Path -Parent $MyInvocation.MyCommand.Path
$o   = @("-i",$key,"-o","StrictHostKeyChecking=no","-o","ConnectTimeout=40")

Write-Host "[sync] uploading scripts..." -ForegroundColor Cyan
& scp.exe @o "$d\assemble_impromptu.py" "$d\build_manifest_impromptu.py" "$d\make_bullet_card.py" "$d\classify_speakers.py" "$d\render_clip.sh" "${srv}:$ca/"

Write-Host "[cloud] assembling + rendering $Clip on Hostinger (this is all server-side)..." -ForegroundColor Cyan
& ssh.exe @o "-o" "ServerAliveInterval=20" "-o" "ServerAliveCountMax=40" $srv "bash $ca/render_clip.sh $Clip"

$dest = "$env:USERPROFILE\Downloads\$Clip-$Suffix-1080p.mp4"
Write-Host "[get] downloading -> $dest" -ForegroundColor Cyan
& scp.exe @o "${srv}:$hp/out/$Clip-1080p.mp4" $dest
Get-Item $dest | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
Write-Host "DONE" -ForegroundColor Green
