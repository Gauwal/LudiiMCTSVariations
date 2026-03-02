#!/bin/bash
#
#SBATCH --job-name=mcts_T1471
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1471_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1471_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=01:15:06

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T1471 on $(hostname) at $(date)"
echo "Game: Selus"
echo "Variant: UCB1 GRAVE | NST | Heuristic | Proportional Exp"
echo "Meta: moveTime=0.2, gamesPerMatchup=10, maxMoves=1000"
echo "Estimated: cpus=4, mem=7G, time=01:15:06"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1471" --out "${OUT_DIR}/T1471.csv"

echo "Job completed at $(date)"
