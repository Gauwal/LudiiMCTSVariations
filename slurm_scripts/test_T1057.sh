#!/bin/bash
#
#SBATCH --job-name=mcts_T1057
#SBATCH --output=planned_T1057_%j.out
#SBATCH --error=planned_T1057_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:11:55

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1057 on $(hostname) at $(date)"
echo "Game: Shatranj (14x14)"
echo "Variant: McBRAVE | Random | Qualitative | Robust"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=8G, time=00:11:55"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1057" --out "${OUT_DIR}/T1057.csv"

echo "Job completed at $(date)"
