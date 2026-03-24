#!/bin/bash
#
#SBATCH --job-name=mcts_T410
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T410_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T410_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=8G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests_combo_timevar.csv"
OUT_DIR="/home/ucl/ingi/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results"
mkdir -p "${OUT_DIR}"

echo "Running T410 on $(hostname) at $(date)"
echo "Game: Patok"
echo "Variant: AG0 | MAST | Heuristic | Robust"
echo "Meta: moveTime=0.5, gamesPerMatchup=100, maxMoves=2000"
echo "Estimated: cpus=5, mem=8G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T410" --out "${OUT_DIR}/T410.csv"

echo "Job completed at $(date)"
