#!/bin/bash
#SBATCH --job-name=ludii_decay
#SBATCH --output=slurm_sweep_full_dataset/slurm_logs/decay_%j.log
#SBATCH --error=slurm_sweep_full_dataset/slurm_logs/decay_%j.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --array=0-4

# ============================================================================
# SLURM Submission Script: Single Decay Experiment
# ============================================================================
#
# Called by submit_decay_all.sh — do not run directly.
#
# Arguments (positional):
#   $1  method      e.g. "baseline" or "warm:50"
#   $2  decay_mode  e.g. "none" or "exponential"
#   $3  decay_param e.g. "0.10"
#
# SLURM_ARRAY_TASK_ID is used as the random seed (0-4 → 5 seeds).
# ============================================================================

METHOD="${1:-baseline}"
DECAY_MODE="${2:-none}"
DECAY_PARAM="${3:-0.0}"

PROJECT_ROOT="/home/users/g/s/gsavary/LudiiMCTSVariations"

mkdir -p "${PROJECT_ROOT}/slurm_sweep_full_dataset/slurm_logs"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SEED=${SLURM_ARRAY_TASK_ID:-0}

# Sanitise decay param for directory name (replace . with _)
DECAY_LABEL=$(echo "${DECAY_PARAM}" | sed 's/\./_/g')
METHOD_LABEL=$(echo "${METHOD}" | sed 's/:/_/g')

OUTPUT_DIR="${PROJECT_ROOT}/slurm_sweep_full_dataset/output_decay/${METHOD_LABEL}_decay_${DECAY_MODE}_${DECAY_LABEL}/seed_${SEED}"

cd "${PROJECT_ROOT}" || exit 1

source "/home/users/g/s/gsavary/venvs/myproj/bin/activate"

echo "============================================================"
echo "Decay sweep experiment"
echo "Method:      ${METHOD}"
echo "Decay mode:  ${DECAY_MODE}"
echo "Decay param: ${DECAY_PARAM}"
echo "Seed:        ${SEED}"
echo "Output:      ${OUTPUT_DIR}"
echo "============================================================"

python slurm_sweep_full_dataset/main_sweep_decay.py \
    --method       "${METHOD}"      \
    --decay-mode   "${DECAY_MODE}"  \
    --decay-param  "${DECAY_PARAM}" \
    --time-limit   3600             \
    --seed         "${SEED}"        \
    --batch-size   20               \
    --output-dir   "${OUTPUT_DIR}"

echo "Done. Results in: ${OUTPUT_DIR}"
