#!/bin/bash
#
#SBATCH --job-name=mcts_T995
#SBATCH --output=planned_T995_%j.out
#SBATCH --error=planned_T995_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:10:38

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T995 on $(hostname) at $(date)"
echo "Game: Xonin Shatar (Complex)"
echo "Variant: ExIt | MAST | Qualitative | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:10:38"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T995" --out "${OUT_DIR}/T995.csv"

echo "Job completed at $(date)"
