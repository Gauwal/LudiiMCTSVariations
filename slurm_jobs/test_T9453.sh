#!/bin/bash
#
#SBATCH --job-name=mcts_T9453
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T9453_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T9453_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=15:18:13

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T9453 on $(hostname) at $(date)"
echo "Game: Adhesion"
echo "Variant: UCB1 | Random | Qualitative | Robust"
echo "Meta: moveTime=0.2, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=4, mem=7G, time=15:18:13"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T9453" --out "${OUT_DIR}/T9453.csv"

echo "Job completed at $(date)"
