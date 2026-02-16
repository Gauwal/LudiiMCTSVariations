#!/bin/bash
#
#SBATCH --job-name=mcts_T1593
#SBATCH --output=planned_T1593_%j.out
#SBATCH --error=planned_T1593_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=12G
#SBATCH --time=00:15:10

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1593 on $(hostname) at $(date)"
echo "Game: Dai Seireigi"
echo "Variant: AG0 | Random | AlphaGo | Robust"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=12G, time=00:15:10"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1593" --out "${OUT_DIR}/T1593.csv"

echo "Job completed at $(date)"
