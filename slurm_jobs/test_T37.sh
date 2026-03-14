#!/bin/bash
#
#SBATCH --job-name=mcts_T37
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T37_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T37_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=15:18:07

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T37 on $(hostname) at $(date)"
echo "Game: Radran"
echo "Variant: McBRAVE | Random | MonteCarlo | Robust"
echo "Meta: moveTime=0.2, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=4, mem=7G, time=15:18:07"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T37" --out "${OUT_DIR}/T37.csv"

echo "Job completed at $(date)"
