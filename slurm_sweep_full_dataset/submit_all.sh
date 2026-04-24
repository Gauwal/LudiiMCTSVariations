#!/bin/bash
#
# ============================================================================
# Master Script: Submit All Independent Jobs
# ============================================================================
#
# This script submits independent SLURM jobs for:
#   - Baseline (5 seeds in parallel)
#   - Warm w=5 (5 seeds in parallel)
#   - Warm w=20 (5 seeds in parallel)
#   - Warm w=50 (5 seeds in parallel)
#   - Warm w=100 (5 seeds in parallel)
#   - Warm w=200 (5 seeds in parallel)
#   - Warm w=500 (5 seeds in parallel)
#
# All jobs run in parallel, each with --array=0-4 (5 seeds each).
#
# USAGE:
#   bash submit_all.sh              # Submit all jobs
#   bash submit_all.sh --dry-run    # Show what would be submitted
#
# SETUP (first time):
#   1. Edit submit_method.sh and set PROJECT_ROOT to your workspace
#   2. mkdir -p slurm_sweep_full_dataset/slurm_logs
#   3. bash submit_all.sh
#
# ============================================================================

# Check if dry-run mode
DRY_RUN=0
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=1
    echo "DRY RUN MODE - showing commands without submitting"
    echo ""
fi

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Methods to run (baseline + all warm weights)
METHODS=("baseline" "warm:5" "warm:20" "warm:50" "warm:100" "warm:200" "warm:500")

echo "============================================================================"
echo "Submitting Independent SLURM Jobs"
echo "============================================================================"
echo ""
echo "Jobs to submit:"
for method in "${METHODS[@]}"; do
    echo "  - ${method} (5 seeds: 0-4 in parallel)"
done
echo ""
echo "Each job will run independently and in parallel."
echo "Total: 7 methods × 5 seeds = 35 runs"
echo ""

# Submit jobs
JOB_IDS=()
for method in "${METHODS[@]}"; do
    echo "Submitting ${method}..."
    
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "  [DRY RUN] sbatch --array=0-4 ${SCRIPT_DIR}/submit_method.sh ${method}"
    else
        JOB_ID=$(sbatch --array=0-4 "${SCRIPT_DIR}/submit_method.sh" "${method}" | awk '{print $4}')
        JOB_IDS+=($JOB_ID)
        echo "  Submitted job ID: ${JOB_ID}"
    fi
done

echo ""
echo "============================================================================"
if [[ $DRY_RUN -eq 1 ]]; then
    echo "Dry run complete. No jobs were actually submitted."
else
    echo "All jobs submitted!"
    echo ""
    echo "Job IDs: ${JOB_IDS[@]}"
    echo ""
    echo "Monitor progress with:"
    echo "  squeue -u \$USER"
    echo ""
    echo "View logs:"
    echo "  tail -f ${SCRIPT_DIR}/slurm_logs/sweep_*.log"
    echo ""
    echo "Results will be saved to:"
    echo "  ${SCRIPT_DIR}/results_YYYYMMDD_HHMMSS/"
fi
echo "============================================================================"
