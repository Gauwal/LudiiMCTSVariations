#!/bin/bash
#
#SBATCH --job-name=mcts_T972
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T972_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T972_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests_combo_timevar.csv"
OUT_DIR="/home/ucl/ingi/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results"
mkdir -p "${OUT_DIR}"

echo "Running T972 on $(hostname) at $(date)"
echo "Game: Hasami Shogi"
echo "Variant: McGRAVE | MAST | Qualitative | Robust"
echo "Meta: moveTime=2.0, gamesPerMatchup=100, maxMoves=2000"
echo "Estimated: cpus=4, mem=7G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T972" --out "${OUT_DIR}/T972.csv"

echo "Job completed at $(date)"
