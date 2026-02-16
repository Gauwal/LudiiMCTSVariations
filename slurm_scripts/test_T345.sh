#!/bin/bash
#
#SBATCH --job-name=mcts_T345
#SBATCH --output=planned_T345_%j.out
#SBATCH --error=planned_T345_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=10G
#SBATCH --time=00:16:53

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T345 on $(hostname) at $(date)"
echo "Game: Trax"
echo "Variant: McGRAVE | NST | Qualitative | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=10G, time=00:16:53"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T345" --out "${OUT_DIR}/T345.csv"

echo "Job completed at $(date)"
