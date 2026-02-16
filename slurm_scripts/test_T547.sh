#!/bin/bash
#
#SBATCH --job-name=mcts_T547
#SBATCH --output=planned_T547_%j.out
#SBATCH --error=planned_T547_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=00:10:40

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T547 on $(hostname) at $(date)"
echo "Game: Selayar Game"
echo "Variant: Noisy AG0 | NST | Qualitative | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=7G, time=00:10:40"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T547" --out "${OUT_DIR}/T547.csv"

echo "Job completed at $(date)"
