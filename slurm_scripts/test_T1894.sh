#!/bin/bash
#
#SBATCH --job-name=mcts_T1894
#SBATCH --output=planned_T1894_%j.out
#SBATCH --error=planned_T1894_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:10:58

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1894 on $(hostname) at $(date)"
echo "Game: Five Men's Morris"
echo "Variant: Progressive Widening | MAST | AlphaGo | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:10:58"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1894" --out "${OUT_DIR}/T1894.csv"

echo "Job completed at $(date)"
