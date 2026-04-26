#!/bin/bash
#
# ============================================================================
# Master Script: Submit All Decay Sweep Jobs
# ============================================================================
#
# Submits independent SLURM array jobs (5 seeds each) for:
#   - 1 baseline (no decay, no warm-start)
#   - w=50  × 8 decay rates  =  8 array jobs
#   - w=200 × 8 decay rates  =  8 array jobs
#   Total: 17 array jobs × 5 seeds = 85 individual runs
#
# Decay rates tested (exponential mode):
#   0.00   No decay            (synthetic stays forever)
#   0.025  Very slow           (2.5% removed per batch)
#   0.05   Slow                (5%  removed per batch)
#   0.075  Slow-medium         (7.5% removed per batch)
#   0.10   Medium              (10% removed per batch)
#   0.15   Medium-fast         (15% removed per batch)
#   0.20   Fast                (20% removed per batch)
#   0.50   Almost instant      (50% removed per batch)
#
# Results are stored under:
#   slurm_sweep_full_dataset/output_decay/
#
# USAGE:
#   bash submit_decay_all.sh            # submit everything
#   bash submit_decay_all.sh --dry-run  # preview without submitting
#
# ============================================================================

set -e

DRY_RUN=0
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=1
    echo "DRY RUN MODE — showing commands without submitting"
    echo ""
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
METHOD_SCRIPT="${SCRIPT_DIR}/submit_decay_method.sh"

DECAY_RATES=(0.00 0.025 0.05 0.075 0.10 0.15 0.20 0.50 0.90)
WARM_WEIGHTS=(50 200)

echo "============================================================================"
echo "Submitting Decay Sweep Jobs"
echo "============================================================================"
echo ""
echo "Warm weights : ${WARM_WEIGHTS[*]}"
echo "Decay rates  : ${DECAY_RATES[*]}"
echo "Seeds        : 0-4 (via SLURM array)"
echo ""
total_jobs=$(( 1 + ${#WARM_WEIGHTS[@]} * ${#DECAY_RATES[@]} ))
echo "Array jobs to submit : ${total_jobs}  (× 5 seeds = $((total_jobs * 5)) runs total)"
echo ""

JOB_IDS=()

# -----------------------------------------------------------------------
# 1. Baseline (single job, no decay, no warm-start)
# -----------------------------------------------------------------------
echo "Submitting: baseline (no warm-start, no decay)..."
if [[ $DRY_RUN -eq 1 ]]; then
    echo "  [DRY RUN] sbatch --array=0-4 ${METHOD_SCRIPT} baseline none 0.0"
else
    JOB_ID=$(sbatch --array=0-4 "${METHOD_SCRIPT}" baseline none 0.0 | awk '{print $4}')
    JOB_IDS+=("${JOB_ID}")
    echo "  Submitted job ID: ${JOB_ID}"
fi

# -----------------------------------------------------------------------
# 2. Warm-start with decay for each weight × each decay rate
# -----------------------------------------------------------------------
for weight in "${WARM_WEIGHTS[@]}"; do
    echo ""
    echo "Submitting: warm:${weight} (8 decay rates × 5 seeds)..."
    for rate in "${DECAY_RATES[@]}"; do
        label="warm:${weight} exponential decay=${rate}"
        if [[ $DRY_RUN -eq 1 ]]; then
            echo "  [DRY RUN] sbatch --array=0-4 ${METHOD_SCRIPT} warm:${weight} exponential ${rate}"
        else
            JOB_ID=$(sbatch --array=0-4 "${METHOD_SCRIPT}" "warm:${weight}" exponential "${rate}" | awk '{print $4}')
            JOB_IDS+=("${JOB_ID}")
            echo "  [${label}] job ID: ${JOB_ID}"
        fi
    done
done

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
echo ""
echo "============================================================================"
if [[ $DRY_RUN -eq 1 ]]; then
    echo "Dry run complete — no jobs were submitted."
else
    echo "All jobs submitted!"
    echo ""
    echo "Job IDs: ${JOB_IDS[*]}"
    echo ""
    echo "Monitor:"
    echo "  squeue -u \$USER"
    echo ""
    echo "Logs:"
    echo "  tail -f slurm_sweep_full_dataset/slurm_logs/decay_*.log"
    echo ""
    echo "Results directory:"
    echo "  slurm_sweep_full_dataset/output_decay/"
fi
echo "============================================================================"
