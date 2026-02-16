#!/bin/bash
#
#SBATCH --job-name=mcts_T1570
#SBATCH --output=planned_T1570_%j.out
#SBATCH --error=planned_T1570_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=11G
#SBATCH --time=00:14:48

module load Java

PROJECT_DIR="/home/user/g/s/gsavary/LudiiMCTSVariations"
LUDII_JAR="/home/user/g/s/gsavary/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="results"
mkdir -p "${OUT_DIR}"

echo "Running T1570 on $(hostname) at $(date)"
echo "Game: Tenjiku Shogi"
echo "Variant: Progressive Bias | NST | Heuristic | Proportional Exp"
echo "Meta: moveTime=0.1, gamesPerMatchup=10, maxMoves=500"
echo "Estimated: cpus=5, mem=11G, time=00:14:48"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1570" --out "${OUT_DIR}/T1570.csv"

echo "Job completed at $(date)"
