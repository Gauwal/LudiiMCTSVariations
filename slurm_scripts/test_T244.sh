#!/bin/bash
#
#SBATCH --job-name=mcts_T244
#SBATCH --output=planned_T244_%j.out
#SBATCH --error=planned_T244_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:10:56

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T244 on $(hostname) at $(date)"
echo "Game: Altan Xaraacaj"
echo "Variant: McGRAVE | NST | Implicit Minimax | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:10:56"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T244" --out "${OUT_DIR}/T244.csv"

echo "Job completed at $(date)"
