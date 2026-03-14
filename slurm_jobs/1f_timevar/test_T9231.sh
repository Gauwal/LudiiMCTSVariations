#!/bin/bash
#
#SBATCH --job-name=mcts_T9231
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T9231_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T9231_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T9231 on $(hostname) at $(date)"
echo "Game: Centripetal Force"
echo "Variant: UCB1 | Heuristic | MonteCarlo | Robust"
echo "Meta: moveTime=1.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=7G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T9231" --out "${OUT_DIR}/T9231.csv"

echo "Job completed at $(date)"
