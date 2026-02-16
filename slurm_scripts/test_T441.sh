#!/bin/bash
#
#SBATCH --job-name=mcts_T441
#SBATCH --output=planned_T441_%j.out
#SBATCH --error=planned_T441_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=19G
#SBATCH --time=00:21:35

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T441 on $(hostname) at $(date)"
echo "Game: Tai Shogi"
echo "Variant: Implicit Minimax | NST | Heuristic | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=19G, time=00:21:35"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T441" --out "${OUT_DIR}/T441.csv"

echo "Job completed at $(date)"
