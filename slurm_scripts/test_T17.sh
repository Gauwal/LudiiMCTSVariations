#!/bin/bash
#
#SBATCH --job-name=mcts_T17
#SBATCH --output=planned_T17_%j.out
#SBATCH --error=planned_T17_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=10G
#SBATCH --time=00:16:46

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T17 on $(hostname) at $(date)"
echo "Game: Ringo"
echo "Variant: Alpha-Beta | MAST | Qualitative | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=10G, time=00:16:46"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T17" --out "${OUT_DIR}/T17.csv"

echo "Job completed at $(date)"
