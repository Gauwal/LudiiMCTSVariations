#!/bin/bash
#
#SBATCH --job-name=mcts_T14
#SBATCH --output=planned_T14_%j.out
#SBATCH --error=planned_T14_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=8G
#SBATCH --time=00:12:08

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T14 on $(hostname) at $(date)"
echo "Game: Shakhmaty (Early Modern)"
echo "Variant: Progressive Widening | MAST | Qualitative | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=8G, time=00:12:08"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T14" --out "${OUT_DIR}/T14.csv"

echo "Job completed at $(date)"
