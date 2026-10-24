param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$ArtifactRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
& $Python -B (Join-Path $ArtifactRoot "reproduce.py")
if ($LASTEXITCODE -ne 0) { throw "Artifact replay failed with exit code $LASTEXITCODE" }
