#!/bin/bash
#
# ============================================================================
# Master Script: Submit Fractional Warm Start Jobs
# ============================================================================
#
# Submits 2 array jobs (5 seeds each) = 10 runs total:
#   - baseline  (cold start, control)
#   - warm      (single fractional sample prior)
#
# Results go to:
#   slurm_sweep_full_dataset/output_fractional/
#
# USAGE:
#   bash submit_fractional_all.sh            # submit
#   bash submit_fractional_all.sh --dry-run  # preview
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
METHOD_SCRIPT="${SCRIPT_DIR}/submit_fractional_method.sh"

METHODS=("baseline" "warm")

echo "============================================================================"
echo "Submitting Fractional Warm Start Jobs"
echo "============================================================================"
echo ""
echo "Methods : ${METHODS[*]}"
echo "Seeds   : 0-4 (via SLURM array)"
echo "Total   : $((${#METHODS[@]} * 5)) runs"
echo ""

JOB_IDS=()

for method in "${METHODS[@]}"; do
    echo "Submitting: ${method}..."
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "  [DRY RUN] sbatch --array=0-4 ${METHOD_SCRIPT} ${method}"
    else
        JOB_ID=$(sbatch --array=0-4 "${METHOD_SCRIPT}" "${method}" | awk '{print $4}')
        JOB_IDS+=("${JOB_ID}")
        echo "  Submitted job ID: ${JOB_ID}"
    fi
done

echo ""
echo "============================================================================"
if [[ $DRY_RUN -eq 1 ]]; then
    echo "Dry run complete — no jobs were submitted."
else
    echo "All jobs submitted!"
    echo ""
    echo "Job IDs: ${JOB_IDS[*]}"
    echo ""
    echo "Monitor:  squeue -u \$USER"
    echo "Logs:     tail -f slurm_sweep_full_dataset/slurm_logs/fractional_*.log"
    echo "Results:  slurm_sweep_full_dataset/output_fractional/"
fi
echo "============================================================================"
