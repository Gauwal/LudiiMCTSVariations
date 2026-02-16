#!/bin/bash
#
#SBATCH --job-name=mcts_T586
#SBATCH --output=planned_T586_%j.out
#SBATCH --error=planned_T586_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=00:11:04

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T586 on $(hostname) at $(date)"
echo "Game: Guerrilla Checkers"
echo "Variant: Alpha-Beta | MAST | Score Bounded | MaxAvgScore"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=4, mem=7G, time=00:11:04"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T586" --out "${OUT_DIR}/T586.csv"

echo "Job completed at $(date)"
