#!/bin/bash
#
#SBATCH --job-name=mcts_T1763
#SBATCH --output=planned_T1763_%j.out
#SBATCH --error=planned_T1763_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:10:53

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1763 on $(hostname) at $(date)"
echo "Game: La Dama"
echo "Variant: McBRAVE | MAST | Implicit Minimax | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:10:53"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1763" --out "${OUT_DIR}/T1763.csv"

echo "Job completed at $(date)"
