#!/bin/bash
#
#SBATCH --job-name=mcts_T1051
#SBATCH --output=planned_T1051_%j.out
#SBATCH --error=planned_T1051_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=00:11:54

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1051 on $(hostname) at $(date)"
echo "Game: Alea Evangelii"
echo "Variant: Noisy AG0 | MAST | Qualitative | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=7G, time=00:11:54"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1051" --out "${OUT_DIR}/T1051.csv"

echo "Job completed at $(date)"
