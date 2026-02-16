#!/bin/bash
#
#SBATCH --job-name=mcts_T401
#SBATCH --output=planned_T401_%j.out
#SBATCH --error=planned_T401_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=19G
#SBATCH --time=00:21:24

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T401 on $(hostname) at $(date)"
echo "Game: Tai Shogi"
echo "Variant: Progressive History | MAST | Score Bounded | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=19G, time=00:21:24"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T401" --out "${OUT_DIR}/T401.csv"

echo "Job completed at $(date)"
