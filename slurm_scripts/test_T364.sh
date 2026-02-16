#!/bin/bash
#
#SBATCH --job-name=mcts_T364
#SBATCH --output=planned_T364_%j.out
#SBATCH --error=planned_T364_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:11:05

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T364 on $(hostname) at $(date)"
echo "Game: Fractal"
echo "Variant: Noisy AG0 | Random | Heuristic | Robust"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:11:05"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T364" --out "${OUT_DIR}/T364.csv"

echo "Job completed at $(date)"
