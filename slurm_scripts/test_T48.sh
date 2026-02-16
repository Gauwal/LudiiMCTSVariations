#!/bin/bash
#
#SBATCH --job-name=mcts_T48
#SBATCH --output=planned_T48_%j.out
#SBATCH --error=planned_T48_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=00:10:44

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T48 on $(hostname) at $(date)"
echo "Game: Connect Four"
echo "Variant: Alpha-Beta | NST | Heuristic | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=7G, time=00:10:44"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T48" --out "${OUT_DIR}/T48.csv"

echo "Job completed at $(date)"
