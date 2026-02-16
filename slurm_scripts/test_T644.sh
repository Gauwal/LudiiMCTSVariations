#!/bin/bash
#
#SBATCH --job-name=mcts_T644
#SBATCH --output=planned_T644_%j.out
#SBATCH --error=planned_T644_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=00:11:18

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T644 on $(hostname) at $(date)"
echo "Game: Dots and Boxes"
echo "Variant: Progressive History | NST | Implicit Minimax | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=7G, time=00:11:18"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T644" --out "${OUT_DIR}/T644.csv"

echo "Job completed at $(date)"
