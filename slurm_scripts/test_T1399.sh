#!/bin/bash
#
#SBATCH --job-name=mcts_T1399
#SBATCH --output=planned_T1399_%j.out
#SBATCH --error=planned_T1399_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:10:52

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1399 on $(hostname) at $(date)"
echo "Game: Lay Gwet Kyah"
echo "Variant: McBRAVE | Random | Heuristic | Robust"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:10:52"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1399" --out "${OUT_DIR}/T1399.csv"

echo "Job completed at $(date)"
