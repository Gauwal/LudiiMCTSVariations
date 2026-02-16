#!/bin/bash
#
#SBATCH --job-name=mcts_T2
#SBATCH --output=planned_T2_%j.out
#SBATCH --error=planned_T2_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=11G
#SBATCH --time=00:17:14

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T2 on $(hostname) at $(date)"
echo "Game: Kriegsspiel"
echo "Variant: UCB1 tuned | MAST | Heuristic | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=11G, time=00:17:14"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T2" --out "${OUT_DIR}/T2.csv"

echo "Job completed at $(date)"
