#!/bin/bash
#
#SBATCH --job-name=mcts_T810
#SBATCH --output=planned_T810_%j.out
#SBATCH --error=planned_T810_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:10:47

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T810 on $(hostname) at $(date)"
echo "Game: Abalala'e"
echo "Variant: UCB1 tuned | NST | AlphaGo | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:10:47"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T810" --out "${OUT_DIR}/T810.csv"

echo "Job completed at $(date)"
