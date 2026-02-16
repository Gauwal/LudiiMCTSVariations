#!/bin/bash
#
#SBATCH --job-name=mcts_T146
#SBATCH --output=planned_T146_%j.out
#SBATCH --error=planned_T146_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=9G
#SBATCH --time=00:15:20

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T146 on $(hostname) at $(date)"
echo "Game: Bravalath"
echo "Variant: UCB1 GRAVE | MAST | Score Bounded | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=9G, time=00:15:20"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T146" --out "${OUT_DIR}/T146.csv"

echo "Job completed at $(date)"
