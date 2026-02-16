#!/bin/bash
#
#SBATCH --job-name=mcts_T681
#SBATCH --output=planned_T681_%j.out
#SBATCH --error=planned_T681_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=8G
#SBATCH --time=00:12:15

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T681 on $(hostname) at $(date)"
echo "Game: Chaturanga (14x14)"
echo "Variant: McBRAVE | NST | Score Bounded | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=8G, time=00:12:15"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T681" --out "${OUT_DIR}/T681.csv"

echo "Job completed at $(date)"
