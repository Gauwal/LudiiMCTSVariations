#!/bin/bash
#
#SBATCH --job-name=mcts_T9863
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T9863_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T9863_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=76:25:33

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T9863 on $(hostname) at $(date)"
echo "Game: Chaturanga (12x12)"
echo "Variant: UCB1 | Random | MonteCarlo | Proportional Exp"
echo "Meta: moveTime=1.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=4, mem=8G, time=76:25:33"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T9863" --out "${OUT_DIR}/T9863.csv"

echo "Job completed at $(date)"
