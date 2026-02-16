#!/bin/bash
#
#SBATCH --job-name=mcts_T1607
#SBATCH --output=planned_T1607_%j.out
#SBATCH --error=planned_T1607_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:10:39

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1607 on $(hostname) at $(date)"
echo "Game: Yaguarete Kora"
echo "Variant: Progressive Bias | MAST | Qualitative | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:10:39"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1607" --out "${OUT_DIR}/T1607.csv"

echo "Job completed at $(date)"
