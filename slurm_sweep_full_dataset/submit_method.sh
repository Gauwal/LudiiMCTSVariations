#!/bin/bash
#SBATCH --job-name=ludii_sweep
#SBATCH --output=slurm_logs/sweep_%j.log
#SBATCH --error=slurm_logs/sweep_%j.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-4

# ============================================================================
# SLURM Submission Script for Single Method (Baseline or Warm-Start)
# ============================================================================
# 
# This script is called by submit_all.sh with METHOD as first argument.
# DO NOT use this directly; use submit_all.sh instead.
#
# Usage (from submit_all.sh):
#   sbatch submit_method.sh baseline
#   sbatch submit_method.sh warm:50
#
# With array jobs (5 seeds):
#   sbatch --array=0-4 submit_method.sh baseline
#
# ============================================================================

# Method passed as argument
METHOD="${1:-baseline}"

# Set project root (MODIFY THIS to match your workspace)
PROJECT_ROOT="${HOME}/LudiiMCTSVariations"

# Create log directory if it doesn't exist
mkdir -p "${PROJECT_ROOT}/slurm_sweep_full_dataset/slurm_logs"

# Timestamp for unique output directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="${PROJECT_ROOT}/slurm_sweep_full_dataset/results_${TIMESTAMP}"

# Use SLURM_ARRAY_TASK_ID as seed (0-4 for 5 parallel seeds)
SEED=${SLURM_ARRAY_TASK_ID:-0}

# Go to project root
cd "${PROJECT_ROOT}" || exit 1

# Load any necessary modules (adjust for your cluster)
# module load python/3.10
# module load cuda/11.8

# Activate virtual environment
source ".venv/Scripts/activate"

# Run the experiment
echo "Starting experiment..."
echo "Project root: ${PROJECT_ROOT}"
echo "Method: ${METHOD}"
echo "Output dir: ${OUTPUT_DIR}"
echo "Seed: ${SEED}"
echo "Time limit: ${SLURM_TIME_LIMIT} seconds"
echo ""

python slurm_sweep_full_dataset/main_sweep.py \
    --method "${METHOD}" \
    --time-limit 7200 \
    --seed ${SEED} \
    --batch-size 20 \
    --output-dir "${OUTPUT_DIR}"

echo "Experiment finished. Results saved to: ${OUTPUT_DIR}"
