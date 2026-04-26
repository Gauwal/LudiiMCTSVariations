#!/bin/bash
#SBATCH --job-name=ludii_fractional
#SBATCH --output=slurm_sweep_full_dataset/slurm_logs/fractional_%j.log
#SBATCH --error=slurm_sweep_full_dataset/slurm_logs/fractional_%j.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-4

# ============================================================================
# SLURM Submission Script: Single Fractional Sample Experiment
# ============================================================================
#
# Called by submit_fractional_all.sh — do not run directly.
#
# Arguments:
#   $1  method   "baseline" or "warm"
#
# SLURM_ARRAY_TASK_ID is used as the random seed (0-4 → 5 seeds).
# ============================================================================

METHOD="${1:-baseline}"

PROJECT_ROOT="/home/users/g/s/gsavary/LudiiMCTSVariations"

mkdir -p "${PROJECT_ROOT}/slurm_sweep_full_dataset/slurm_logs"

SEED=${SLURM_ARRAY_TASK_ID:-0}

OUTPUT_DIR="${PROJECT_ROOT}/slurm_sweep_full_dataset/output_fractional/${METHOD}/seed_${SEED}"

cd "${PROJECT_ROOT}" || exit 1

source "/home/users/g/s/gsavary/venvs/myproj/bin/activate"

echo "============================================================"
echo "Fractional warm start experiment"
echo "Method: ${METHOD}"
echo "Seed:   ${SEED}"
echo "Output: ${OUTPUT_DIR}"
echo "============================================================"

python slurm_sweep_full_dataset/main_sweep_fractional.py \
    --method      "${METHOD}" \
    --time-limit  3600        \
    --seed        "${SEED}"   \
    --batch-size  20          \
    --output-dir  "${OUTPUT_DIR}"

echo "Done. Results in: ${OUTPUT_DIR}"
