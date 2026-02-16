#!/bin/bash
#
#SBATCH --job-name=mcts_T1808
#SBATCH --output=planned_T1808_%j.out
#SBATCH --error=planned_T1808_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:11:09

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1808 on $(hostname) at $(date)"
echo "Game: Shafran Chess"
echo "Variant: Implicit Minimax | MAST | Implicit Minimax | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:11:09"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1808" --out "${OUT_DIR}/T1808.csv"

echo "Job completed at $(date)"
