#!/bin/bash
#
#SBATCH --job-name=mcts_T47
#SBATCH --output=planned_T47_%j.out
#SBATCH --error=planned_T47_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=38G
#SBATCH --time=00:37:15

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T47 on $(hostname) at $(date)"
echo "Game: Taikyoku Shogi"
echo "Variant: McGRAVE | Random | AlphaGo | Robust"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=38G, time=00:37:15"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T47" --out "${OUT_DIR}/T47.csv"

echo "Job completed at $(date)"
