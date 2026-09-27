param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$PdfLaTeX = "pdflatex",
    [string]$BibTeX = "bibtex",
    [switch]$SkipLatex,
    [switch]$SkipFreezeVerification,
    [switch]$ReviewerArtifact
)

# Rebuild every paper-facing analysis from tracked physical captures. The
# temporary database prevents a reproduction audit from mutating the canonical
# research database while still exercising the normal publication path.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TemporaryDatabase = Join-Path $RepoRoot "tmp\paper2_arc_reproduction.sqlite3"
# A unique pytest root avoids Windows cleanup failures when a prior audit was
# interrupted while antivirus or an editor still held a directory handle.
$PytestRunId = "{0}-{1}" -f $PID, ([guid]::NewGuid().ToString("N"))
$PytestTemp = Join-Path $RepoRoot "tmp\pytest-paper2-arc-$PytestRunId"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TemporaryDatabase) | Out-Null
New-Item -ItemType Directory -Force -Path $PytestTemp | Out-Null

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$WorkingDirectory = $RepoRoot
    )

    # PowerShell does not stop automatically when a native executable returns
    # nonzero, so convert every tool failure into an immediate audit failure.
    Push-Location $WorkingDirectory
    try {
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Executable failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

Invoke-Checked $Python @("-m", "src.hardware.analyze_sparse_balanced_physical")

$ControlledRoot = "fpga/docs/captures/sparse_refinement_accelerator_v2"
Invoke-Checked $Python @(
    "-m", "src.hardware.analyze_sparse_hierarchical_commit_physical",
    "--capture", "$ControlledRoot/hierarchical_commit_suite_controlled_masks_physical/physical_zybo_sparse_hierarchical_commit_suite.txt",
    "--manifest", "fpga/generated/sparse_refinement_accelerator_v1/hierarchical_mask_suite_controlled_shapes_v1/manifest.json",
    "--board-ready", "results/tables/sparse_hierarchical_commit_controlled_masks_board_ready.json",
    "--timing", "$ControlledRoot/hierarchical_commit_suite_controlled_masks_physical/route/timing_summary.txt",
    "--utilization", "$ControlledRoot/hierarchical_commit_suite_controlled_masks_physical/route/utilization.txt",
    "--output-json", "results/tables/sparse_hierarchical_commit_controlled_masks_physical.json",
    "--output-markdown", "results/tables/sparse_hierarchical_commit_controlled_masks_physical.md",
    "--output-tex", "docs/paper/generated/sparse_hierarchical_commit_controlled_masks_physical.tex",
    "--database", $TemporaryDatabase,
    "--record-set", "reproduction.paper2.controlled_58p824",
    "--overwrite"
)
Invoke-Checked $Python @(
    "-m", "src.hardware.analyze_sparse_hierarchical_commit_physical",
    "--capture", "$ControlledRoot/hierarchical_commit_suite_controlled_masks_50mhz_physical/physical_zybo_sparse_hierarchical_commit_suite.txt",
    "--manifest", "fpga/generated/sparse_refinement_accelerator_v1/hierarchical_mask_suite_controlled_shapes_50mhz_v1/manifest.json",
    "--board-ready", "results/tables/sparse_hierarchical_commit_controlled_masks_50mhz_board_ready.json",
    "--timing", "$ControlledRoot/hierarchical_commit_suite_controlled_masks_50mhz_physical/route/timing_summary.txt",
    "--utilization", "$ControlledRoot/hierarchical_commit_suite_controlled_masks_50mhz_physical/route/utilization.txt",
    "--output-json", "results/tables/sparse_hierarchical_commit_controlled_masks_50mhz_physical.json",
    "--output-markdown", "results/tables/sparse_hierarchical_commit_controlled_masks_50mhz_physical.md",
    "--output-tex", "docs/paper/generated/sparse_hierarchical_commit_controlled_masks_50mhz_physical.tex",
    "--database", $TemporaryDatabase,
    "--record-set", "reproduction.paper2.controlled_50",
    "--overwrite"
)

# Rebuild the architecture-only temporal table before the paper summary
# consumes it. The frozen selector remains rejected; this reproduces only the
# physical worklist-scaling evidence reported by the FPGA paper.
Invoke-Checked $Python @(
    "-m", "src.hardware.analyze_sparse_independent_worklists",
    "--database", $TemporaryDatabase,
    "--record-set", "reproduction.paper2.independent_worklists",
    "--overwrite"
)

# Validate the closure generator on a second finite-support DAG using only
# deterministic synthetic integers. This is software contract evidence, not a
# routed or physical second accelerator.
Invoke-Checked $Python @(
    "-m", "src.hardware.validate_finite_receptive_field_closure"
)

# The complete repository audits sealed 126b/126c primary evidence. The compact
# reviewer package intentionally contains only their frozen disposition records
# and verifies those hashes later; it does not claim to regenerate every route,
# XSA, log, or historical experiment.
if (-not $ReviewerArtifact) {
    Invoke-Checked $Python @(
        "-m", "src.hardware.analyze_sparse_same_clock_organization_control_126b_adverse",
        "--check"
    )
    Invoke-Checked $Python @(
        "-m", "src.hardware.analyze_sparse_same_clock_organization_control_126c_terminal",
        "--check"
    )
}

Invoke-Checked $Python @("-m", "src.hardware.analyze_sparse_accelerator_paper")
Invoke-Checked $Python @("-m", "src.hardware.analyze_sparse_architecture_ablation")
Invoke-Checked $Python @("-m", "src.hardware.verify_paper2_successor_diagnostics")
Invoke-Checked $Python @("-B", "scripts/paper2_conventional_comparison_v1/replay_physical.py")
Invoke-Checked $Python @("-B", "scripts/paper2_conventional_comparison_v1/replay_safety.py")
Invoke-Checked $Python @("-m", "src.report.paper2_roi_publication")
Invoke-Checked $Python @("-m", "src.hardware.analyze_sparse_realtime_envelope")
Invoke-Checked $Python @("-m", "src.hardware.analyze_sparse_deadline_traces")
Invoke-Checked $Python @("-m", "src.hardware.analyze_sparse_postroute_power")
Invoke-Checked $Python @(
    "-m", "src.hardware.analyze_tang_sparse_commit_candidate",
    "--database", $TemporaryDatabase
)
Invoke-Checked $Python @(
    "-m", "src.hardware.audit_sparse_accelerator_evidence",
    "--output-json", "results/tables/paper2_physical_evidence_index.json",
    "--output-markdown", "artifact/paper2_arc/PHYSICAL_EVIDENCE_INDEX.md"
)
Invoke-Checked $Python @("-m", "src.report.plot_sparse_accelerator_paper_figures")

$FocusedTests = @(
    "tests/test_paper2_roi_publication.py",
    "tests/test_paper2_roi_public_replay.py",
    "tests/test_paper2_successor_publication.py",
    "tests/test_analyze_sparse_balanced_physical.py",
    "tests/test_analyze_sparse_accelerator_paper.py",
    "tests/test_analyze_sparse_architecture_ablation.py",
    "tests/test_analyze_sparse_realtime_envelope.py",
    "tests/test_analyze_sparse_hierarchical_commit_physical.py",
    "tests/test_analyze_sparse_deadline_traces.py",
    "tests/test_analyze_sparse_independent_worklists.py",
    "tests/test_analyze_sparse_postroute_power.py",
    "tests/test_analyze_tang_sparse_commit_candidate.py",
    "tests/test_audit_sparse_accelerator_evidence.py",
    "tests/test_plot_sparse_accelerator_paper_figures.py",
    "tests/test_sparse_accelerator_exactness_proof.py",
    "tests/test_paper2_strengthening_experiment_contracts.py",
    "tests/test_validate_finite_receptive_field_closure.py"
)

# The full repository regression also checks vector export and immutable Git
# history. The anonymous reviewer package deliberately excludes checkpoints,
# Git metadata, and unrelated model code, so its reproduction run keeps only
# the tests needed to regenerate and audit every reported paper result.
if (-not $ReviewerArtifact) {
    $FocusedTests += @(
        "tests/test_analyze_sparse_same_clock_organization_control_126b_adverse.py",
        "tests/test_analyze_sparse_same_clock_organization_control_126c_terminal.py",
        "tests/test_export_sparse_hierarchical_mask_suite.py",
        "tests/test_freeze_sparse_accelerator_fccm.py",
        "tests/test_freeze_sparse_accelerator_submission.py",
        "tests/test_paper2_reviewer_artifact.py",
        "tests/test_sparse_refinement_accelerator_paper.py",
        "tests/test_sparse_matched_control_130_feasibility.py"
    )
}
Invoke-Checked $Python (
    @("-m", "pytest") +
    $FocusedTests +
    @("-q", "-p", "no:cacheprovider", "--basetemp", $PytestTemp, "-k", "not manuscript and not retrospective_applicability")
)

if (-not $SkipLatex) {
    # Fixed source-date metadata makes the archived PDF reproducible across
    # clean builds instead of changing its hash every time LaTeX runs.
    $env:SOURCE_DATE_EPOCH = "1785628800"
    $env:FORCE_SOURCE_DATE = "1"
    $PaperDirectory = Join-Path $RepoRoot "docs\paper"
    Invoke-Checked $PdfLaTeX @("-interaction=nonstopmode", "-halt-on-error", "sparse_refinement_accelerator.tex") $PaperDirectory
    Invoke-Checked $BibTeX @("sparse_refinement_accelerator") $PaperDirectory
    Invoke-Checked $PdfLaTeX @("-interaction=nonstopmode", "-halt-on-error", "sparse_refinement_accelerator.tex") $PaperDirectory
    Invoke-Checked $PdfLaTeX @("-interaction=nonstopmode", "-halt-on-error", "sparse_refinement_accelerator.tex") $PaperDirectory
}

# Preserve the earlier FCCM V1 freeze as archival provenance. This verifies the
# immutable historical Git object; it does not define the current ARC template.
if (-not $SkipFreezeVerification) {
    Invoke-Checked $Python @("-m", "src.export.freeze_sparse_accelerator_fccm", "--verify")
}
Write-Host "PAPER2_ARC_REPRODUCTION_PASS"
