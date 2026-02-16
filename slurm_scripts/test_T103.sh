#!/bin/bash
#
#SBATCH --job-name=mcts_T103
#SBATCH --output=planned_T103_%j.out
#SBATCH --error=planned_T103_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=10G
#SBATCH --time=00:13:28

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T103 on $(hostname) at $(date)"
echo "Game: Chu Seireigi"
echo "Variant: Alpha-Beta | Random | Heuristic | Robust"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=10G, time=00:13:28"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T103" --out "${OUT_DIR}/T103.csv"

echo "Job completed at $(date)"
