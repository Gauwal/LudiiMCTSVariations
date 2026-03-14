#!/bin/bash
#
#SBATCH --job-name=mcts_T5436
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T5436_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T5436_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=152:49:10

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T5436 on $(hostname) at $(date)"
echo "Game: Patok"
echo "Variant: UCB1 | Random | MonteCarlo | Robust"
echo "Meta: moveTime=2.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=7G, time=152:49:10"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T5436" --out "${OUT_DIR}/T5436.csv"

echo "Job completed at $(date)"
