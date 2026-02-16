#!/bin/bash
#
#SBATCH --job-name=mcts_T1767
#SBATCH --output=planned_T1767_%j.out
#SBATCH --error=planned_T1767_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:11:50

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1767 on $(hostname) at $(date)"
echo "Game: Shogi"
echo "Variant: UCB1 tuned | MAST | Score Bounded | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=8G, time=00:11:50"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1767" --out "${OUT_DIR}/T1767.csv"

echo "Job completed at $(date)"
