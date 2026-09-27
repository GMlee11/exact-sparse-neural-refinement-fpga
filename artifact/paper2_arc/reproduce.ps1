param(
    [string]$Python = "python",
    [string]$PdfLaTeX = "pdflatex",
    [string]$BibTeX = "bibtex",
    [switch]$SkipLatex = $true
)

# This public entry point is non-mutating. It copies the exact FILES.txt
# dependency closure into an external temporary directory, runs the worker
# there, audits the candidates there, and removes the temporary tree.
$ErrorActionPreference = "Stop"
$ReleaseRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$FilesPath = Join-Path $PSScriptRoot "FILES.txt"
$ExpectedPath = Join-Path $PSScriptRoot "expected_outputs.json"
$ReplayRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "paper2_arc_replay_" + [guid]::NewGuid().ToString("N")
)

if (-not (Test-Path -LiteralPath $ExpectedPath)) {
    throw "missing expected-output manifest: $ExpectedPath"
}

function Get-Allowlist {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "missing release allowlist: $Path"
    }
    $Entries = @(
        Get-Content -LiteralPath $Path |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith("#") }
    )
    if ($Entries.Count -eq 0 -or @($Entries | Select-Object -Unique).Count -ne $Entries.Count) {
        throw "release allowlist is empty or contains duplicate paths"
    }
    return $Entries
}

function Get-AllowlistSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$Entries
    )

    $Snapshot = [ordered]@{}
    foreach ($RelativePath in $Entries) {
        if ([IO.Path]::IsPathRooted($RelativePath) -or $RelativePath.Contains("..")) {
            throw "unsafe release allowlist path: $RelativePath"
        }
        $SourcePath = Join-Path $Root $RelativePath
        if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
            throw "allowlisted release file is missing: $RelativePath"
        }
        $Snapshot[$RelativePath] = (
            Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256
        ).Hash.ToLowerInvariant()
    }
    return $Snapshot
}

function Assert-SameSnapshot {
    param(
        [Parameter(Mandatory = $true)]$Before,
        [Parameter(Mandatory = $true)]$After
    )

    if ($Before.Count -ne $After.Count) {
        throw "release allowlist changed during replay"
    }
    foreach ($Key in $Before.Keys) {
        if (-not $After.Contains($Key) -or $Before[$Key] -cne $After[$Key]) {
            throw "release file changed during replay: $Key"
        }
    }
}

function Assert-PdfContentMatchExceptTrailerId {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$AcceptedBytes,
        [Parameter(Mandatory = $true)]
        [byte[]]$RebuiltBytes
    )

    if ($AcceptedBytes.Length -ne $RebuiltBytes.Length) {
        throw "rebuilt PDF size differs from the frozen PDF"
    }

    $Latin1 = [Text.Encoding]::GetEncoding(28591)
    $Pattern = '/ID\s*\[<([0-9A-Fa-f]{32})>\s*<([0-9A-Fa-f]{32})>\]'
    $AcceptedMatches = [regex]::Matches($Latin1.GetString($AcceptedBytes), $Pattern)
    $RebuiltMatches = [regex]::Matches($Latin1.GetString($RebuiltBytes), $Pattern)
    if ($AcceptedMatches.Count -ne 1 -or $RebuiltMatches.Count -ne 1) {
        throw "each PDF must contain exactly one well-formed duplicated trailer ID record"
    }

    $AcceptedMatch = $AcceptedMatches[0]
    $RebuiltMatch = $RebuiltMatches[0]
    if (
        $AcceptedMatch.Groups[1].Value -cne $AcceptedMatch.Groups[2].Value -or
        $RebuiltMatch.Groups[1].Value -cne $RebuiltMatch.Groups[2].Value
    ) {
        throw "each PDF trailer ID must repeat the same 32-hex value"
    }
    if ($AcceptedMatch.Length -ne $RebuiltMatch.Length) {
        throw "PDF trailer ID records differ in length"
    }

    $AcceptedNormalized = [byte[]]$AcceptedBytes.Clone()
    $RebuiltNormalized = [byte[]]$RebuiltBytes.Clone()
    foreach ($GroupIndex in 1, 2) {
        $AcceptedGroup = $AcceptedMatch.Groups[$GroupIndex]
        $RebuiltGroup = $RebuiltMatch.Groups[$GroupIndex]
        for ($Index = 0; $Index -lt $AcceptedGroup.Length; $Index++) {
            $AcceptedNormalized[$AcceptedGroup.Index + $Index] = 0x30
            $RebuiltNormalized[$RebuiltGroup.Index + $Index] = 0x30
        }
    }
    for ($Index = 0; $Index -lt $AcceptedNormalized.Length; $Index++) {
        if ($AcceptedNormalized[$Index] -ne $RebuiltNormalized[$Index]) {
            throw "rebuilt PDF differs outside its trailer ID"
        }
    }

    Write-Host "PAPER2_ARC_LATEX_CONTENT_MATCH_PASS trailer_id_only"
}

function Get-ExpectedOutputIdentity {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$HashMode
    )

    [byte[]]$Bytes = [IO.File]::ReadAllBytes($Path)
    if ($HashMode -eq "crlf_to_lf_fail_closed") {
        $Normalized = New-Object 'System.Collections.Generic.List[byte]'
        for ($Index = 0; $Index -lt $Bytes.Length; $Index++) {
            if ($Bytes[$Index] -eq 13) {
                if ($Index + 1 -ge $Bytes.Length -or $Bytes[$Index + 1] -ne 10) {
                    throw "expected text output contains unsupported bare CR: $Path"
                }
                $Normalized.Add(10)
                $Index++
            }
            else {
                $Normalized.Add($Bytes[$Index])
            }
        }
        [byte[]]$IdentityBytes = $Normalized.ToArray()
    }
    elseif ($HashMode -eq "raw_bytes") {
        [byte[]]$IdentityBytes = $Bytes
    }
    else {
        throw "unsupported expected-output hash mode: $HashMode"
    }

    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $HashBytes = $Hasher.ComputeHash($IdentityBytes)
    }
    finally {
        $Hasher.Dispose()
    }
    return [pscustomobject]@{
        sha256 = ([BitConverter]::ToString($HashBytes)).Replace("-", "").ToLowerInvariant()
        size_bytes = $IdentityBytes.Length
    }
}

$Allowlist = Get-Allowlist -Path $FilesPath
$ReleaseBefore = Get-AllowlistSnapshot -Root $ReleaseRoot -Entries $Allowlist
$Expected = Get-Content -LiteralPath $ExpectedPath -Raw | ConvertFrom-Json
$FrozenPdfBytes = $null

try {
    New-Item -ItemType Directory -Path $ReplayRoot -ErrorAction Stop | Out-Null
    foreach ($RelativePath in $Allowlist) {
        $SourcePath = Join-Path $ReleaseRoot $RelativePath
        $DestinationPath = Join-Path $ReplayRoot $RelativePath
        $DestinationDirectory = Split-Path -Parent $DestinationPath
        if (-not (Test-Path -LiteralPath $DestinationDirectory)) {
            New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
        }
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath
    }

    $WorkExpectedPath = Join-Path $ReplayRoot "artifact\paper2_arc\expected_outputs.json"
    $WorkReproduceScript = Join-Path $ReplayRoot "scripts\reproduce_paper2_arc.ps1"
    if (-not (Test-Path -LiteralPath $WorkExpectedPath -PathType Leaf)) {
        throw "staged expected-output manifest is missing"
    }
    if (-not (Test-Path -LiteralPath $WorkReproduceScript -PathType Leaf)) {
        throw "staged reproduction worker is missing"
    }

    if (-not $SkipLatex) {
        $PdfArtifacts = @($Expected.artifacts | Where-Object {
            $_.path -eq "docs/paper/sparse_refinement_accelerator.pdf"
        })
        if ($PdfArtifacts.Count -ne 1) {
            throw "expected-output manifest must contain exactly one manuscript PDF"
        }
        $FrozenPdfPath = Join-Path $ReleaseRoot $PdfArtifacts[0].path
        if (-not (Test-Path -LiteralPath $FrozenPdfPath -PathType Leaf)) {
            throw "frozen manuscript PDF is missing before rebuild"
        }
        $FrozenPdfHash = (
            Get-FileHash -LiteralPath $FrozenPdfPath -Algorithm SHA256
        ).Hash.ToLowerInvariant()
        if ($FrozenPdfHash -ne $PdfArtifacts[0].sha256) {
            throw "frozen manuscript PDF hash is invalid before rebuild"
        }
        $FrozenPdfBytes = [IO.File]::ReadAllBytes($FrozenPdfPath)
    }

    # Starting a scoped child avoids the default execution policy and keeps
    # every generated candidate under the external replay root.
    $ReproduceArguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $WorkReproduceScript,
        "-Python", $Python,
        "-PdfLaTeX", $PdfLaTeX,
        "-BibTeX", $BibTeX,
        "-ReviewerArtifact",
        "-SkipFreezeVerification"
    )
    if ($SkipLatex) {
        $ReproduceArguments += "-SkipLatex"
    }

    Push-Location $ReplayRoot
    try {
        & powershell @ReproduceArguments
        if ($LASTEXITCODE -ne 0) {
            throw "paper reproduction failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }

    foreach ($Artifact in $Expected.artifacts) {
        if ($SkipLatex -and $Artifact.requires_latex) {
            continue
        }
        $ArtifactPath = Join-Path $ReplayRoot $Artifact.path
        if (-not (Test-Path -LiteralPath $ArtifactPath -PathType Leaf)) {
            throw "expected output is missing: $($Artifact.path)"
        }
        $ActualIdentity = Get-ExpectedOutputIdentity `
            -Path $ArtifactPath `
            -HashMode ([string]$Artifact.hash_mode)
        if (
            $ActualIdentity.sha256 -ne $Artifact.sha256 -or
            $ActualIdentity.size_bytes -ne $Artifact.size_bytes
        ) {
            if (
                -not $SkipLatex -and
                $Artifact.path -eq "docs/paper/sparse_refinement_accelerator.pdf"
            ) {
                Assert-PdfContentMatchExceptTrailerId `
                    -AcceptedBytes $FrozenPdfBytes `
                    -RebuiltBytes ([IO.File]::ReadAllBytes($ArtifactPath))
                continue
            }
            throw "identity mismatch for $($Artifact.path): expected $($Artifact.sha256)/$($Artifact.size_bytes), got $($ActualIdentity.sha256)/$($ActualIdentity.size_bytes)"
        }
    }

    $ReleaseAfter = Get-AllowlistSnapshot -Root $ReleaseRoot -Entries $Allowlist
    Assert-SameSnapshot -Before $ReleaseBefore -After $ReleaseAfter
    Write-Host "PAPER2_ARC_RELEASE_TREE_IMMUTABLE_PASS"
    Write-Host "PAPER2_ARC_ARTIFACT_HASHES_PASS"
}
finally {
    if (Test-Path -LiteralPath $ReplayRoot) {
        $ResolvedReplayRoot = [IO.Path]::GetFullPath($ReplayRoot)
        $ResolvedTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        if (-not $ResolvedReplayRoot.StartsWith($ResolvedTempRoot, [StringComparison]::OrdinalIgnoreCase) -or
            [IO.Path]::GetFileName($ResolvedReplayRoot) -notmatch '^paper2_arc_replay_[0-9a-f]{32}$') {
            throw "Unsafe replay cleanup target: $ResolvedReplayRoot"
        }
        Remove-Item -LiteralPath $ResolvedReplayRoot -Recurse -Force
    }
}
